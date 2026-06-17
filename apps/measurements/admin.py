from django.contrib import admin

from .models import Measurement


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "status", "progress_pct", "captured_at", "pinned")
    list_filter = ("status", "pinned")
    search_fields = ("project__name", "project__owner__email", "celery_task_id")
    raw_id_fields = ("project",)
    date_hierarchy = "captured_at"
    readonly_fields = ("id", "celery_task_id", "started_at", "finished_at")
