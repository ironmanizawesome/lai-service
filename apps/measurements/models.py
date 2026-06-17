import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone


def upload_video_path(instance: "Measurement", filename: str) -> str:
    """videos/<owner_id>/<project_id>/<measurement_id>.<ext>"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "mp4"
    return f"videos/{instance.project.owner_id}/{instance.project_id}/{instance.id}.{ext}"


class Measurement(models.Model):
    class Status(models.TextChoices):
        UPLOADING = "uploading", "Uploading"
        QUEUED = "queued", "Queued"
        EXTRACTING = "extracting", "Extracting frames"
        RECONSTRUCT = "reconstruct", "Reconstructing"
        ANALYZING = "analyzing", "Analyzing LAI"
        RENDERING = "rendering", "Rendering preview"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.CropProject",
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    video = models.FileField(upload_to=upload_video_path, null=True, blank=True)
    captured_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the video was recorded (user-editable; defaults to upload time).",
    )
    fps_target = models.PositiveSmallIntegerField(default=10)
    scale_ref_m = models.FloatField(
        null=True,
        blank=True,
        help_text="Known reference length (e.g., pot diameter) for volume_lai scale anchor.",
    )

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADING)
    status_msg = models.CharField(max_length=255, blank=True)
    progress_pct = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=64, blank=True, db_index=True)

    pinned = models.BooleanField(default=False, help_text="If True, NPZ is not auto-deleted.")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_trace = models.TextField(blank=True)

    class Meta:
        ordering = ["-captured_at"]
        indexes = [
            models.Index(fields=["project", "-captured_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} @ {self.captured_at:%Y-%m-%d}"

    def get_absolute_url(self) -> str:
        return reverse("measurements:detail", kwargs={"pk": self.pk})
