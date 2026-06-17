from django.db import models


class MeasurementResult(models.Model):
    """Aggregate, headline metrics per Measurement.

    Per-component (per-pot) values are split into `ResultComponent` rows so we can
    query/filter without re-parsing JSON, and so per-pot drilldown is cheap.
    """

    measurement = models.OneToOneField(
        "measurements.Measurement",
        on_delete=models.CASCADE,
        related_name="result",
        primary_key=True,
    )
    pipeline_version = models.CharField(max_length=32)
    up_vector = models.JSONField(help_text="Estimated gravity-up direction [3].")
    basis_uv = models.JSONField(help_text="Footprint plane basis [[3],[3]].")
    n_components = models.PositiveSmallIntegerField(default=0)

    # Aggregate (footprint-area-weighted) values used for the trend graph.
    agg_cover_fraction = models.FloatField(null=True, blank=True)
    agg_column_lai = models.FloatField(null=True, blank=True)
    agg_volume_lai = models.FloatField(null=True, blank=True)
    agg_mean_height_m = models.FloatField(null=True, blank=True)

    # File pointers (relative to MEDIA_ROOT; resolved through storage backend).
    npz_path = models.CharField(max_length=400, blank=True)
    leaf_points_path = models.CharField(max_length=400, blank=True)
    raw_lai_json_path = models.CharField(max_length=400, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Result({self.measurement_id})"


class ResultComponent(models.Model):
    """One row per pot / connected component returned by `pots.separate_pots`."""

    result = models.ForeignKey(
        MeasurementResult,
        on_delete=models.CASCADE,
        related_name="components",
    )
    comp_index = models.PositiveSmallIntegerField()
    n_points = models.PositiveIntegerField()
    centroid_uv = models.JSONField(help_text="[u, v] centroid in footprint plane.")

    # footprint_lai outputs
    leaf_proj_area_m2 = models.FloatField()
    ground_area_m2 = models.FloatField()
    cover_fraction = models.FloatField()

    # column_volume_lai outputs (primary v1 metric for biomass inference)
    column_volume_m3 = models.FloatField(null=True, blank=True)
    mean_height_m = models.FloatField(null=True, blank=True)
    lad_m2_m3 = models.FloatField(null=True, blank=True)
    leaf_area_m2 = models.FloatField(null=True, blank=True)
    volume_lai = models.FloatField(null=True, blank=True)
    canopy_base_h = models.FloatField(null=True, blank=True)
    n_columns = models.PositiveIntegerField(null=True, blank=True)

    # volume_lai (convex-hull) kept as diagnostic only — known to over-estimate
    # connected beds. See lingbot-map memory `lai_pot_track`.
    envelope_volume_m3 = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["comp_index"]
        unique_together = [("result", "comp_index")]
        indexes = [models.Index(fields=["result", "comp_index"])]

    def __str__(self) -> str:
        return f"Component#{self.comp_index} of {self.result_id}"


class Preview3D(models.Model):
    result = models.OneToOneField(
        MeasurementResult,
        on_delete=models.CASCADE,
        related_name="preview",
        primary_key=True,
    )
    image = models.ImageField(upload_to="previews/")
    rendered_at = models.DateTimeField(auto_now_add=True)
