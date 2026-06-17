"""Celery tasks for the LAI pipeline (M3: real pipeline).

Single task `process_measurement` orchestrates all stages sequentially:
  kickoff    → validate video with ffprobe
  reconstruct → subprocess precompute_npz.py  (lingbot-map Python, GPU)
  analyze    → importlib pipeline.run_pipeline (numpy/scipy, CPU)
  render     → matplotlib 3D scatter PNG (CPU)

GPU queue separation (kickoff/analyze/render=cpu, reconstruct=gpu) is wired
in settings.CELERY_TASK_ROUTES and will be split into separate tasks at M6
when the GPU worker runs on a different machine.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import subprocess
import tempfile
import traceback
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # must precede pyplot import
import matplotlib.pyplot as plt
import numpy as np
from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone


PIPELINE_VERSION = "m3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_status(m, status: str, msg: str, pct: int) -> None:
    m.status = status
    m.status_msg = msg
    m.progress_pct = pct
    m.save(update_fields=["status", "status_msg", "progress_pct"])


def _load_pipeline_module():
    """Import map-LAIpot/pipeline.py from LINGBOT_MAP_ROOT via importlib."""
    root = Path(settings.LINGBOT_MAP_ROOT)
    path = root / "map-LAIpot" / "pipeline.py"
    if not path.exists():
        raise FileNotFoundError(f"pipeline.py not found at {path}")
    spec = importlib.util.spec_from_file_location("lai_pipeline", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _unproject_for_preview(
    depth: np.ndarray, extrinsic: np.ndarray, intrinsic: np.ndarray
) -> np.ndarray:
    """Depth → world points for preview rendering (numpy-only, no torch)."""
    if depth.ndim == 4:
        depth = depth[..., 0]
    S, H, W = depth.shape
    uu, vv = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    chunks = []
    for i in range(S):
        K, d = intrinsic[i], depth[i]
        cam = np.stack(
            [(uu - K[0, 2]) * d / K[0, 0], (vv - K[1, 2]) * d / K[1, 1], d], axis=-1
        )
        R, t = extrinsic[i][:3, :3], extrinsic[i][:3, 3]
        chunks.append((cam @ R.T + t).reshape(-1, 3))
    return np.concatenate(chunks)


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _kickoff(m) -> None:
    """Validate that a video is attached and present in the storage backend.

    Works for both local FileSystemStorage (dev) and S3/R2 (prod): we check
    existence by storage name rather than touching a local path, since under
    object storage there is no local file until _local_video downloads it.
    """
    if not m.video or not m.video.name:
        raise FileNotFoundError("No video attached to this measurement")
    if not default_storage.exists(m.video.name):
        raise FileNotFoundError(f"Video not found in storage: {m.video.name}")


@contextlib.contextmanager
def _local_video(m):
    """Yield a local filesystem path to the measurement's video.

    The GPU subprocess (precompute_npz.py) needs a real local file. Local
    FileSystemStorage already exposes one via .path; object storage (R2) does
    not, so we stream the upload to a temp file and remove it afterwards.
    """
    f = m.video
    try:
        local_path = f.path             # FileSystemStorage → real path
    except (NotImplementedError, ValueError):
        local_path = None               # S3/R2 → no local path

    if local_path is not None:
        if not Path(local_path).exists():
            raise FileNotFoundError(f"Video file not found: {local_path}")
        yield local_path
        return

    # Name the temp file with the measurement id (not a random tempname) so
    # precompute_npz.py derives the expected "<id>_644.npz" output from the
    # video stem — matching npz_path computed by the caller.
    suffix = Path(f.name).suffix or ".mp4"
    tmpdir = tempfile.mkdtemp(prefix="laivideo_")
    local = os.path.join(tmpdir, f"{m.id}{suffix}")
    try:
        f.open("rb")
        with open(local, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)
        f.close()
        yield local
    finally:
        with contextlib.suppress(OSError):
            os.remove(local)
        with contextlib.suppress(OSError):
            os.rmdir(tmpdir)


def _reconstruct(video_path: str, npz_path: Path, fps: int) -> None:
    """Run precompute_npz.py via subprocess to produce the NPZ (GPU stage)."""
    root = Path(settings.LINGBOT_MAP_ROOT)
    python = settings.LINGBOT_MAP_PYTHON
    model = settings.LINGBOT_MAP_MODEL_PATH

    # Resolve model_path: absolute wins, otherwise relative to root
    model_abs = Path(model)
    if not model_abs.is_absolute():
        model_abs = root / model

    npz_path.parent.mkdir(parents=True, exist_ok=True)

    # precompute_npz.py saves <out_dir>/<stem>_<size>.npz where stem = video basename
    # Our video is named <measurement_id>.<ext>, so output = <npz_dir>/<measurement_id>_644.npz
    out_dir = str(npz_path.parent)

    cmd = [
        python, "precompute_npz.py",
        "--model_path", str(model_abs),
        "--video_path", video_path,
        "--fps", str(fps),
        "--first_k", "0",
        "--image_sizes", "644",
        "--max_frame_num", "1200",
        "--use_sdpa",
        "--offload",
        "--mask_sky",
        "--out_dir", out_dir,
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=1800,  # 30 min
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"precompute_npz.py failed (rc={proc.returncode}):\n"
            f"STDOUT: {proc.stdout[-3000:]}\nSTDERR: {proc.stderr[-3000:]}"
        )

    if not npz_path.exists():
        raise FileNotFoundError(
            f"Expected NPZ not found at {npz_path} after precompute_npz.py succeeded. "
            f"stdout tail: {proc.stdout[-500:]}"
        )


def _analyze(npz_path: Path, crop: str, scale_factor: float) -> dict:
    """Run pipeline.run_pipeline() in-process (numpy/scipy only, no torch)."""
    pipeline_mod = _load_pipeline_module()
    return pipeline_mod.run_pipeline(
        npz_path=str(npz_path),
        crop=crop,
        scale_factor=scale_factor,
    )


def _render_preview(npz_path: Path, lai_result: dict) -> bytes:
    """Render side-by-side 3D scatter PNG: left=original RGB, right=ExG leaf points."""
    d = np.load(str(npz_path), allow_pickle=True)
    stride = max(1, d["depth"].shape[0] // 40)
    idx = np.arange(0, d["depth"].shape[0], stride)

    wp = _unproject_for_preview(d["depth"][idx], d["extrinsic"][idx], d["intrinsic"][idx])

    imgs = d["images"][idx]
    if imgs.ndim == 4 and imgs.shape[1] == 3:  # NCHW → NHWC
        imgs = imgs.transpose(0, 2, 3, 1)
    col = np.clip(imgs.reshape(-1, 3), 0.0, 1.0).astype(np.float32)

    cf = d["depth_conf"][idx].reshape(-1)
    valid = np.isfinite(wp).all(1) & np.isfinite(cf) & (np.abs(wp).max(1) < 1e4)
    if not valid.any():
        raise ValueError("No valid points for preview rendering")
    valid &= cf >= np.percentile(cf[valid], 45)
    wp_all, col_all = wp[valid], col[valid]

    # ── 왼쪽: 원본 RGB 포인트 클라우드 ──────────────────────────────────
    rng = np.random.default_rng(0)
    n_rgb = min(len(wp_all), 20_000)
    idx_rgb = rng.choice(len(wp_all), n_rgb, replace=False)
    wp_rgb, col_rgb = wp_all[idx_rgb], col_all[idx_rgb]

    # ── 오른쪽: ExG 잎 필터 + 높이 컬러 ────────────────────────────────
    exg = 2.0 * col_all[:, 1] - col_all[:, 0] - col_all[:, 2]
    wp_leaf = wp_all[exg > 0.06]
    if len(wp_leaf) == 0:
        raise ValueError("No leaf points after ExG filter for preview")
    if len(wp_leaf) > 20_000:
        wp_leaf = wp_leaf[rng.choice(len(wp_leaf), 20_000, replace=False)]

    up = np.array(lai_result["up_vector"], dtype=np.float64)
    heights = wp_leaf @ up
    h_range = heights.max() - heights.min()
    h_norm = (heights - heights.min()) / max(h_range, 1e-8)

    # ── 렌더링 ────────────────────────────────────────────────────────────
    fig, (ax_rgb, ax_leaf) = plt.subplots(
        1, 2, figsize=(14, 6), subplot_kw={"projection": "3d"}
    )

    ax_rgb.scatter(wp_rgb[:, 0], wp_rgb[:, 1], wp_rgb[:, 2],
                   c=col_rgb, s=0.4, alpha=0.5)
    ax_rgb.set_title("원본 RGB 포인트 클라우드")
    ax_rgb.set_xlabel("X"); ax_rgb.set_ylabel("Y"); ax_rgb.set_zlabel("Z")

    ax_leaf.scatter(wp_leaf[:, 0], wp_leaf[:, 1], wp_leaf[:, 2],
                    c=h_norm, cmap="YlGn", s=0.4, alpha=0.5)
    n = lai_result["n_components"]
    ax_leaf.set_title(
        f"잎 포인트 (ExG 필터) — {n}개 컴포넌트\n"
        f"피복률={lai_result['agg_cover_fraction']:.2f}  "
        f"LAI={lai_result['agg_column_lai']:.2f}"
    )
    ax_leaf.set_xlabel("X"); ax_leaf.set_ylabel("Y"); ax_leaf.set_zlabel("Z")

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Main Celery task
# ---------------------------------------------------------------------------

@shared_task(bind=True, queue="cpu", time_limit=3600, soft_time_limit=3300)
def process_measurement(self, measurement_id: str) -> str:
    """Full LAI pipeline: kickoff → reconstruct (GPU subprocess) → analyze → render."""
    from apps.measurements.models import Measurement
    from apps.results.models import MeasurementResult, Preview3D, ResultComponent

    m = Measurement.objects.get(pk=measurement_id)
    m.started_at = timezone.now()
    m.celery_task_id = self.request.id
    m.save(update_fields=["started_at", "celery_task_id"])

    try:
        media_root = Path(settings.MEDIA_ROOT)

        # ── 1. Kickoff: validate the video is present in storage ──────────────
        _set_status(m, "extracting", "영상 검증 중", 10)
        _kickoff(m)

        # ── 2. Reconstruct: precompute_npz → NPZ ─────────────────────────────
        # The GPU subprocess needs a real local file. _local_video returns the
        # FileSystemStorage path directly (dev) or streams the R2 upload to a
        # temp file (prod). The NPZ stays on the worker's local disk — the web
        # tier never reads it (only the preview PNG + DB rows).
        _set_status(m, "reconstruct", "3D 재건 중 (LingBot-Map)", 25)

        npz_dir = media_root / "npz"
        npz_path = npz_dir / f"{m.id}_644.npz"

        with _local_video(m) as video_path:
            _reconstruct(video_path, npz_path, fps=m.fps_target)

        # ── 3. Analyze: pipeline.run_pipeline → JSON ──────────────────────────
        _set_status(m, "analyzing", "LAI 계산 중", 65)

        # Map CropProject.crop_type to pipeline crop name
        crop_type = m.project.crop_type  # "pot" / "crop" / "other"
        crop_name = "strawberry" if crop_type == "pot" else "_generic"
        scale = float(m.scale_ref_m) if m.scale_ref_m else 1.0

        lai_result = _analyze(npz_path, crop=crop_name, scale_factor=scale)

        # Persist raw JSON through the storage backend (→ R2 in prod) so the web
        # tier can serve it even when the worker runs on a different machine.
        json_name = default_storage.save(
            f"results/{m.id}.json",
            ContentFile(
                json.dumps(lai_result, indent=2, ensure_ascii=False).encode("utf-8")
            ),
        )

        # ── 4. Render preview PNG ─────────────────────────────────────────────
        _set_status(m, "rendering", "미리보기 생성 중", 85)

        result_obj = MeasurementResult.objects.create(
            measurement=m,
            pipeline_version=PIPELINE_VERSION,
            up_vector=lai_result["up_vector"],
            basis_uv=[lai_result["basis_u"], lai_result["basis_v"]],
            n_components=lai_result["n_components"],
            agg_cover_fraction=lai_result["agg_cover_fraction"],
            agg_column_lai=lai_result["agg_column_lai"],
            agg_volume_lai=lai_result.get("agg_volume_m3"),
            npz_path=str(npz_path.relative_to(media_root)),
            raw_lai_json_path=json_name,
        )

        for comp in lai_result["components"]:
            ResultComponent.objects.create(
                result=result_obj,
                comp_index=comp["comp_index"],
                n_points=comp["n_points"],
                centroid_uv=comp.get("centroid_uv", [0.0, 0.0]),
                leaf_proj_area_m2=comp["leaf_proj_area_m2"],
                ground_area_m2=comp["ground_area_m2"],
                cover_fraction=comp["cover_fraction"],
                column_volume_m3=comp.get("column_volume_m3"),
                mean_height_m=comp.get("mean_height_m"),
                lad_m2_m3=comp.get("lad_m2_m3"),
                leaf_area_m2=comp.get("leaf_area_m2"),
                volume_lai=comp.get("volume_lai"),
                n_columns=comp.get("n_columns"),
            )

        # Preview (best-effort — failure doesn't abort the task)
        try:
            png_bytes = _render_preview(npz_path, lai_result)
            preview = Preview3D(result=result_obj)
            preview.image.save(f"{m.id}.png", ContentFile(png_bytes), save=True)
        except Exception as prev_exc:
            print(f"[pipeline] Preview render failed (non-fatal): {prev_exc}")

        # NPZ는 결과가 DB+R2에 저장된 후 더 이상 필요 없음 — 즉시 삭제
        with contextlib.suppress(OSError):
            npz_path.unlink(missing_ok=True)

        # ── Done ──────────────────────────────────────────────────────────────
        m.status = "done"
        m.progress_pct = 100
        m.status_msg = "완료"
        m.finished_at = timezone.now()
        m.save(update_fields=["status", "progress_pct", "status_msg", "finished_at"])

        # Recompute trend (best-effort — failure doesn't abort the task)
        try:
            from apps.analytics.services import update_trend
            update_trend(m.project_id)
        except Exception as trend_exc:
            print(f"[pipeline] Trend update failed (non-fatal): {trend_exc}")

    except Exception:
        m.status = "failed"
        m.error_trace = traceback.format_exc()
        m.finished_at = timezone.now()
        m.save(update_fields=["status", "error_trace", "finished_at"])
        raise

    return str(m.id)


# ---------------------------------------------------------------------------
# Cleanup beat task — removes stale NPZ files left by crashed workers
# ---------------------------------------------------------------------------

@shared_task(queue="cpu")
def clean_stale_npz(max_age_days: int = 3) -> str:
    """Delete NPZ files older than max_age_days from MEDIA_ROOT/npz/.

    Normally NPZ is deleted immediately after a successful pipeline run.
    This task is a safety net for files left behind by crashed workers.
    """
    import time

    npz_dir = Path(settings.MEDIA_ROOT) / "npz"
    if not npz_dir.exists():
        return "npz dir not found — nothing to clean"

    cutoff = time.time() - max_age_days * 86400
    removed, skipped = [], []
    for f in npz_dir.glob("*.npz"):
        if f.stat().st_mtime < cutoff:
            f.unlink(missing_ok=True)
            removed.append(f.name)
        else:
            skipped.append(f.name)

    msg = f"clean_stale_npz: removed {len(removed)}, kept {len(skipped)}"
    print(f"[pipeline] {msg}")
    return msg


# ---------------------------------------------------------------------------
# Legacy alias (kept so existing queued fake_process tasks don't break)
# ---------------------------------------------------------------------------

@shared_task(bind=True, queue="cpu")
def fake_process(self, measurement_id: str) -> str:
    """Deprecated M2 stub — routes to process_measurement."""
    return process_measurement.apply(args=[measurement_id], task_id=self.request.id).get()
