from django.contrib import admin

from .models import CropProject, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(CropProject)
class CropProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "crop_type", "species", "created_at", "archived_at")
    list_filter = ("crop_type", "archived_at", "tags")
    search_fields = ("name", "species", "owner__email", "owner__username")
    raw_id_fields = ("owner",)
    filter_horizontal = ("tags",)
    date_hierarchy = "created_at"
