from django.urls import path

from . import views

app_name = "measurements"

urlpatterns = [
    path("<uuid:pk>/", views.MeasurementDetailView.as_view(), name="detail"),
    path("<uuid:pk>/status/", views.StatusPartialView.as_view(), name="status"),
]
