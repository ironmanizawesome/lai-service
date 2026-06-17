import contextlib
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import default_storage
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView

from apps.core.mixins import OwnerRequiredMixin

from .forms import CropProjectForm
from .models import CropProject


class DashboardView(LoginRequiredMixin, ListView):
    model = CropProject
    template_name = "projects/dashboard.html"
    context_object_name = "projects"
    paginate_by = 24

    def get_queryset(self):
        return CropProject.objects.filter(
            owner=self.request.user,
            archived_at__isnull=True,
        )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = CropProject
    form_class = CropProjectForm
    template_name = "projects/form.html"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class ProjectDetailView(OwnerRequiredMixin, DetailView):
    model = CropProject
    template_name = "projects/detail.html"
    context_object_name = "project"


class ProjectDeleteView(OwnerRequiredMixin, DeleteView):
    model = CropProject
    template_name = "projects/detail.html"
    success_url = reverse_lazy("projects:dashboard")

    def form_valid(self, form):
        project = self.object
        for m in project.measurements.all():
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
