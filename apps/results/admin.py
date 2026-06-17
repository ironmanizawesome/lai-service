from django.contrib import admin

from .models import MeasurementResult, Preview3D, ResultComponent


class ResultComponentInline(admin.TabularInline):
    model = ResultComponent
    extra = 0
    fields = ("comp_index", "n_points", "cover_fraction", "volume_lai", "mean_height_m")
    readonly_fields = fields


@admin.register(MeasurementResult)
class MeasurementResultAdmin(admin.ModelAdmin):
    list_display = (
        "measurement",
        "n_components",
        "agg_cover_fraction",
        "agg_column_lai",
        "pipeline_version",
        "created_at",
    )
    search_fields = ("measurement__id", "pipeline_version")
    raw_id_fields = ("measurement",)
    inlines = [ResultComponentInline]


@admin.register(Preview3D)
class Preview3DAdmin(admin.ModelAdmin):
    list_display = ("result", "rendered_at")
    raw_id_fields = ("result",)
