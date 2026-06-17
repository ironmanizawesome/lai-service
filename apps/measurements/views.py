import contextlib
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView

from apps.core.mixins import OwnerRequiredMixin
from apps.projects.models import CropProject

from .forms import MeasurementUploadForm
from .models import Measurement


class UploadView(LoginRequiredMixin, CreateView):
    model = Measurement
    form_class = MeasurementUploadForm
    template_name = "measurements/upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.project = get_object_or_404(
            CropProject, pk=kwargs["project_pk"], owner=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["project"] = self.project
        return ctx

    def form_valid(self, form):
        form.instance.project = self.project
        form.instance.status = Measurement.Status.QUEUED
        response = super().form_valid(form)

        from apps.pipeline.tasks import process_measurement

        result = process_measurement.delay(str(self.object.id))
        self.object.celery_task_id = result.id
        self.object.save(update_fields=["celery_task_id"])
        return response


class MeasurementDetailView(OwnerRequiredMixin, DetailView):
    model = Measurement
    template_name = "measurements/detail.html"
    context_object_name = "measurement"
    owner_field = "project__owner"


class StatusPartialView(OwnerRequiredMixin, DetailView):
    model = Measurement
    template_name = "measurements/_status.html"
    context_object_name = "m"
    owner_field = "project__owner"


class MeasurementDeleteView(OwnerRequiredMixin, DeleteView):
    model = Measurement
    template_name = "measurements/detail.html"
    owner_field = "project__owner"

    def get_success_url(self):
        return reverse("projects:detail", kwargs={"pk": self.object.project_id})

    def form_valid(self, form):
        m = self.object
        # Clean up storage files (best-effort)
        with contextlib.suppress(Exception):
            if m.video and m.video.name:
                default_storage.delete(m.video.name)
        with contextlib.suppress(Exception):
            result = m.result
            if result.raw_lai_json_path:
                default_storage.delete(result.raw_lai_json_path)
            if hasattr(result, "preview") and result.preview.image:
                default_storage.delete(result.preview.image.name)
        with contextlib.suppress(Exception):
            npz = Path(settings.MEDIA_ROOT) / "npz" / f"{m.id}_644.npz"
            npz.unlink(missing_ok=True)
        return super().form_valid(form)
