from django.urls import path

from apps.measurements import views as m_views

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.ProjectDetailView.as_view(), name="detail"),
    path("<uuid:project_pk>/measure/", m_views.UploadView.as_view(), name="measure"),
]
