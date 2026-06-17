from django.contrib import admin

from .models import CropProject


@admin.register(CropProject)
class CropProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "crop_type", "species", "created_at", "archived_at")
    list_filter = ("crop_type", "archived_at")
    search_fields = ("name", "species", "owner__email", "owner__username")
    raw_id_fields = ("owner",)
    date_hierarchy = "created_at"
