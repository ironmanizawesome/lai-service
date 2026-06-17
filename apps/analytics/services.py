"""Analytics computation: polyfit trend + 14-day forecast."""

from __future__ import annotations

import numpy as np

R2_LOW_CONFIDENCE = 0.3
MIN_POINTS = 2


def update_trend(project_id) -> None:
    """Recompute TrendSnapshot for a project from all DONE measurements.

    - N >= 5: deg-2 polyfit; else deg-1 (linear)
    - R² < 0.3: stored but UI labels as low-confidence
    - Skipped silently if fewer than 2 data points
    """
    from apps.analytics.models import TrendSnapshot
    from apps.projects.models import CropProject

    project = CropProject.objects.get(pk=project_id)
    qs = (
        project.measurements
        .filter(status="done")
        .select_related("result")
        .order_by("captured_at")
    )

    pairs = [
        (m.captured_at, m.result.agg_column_lai)
        for m in qs
        if hasattr(m, "result") and m.result.agg_column_lai is not None
    ]

    n = len(pairs)
    if n < MIN_POINTS:
        return

    t0 = pairs[0][0]
    x = np.array([(t - t0).total_seconds() / 86400.0 for t, _ in pairs])
    y = np.array([v for _, v in pairs])

    deg = 2 if n >= 5 else 1
    coeffs = np.polyfit(x, y, deg)

    y_pred = np.polyval(coeffs, x)
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = round(1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0, 4)

    # Forecast: day-by-day from last observation to +14 days
    x_last = float(x[-1])
    forecast = [
        {"day_offset": int(x_last) + d, "value": round(float(np.polyval(coeffs, x_last + d)), 4)}
        for d in range(0, 15)
    ]

    TrendSnapshot.objects.update_or_create(
        project=project,
        defaults={
            "metric": "agg_column_lai",
            "poly_degree": int(deg),
            "coeffs": coeffs.tolist(),
            "r_squared": r2,
            "horizon_days": 14,
            "forecast": forecast,
            "n_points": n,
        },
    )
