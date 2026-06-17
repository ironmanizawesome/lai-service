from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("demo/trend/", TemplateView.as_view(template_name="core/trend_demo.html"), name="trend_demo"),
    path("demo/slides/", TemplateView.as_view(template_name="core/slides.html"), name="slides"),
    path("healthz/", views.health, name="health"),
    # PWA — manifest + service worker must sit at root scope.
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    path("offline/", views.OfflineView.as_view(), name="offline"),
]
