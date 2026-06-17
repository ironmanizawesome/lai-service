"""Analytics views: Chart.js JSON endpoint for project trend."""

from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import OwnerRequiredMixin
from apps.projects.models import CropProject


class TrendJSONView(OwnerRequiredMixin, View):
    """Return Chart.js-ready JSON for a project's LAI time-series + 14-day forecast.

    URL: /app/projects/<uuid>/trend.json
    Auth: login required, owner-only (returns 404 for foreign objects)
    """

    model = CropProject
    owner_field = "owner"

    def get(self, request, pk):
        project = get_object_or_404(CropProject, pk=pk, owner=request.user)

        # ── Historical measurements ───────────────────────────────────────────
        measurements = (
            project.measurements
            .filter(status="done")
            .select_related("result")
            .order_by("captured_at")
        )

        actual_points = []
        for m in measurements:
            if hasattr(m, "result") and m.result.agg_column_lai is not None:
                actual_points.append({
                    "x": m.captured_at.strftime("%Y-%m-%d"),
                    "y": round(float(m.result.agg_column_lai), 3),
                })

        # ── Trend + forecast ─────────────────────────────────────────────────
        forecast_points = []
        r2 = None
        low_confidence = True
        n_points = len(actual_points)

        try:
            snap = project.trend
            r2 = snap.r_squared
            low_confidence = r2 < 0.3

            if actual_points:
                from datetime import timedelta
                import datetime

                t0_str = actual_points[0]["x"]
                t0 = datetime.date.fromisoformat(t0_str)
                for item in snap.forecast:
                    d = t0 + timedelta(days=item["day_offset"])
                    forecast_points.append({
                        "x": d.strftime("%Y-%m-%d"),
                        "y": round(item["value"], 3),
                    })
        except CropProject.trend.RelatedObjectDoesNotExist:
            pass

        return JsonResponse({
            "n_points": n_points,
            "r_squared": r2,
            "low_confidence": low_confidence,
            "datasets": [
                {
                    "id": "actual",
                    "label": "LAI 실측",
                    "data": actual_points,
                    "borderColor": "#22c55e",
                    "backgroundColor": "rgba(34,197,94,0.12)",
                    "tension": 0.3,
                    "pointRadius": 5,
                },
                {
                    "id": "forecast",
                    "label": "예측 (14일)",
                    "data": forecast_points,
                    "borderColor": "#f59e0b",
                    "backgroundColor": "rgba(245,158,11,0.08)",
                    "borderDash": [6, 4],
                    "tension": 0.2,
                    "pointRadius": 2,
                },
            ],
        })
