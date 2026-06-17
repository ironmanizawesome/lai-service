# Home GPU worker → CLOUD data tier (Neon Postgres + Upstash Redis + R2).
#
# Runs the Celery worker in the lai-service .venv. The worker shells out to
# LINGBOT_MAP_PYTHON (conda env w/ torch+CUDA) for precompute_npz.py, so this
# machine is the only place inference actually runs.
#
# Prereq:  copy .env.worker.example -> .env.worker and fill in the cloud creds
#          (same DATABASE_URL / CELERY_BROKER_URL / AWS_* as the Render web).
#
# Usage:   .\scripts\run_worker_cloud.ps1
#
# The worker only makes OUTBOUND connections (pull jobs, pull video, push
# results) — no inbound port or tunnel is needed on this machine.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.worker"

if (-not (Test-Path $envFile)) {
    Write-Error "Missing $envFile — copy .env.worker.example to .env.worker and fill in cloud creds."
}

Set-Location $root
$env:ENV_FILE = $envFile

# Start celery beat in background (cleanup schedule)
Write-Host "Starting celery beat (background)..." -ForegroundColor Yellow
$beatJob = Start-Job -ScriptBlock {
    param($py, $root, $envFile)
    $env:ENV_FILE = $envFile
    Set-Location $root
    & $py -m celery -A laihub beat -l warning --scheduler celery.beat.PersistentScheduler
} -ArgumentList $py, $root, $envFile

Write-Host "Starting cloud-connected GPU worker (Q=cpu,gpu, pool=solo)..." -ForegroundColor Green
try {
    & $py -m celery -A laihub worker -Q cpu,gpu --pool=solo -l info
} finally {
    Write-Host "Stopping beat..." -ForegroundColor Yellow
    Stop-Job $beatJob -PassThru | Remove-Job
}
