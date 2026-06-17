from django.http import HttpResponse
from django.views.generic import TemplateView
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string


class HomeView(TemplateView):
    template_name = "core/home.html"


class OfflineView(TemplateView):
    """Fallback page the service worker serves when a navigation fails offline."""
    template_name = "pwa/offline.html"


def health(request):
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def manifest(request):
    """PWA manifest. Served at /manifest.webmanifest (root scope)."""
    body = render_to_string("pwa/manifest.webmanifest", request=request)
    return HttpResponse(body, content_type="application/manifest+json")


@require_GET
def service_worker(request):
    """Service worker. MUST be served from root so its scope covers the whole site.

    A SW at /static/service-worker.js would only control /static/, so we serve it
    via this view at /service-worker.js instead.
    """
    body = render_to_string("pwa/service-worker.js", request=request)
    resp = HttpResponse(body, content_type="application/javascript")
    # Allow the SW to claim the root scope even though the file path is /service-worker.js.
    resp["Service-Worker-Allowed"] = "/"
    # SWs should not be cached aggressively or updates never ship.
    resp["Cache-Control"] = "no-cache"
    return resp
