from django.contrib import admin

from .models import TrendSnapshot


@admin.register(TrendSnapshot)
class TrendSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "metric", "poly_degree", "r_squared", "n_points", "computed_at")
    list_filter = ("metric", "poly_degree")
    search_fields = ("project__name", "project__owner__email")
    raw_id_fields = ("project",)
