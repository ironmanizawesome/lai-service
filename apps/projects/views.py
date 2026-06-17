from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, DetailView, ListView

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
