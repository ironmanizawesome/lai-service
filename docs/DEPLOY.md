# M6 — Public Deployment Guide

Split deployment: **public web on Render (CPU)** + **GPU worker at home (RTX 5080)**.
They never share a disk — they talk only through three managed services:

```
                    ┌─────────────── Neon (Postgres) ───────────────┐
[phone/browser]     │              Upstash (Redis broker)            │
      │             │           Cloudflare R2 (object storage)       │
      ▼             └───────▲───────────────────────────────▲────────┘
  Render web ───────────────┘ (enqueue job, read results)   │
  (Django + gunicorn)                                        │ (pull job, pull video,
                                                             │  push preview+results)
                                              Home RTX 5080 ─┘
                                              (Celery worker → precompute_npz.py)
```

The home worker makes **only outbound connections** — no port-forwarding or tunnel needed.

> All four accounts below have free tiers sufficient for this MVP.

---

## 1. Cloudflare R2 (object storage)

1. Cloudflare dashboard → **R2** → *Create bucket* → name `laihub-media` → region *Automatic*.
2. R2 → *Manage R2 API Tokens* → **Create API Token**:
   - Permission: **Object Read & Write**
   - Bucket: `laihub-media` (scope to this bucket)
   - Create → copy **Access Key ID** and **Secret Access Key** (shown once).
3. Note your **endpoint**: R2 → bucket → *Settings* → S3 API →
   `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

You now have: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`,
`AWS_STORAGE_BUCKET_NAME=laihub-media`.

> Media (videos, previews) are kept **private** and served via short-lived signed URLs.

---

## 2. Neon (Postgres)

1. [neon.tech](https://neon.tech) → new project → region **AWS ap-southeast-1 (Singapore)** (closest to Korea).
2. Copy the **connection string** (it looks like
   `postgres://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/dbname?sslmode=require`).

You now have: `DATABASE_URL`.

---

## 3. Upstash (Redis)

1. [upstash.com](https://upstash.com) → **Create Database** → Redis → region **ap-northeast-1 / Singapore**.
2. On the database page, copy the **TLS** URL (starts with `rediss://`), e.g.
   `rediss://default:PASSWORD@xxx.upstash.io:6379`.

Use database `/0` for the broker and `/1` for results:

```
CELERY_BROKER_URL=rediss://default:PASSWORD@xxx.upstash.io:6379/0
CELERY_RESULT_BACKEND=rediss://default:PASSWORD@xxx.upstash.io:6379/1
```

---

## 4. Push to GitHub

```bash
cd c:/Users/ironm/dev/lai-service
git add -A
git commit -m "feat(M6): split deployment (Render web + R2 storage + home GPU worker)"
git push origin main          # create the GitHub repo first if needed
```

---

## 5. Deploy the web tier on Render

1. [render.com](https://render.com) → **New → Blueprint** → connect the GitHub repo.
   Render reads [`render.yaml`](../render.yaml) and creates the `laihub-web` service.
2. When prompted (or in *Environment* after creation), set the `sync: false` secrets:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon string (step 2) |
   | `CELERY_BROKER_URL` | Upstash `rediss://.../0` (step 3) |
   | `CELERY_RESULT_BACKEND` | Upstash `rediss://.../1` |
   | `AWS_STORAGE_BUCKET_NAME` | `laihub-media` |
   | `AWS_ACCESS_KEY_ID` | R2 key (step 1) |
   | `AWS_SECRET_ACCESS_KEY` | R2 secret (step 1) |
   | `AWS_S3_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
   | `DJANGO_ALLOWED_HOSTS` | *(leave blank — the onrender.com host is auto-trusted)* |
   | `CSRF_TRUSTED_ORIGINS` | *(leave blank initially)* |

   `DJANGO_SECRET_KEY` is generated automatically. `AWS_S3_REGION_NAME=auto` and
   `DJANGO_DEBUG=False` are set in the blueprint.
3. **Manual Deploy** after secrets are set. The build runs
   `pip install → collectstatic → migrate` (this creates the tables on Neon).
4. When live, your URL is `https://laihub-web-XXXX.onrender.com`.

> First build failing on `migrate`? It means a secret wasn't set yet — set it and redeploy.

---

## 6. Create the admin user (from home, against Neon)

Render's free tier has no shell, but your home machine can reach the **same Neon DB**.
Create `.env.worker` first (step 7), then:

```powershell
cd c:\Users\ironm\dev\lai-service
$env:ENV_FILE = "$PWD\.env.worker"
.\.venv\Scripts\python.exe manage.py createsuperuser
```

This writes the superuser into Neon, so you can log into `…onrender.com/admin/`.

> Email/password signup works immediately (email verification is *optional*; no SMTP needed).
> Google login is an optional follow-up — add the callback
> `https://<your-host>/accounts/google/login/callback/` in Google Cloud Console and
> register a SocialApp in admin.

---

## 7. Run the home GPU worker

```powershell
cd c:\Users\ironm\dev\lai-service
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt          # picks up storages/boto3/psycopg

copy .env.worker.example .env.worker
notepad .env.worker                      # fill in the SAME cloud creds as Render
                                         # + local LINGBOT_MAP_PYTHON (conda env)
.\scripts\run_worker_cloud.ps1
```

The worker connects to Upstash, waits for jobs, downloads each video from R2,
runs inference on the 5080, and pushes the preview + result rows back. Leave this
window open while the service is in use.

---

## 8. End-to-end test

1. Open `https://…onrender.com` on your phone → sign up → create a crop → upload a short clip.
2. Watch the home worker window: it should log the job, run `precompute_npz.py`, finish.
3. The measurement page flips to **done** with the 3D preview + LAI summary.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Upload OK but stuck on "분석 중" | Home worker not running, or `CELERY_BROKER_URL` differs between Render and `.env.worker`. |
| Worker error `NoCredentialsError` / bucket | R2 keys/endpoint mismatch between the two sides. |
| `SSL required` on DB | Keep `?sslmode=require` in `DATABASE_URL`. |
| Preview image 403 | Signed URL expired (default 1h) — just reload the page. |
| Web 400 Bad Request | Custom domain not in `DJANGO_ALLOWED_HOSTS` (onrender.com is auto-trusted). |
| Cold start ~30-50s | Render free sleeps after 15 min idle — expected. |
