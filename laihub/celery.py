"""Celery application for the laihub project.

Workers are configured at runtime to consume one of two queues:
    - `cpu`: lightweight tasks (ffmpeg extract, lai.py, matplotlib preview).
    - `gpu`: `pipeline.tasks.reconstruct` only (calls demo.py / LingBot-Map).

Routing is declared in settings.CELERY_TASK_ROUTES so a queue change does not
need a task signature change.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "laihub.settings")

app = Celery("laihub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
