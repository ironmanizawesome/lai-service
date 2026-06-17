from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user. Future-proofs schema changes; default fields plus profile."""

    display_name = models.CharField(max_length=80, blank=True)
    locale = models.CharField(max_length=8, default="ko")
    storage_quota_mb = models.PositiveIntegerField(default=5_000)

    class Meta:
        indexes = [models.Index(fields=["email"])]

    def __str__(self) -> str:
        return self.display_name or self.username or self.email
