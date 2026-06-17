from django.http import HttpResponse
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "core/home.html"


def health(request):
    return HttpResponse("ok", content_type="text/plain")
