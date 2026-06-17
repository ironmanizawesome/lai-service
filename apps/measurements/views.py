from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.views.generic import CreateView, DetailView

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
