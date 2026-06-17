# Dev Celery worker with auto-restart on code changes (watchdog/watchmedo).
#
# Django's runserver already auto-reloads .py + templates, but Celery does not —
# this wraps the worker in watchmedo so editing apps/**.py or laihub/**.py
# restarts the worker automatically (no more manual Ctrl+C).
#
# Usage (from anywhere):
#   .\scripts\run_worker.ps1
#
# Redis must be running (docker container laihub-redis). Stop with Ctrl+C.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$watchmedo = Join-Path $root ".venv\Scripts\watchmedo.exe"

Set-Location $root

& $watchmedo auto-restart `
    --directory "$root\apps" `
    --directory "$root\laihub" `
    --patterns "*.py" `
    --recursive `
    --no-restart-on-command-exit `
    --ignore-patterns "*\__pycache__\*;*\migrations\*" `
    -- $py -m celery -A laihub worker -Q cpu --pool=solo -l info
