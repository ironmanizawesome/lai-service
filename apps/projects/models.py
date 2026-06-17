import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class Tag(models.Model):
    """Free-form label shared across crop projects — a many-to-many (N:N) relation.

    One project can carry several tags (e.g. "strawberry", "greenhouse-A", "bed-1")
    and each tag groups many projects, so neither side "owns" the other.
    """

    name = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CropProject(models.Model):
    """A user's tracking space for one crop instance (a single bed, pot, or plant).

    `crop_type` selects which LAI pipeline branch downstream Measurements use.
    v1 implements `POT` (map-LAIpot); `CROP` (map-LAIcrop) is reserved for v2.
    """

    class CropType(models.TextChoices):
        POT = "pot", "Pot (greenhouse, per-pot)"
        CROP = "crop", "Field crop (outdoor, drone) — coming soon"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=120)
    crop_type = models.CharField(
        max_length=8,
        choices=CropType.choices,
        default=CropType.POT,
    )
    species = models.CharField(
        max_length=60,
        blank=True,
        help_text="Lowercase common name (strawberry, watermelon, tomato). Drives LAD lookup.",
    )
    planted_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="projects",
        help_text="Shared labels grouping projects (many-to-many).",
    )
    cover_thumb = models.ImageField(upload_to="thumbs/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"]),
            models.Index(fields=["owner", "crop_type"]),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("projects:detail", kwargs={"pk": self.pk})
