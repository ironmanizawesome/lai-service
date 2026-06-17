from django.db import models


class TrendSnapshot(models.Model):
    """Cached numpy.polyfit regression for a CropProject's measurement series.

    Invalidated and recomputed in `apps.pipeline.tasks.finalize` after every new
    Measurement reaches DONE state. R^2 below the threshold signals a low-confidence
    trend that the UI should label as such instead of confidently extrapolating.
    """

    project = models.OneToOneField(
        "projects.CropProject",
        on_delete=models.CASCADE,
        related_name="trend",
        primary_key=True,
    )
    metric = models.CharField(max_length=24, default="agg_column_lai")
    poly_degree = models.PositiveSmallIntegerField(default=1)
    coeffs = models.JSONField(help_text="numpy.polyfit output, highest power first.")
    r_squared = models.FloatField()
    horizon_days = models.PositiveSmallIntegerField(default=14)
    forecast = models.JSONField(help_text="[{day_offset, value}, ...]")
    n_points = models.PositiveSmallIntegerField()
    computed_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Trend({self.project_id}, R²={self.r_squared:.2f})"
