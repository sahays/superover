#!/usr/bin/env python3
"""Submit the basketball YOLO11n fine-tune as a Vertex AI custom job.

Trains on a rented GPU (no local GPU needed) and lands a CPU-only ONNX in
libs/basketball/models/. Drives everything through the ``gcloud`` CLI, so it
needs no Python GCP deps — the ``.venv-basketball`` environment stays offline
by design.

GCS layout follows the root ``.env``: a single shared bucket (``UPLOADS_BUCKET``)
namespaced by ``SERVICE_NAME``, matching the repo's existing convention::

    gs://<bucket>/<service>/basketball/datasets/<name>/   # pinned snapshot
    gs://<bucket>/<service>/basketball/trainer/           # this repo's trainer
    gs://<bucket>/<service>/basketball/runs/<run>/        # ONNX + metrics

The dataset is a pinned GCS snapshot, not a live Roboflow pull: no Roboflow
API key ever reaches the job spec, and re-runs train on identical data.

    # one-off: snapshot the local Roboflow export into GCS
    python scripts/basketball_train_vertex.py --upload-dataset

    # submit, wait, and fetch the ONNX
    python scripts/basketball_train_vertex.py

    # submit and return immediately / fetch a finished run
    python scripts/basketball_train_vertex.py --no-wait
    python scripts/basketball_train_vertex.py --fetch-only

Region/GPU defaults are chosen against this project's verified quota:
asia-south1 (the repo's GCP_REGION) has CustomModelTraining L4 = 28 and
T4 = 6, so neither needs a quota increase.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAINER = REPO_ROOT / "libs" / "basketball" / "models" / "vertex_train.py"
MODELS_DIR = REPO_ROOT / "libs" / "basketball" / "models"
DATASET_NAME = "basketball-player-detection-3-v18"
LOCAL_DATASET = MODELS_DIR / "dataset" / DATASET_NAME
ENV_FILE = REPO_ROOT / ".env"

# Verified to exist (registry probe, 2026-07-17). The '.py310' suffix is
# required — 'pytorch-gpu.2-4' alone does not resolve.
CONTAINER = "us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-4.py310:latest"

# L4 by default: 28 quota in asia-south1 vs 6 for T4, and faster at imgsz=960.
GPU_PRESETS = {
    "l4": ("g2-standard-8", "NVIDIA_L4"),
    "t4": ("n1-standard-8", "NVIDIA_TESLA_T4"),
}


def read_env(path: Path = ENV_FILE) -> dict:
    """Parse the root .env (KEY=VALUE, '#' comments) — the single source of
    truth for project/region/bucket, same as deploy.sh consumes."""
    values: dict = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("\"'")
    return values


def run(cmd: list, capture: bool = False, check: bool = True) -> str:
    print(f"+ {' '.join(str(c) for c in cmd)}", file=sys.stderr)
    result = subprocess.run([str(c) for c in cmd], capture_output=capture, text=True, check=False)
    if check and result.returncode != 0:
        if capture and result.stderr:
            print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(str(c) for c in cmd)}")
    return (result.stdout or "").strip()


def parse_args(argv=None) -> argparse.Namespace:
    env = read_env()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=env.get("GCP_PROJECT_ID"), help="default: .env GCP_PROJECT_ID")
    parser.add_argument("--region", default=env.get("GCP_REGION", "asia-south1"), help="default: .env GCP_REGION")
    parser.add_argument("--bucket", default=env.get("UPLOADS_BUCKET"), help="default: .env UPLOADS_BUCKET")
    parser.add_argument("--service", default=env.get("SERVICE_NAME", "superover"), help="default: .env SERVICE_NAME")
    parser.add_argument("--gpu", choices=sorted(GPU_PRESETS), default="l4")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--upload-dataset", action="store_true", help="Sync the local dataset snapshot to GCS and exit")
    parser.add_argument("--no-wait", action="store_true", help="Submit and return without polling")
    parser.add_argument("--fetch-only", action="store_true", help="Download the ONNX from a finished run and exit")
    parser.add_argument("--display-name", default=None)
    return parser.parse_args(argv)


def prefixes(args) -> dict:
    base = f"gs://{args.bucket}/{args.service}/basketball"
    return {
        "dataset": f"{base}/datasets/{DATASET_NAME}",
        "trainer": f"{base}/trainer/vertex_train.py",
        "output": f"{base}/runs/yolo11n-basketball",
    }


def make_worker_pool_spec(args, uris: dict) -> dict:
    machine_type, accelerator = GPU_PRESETS[args.gpu]
    trainer_args = [
        f"--dataset-uri={uris['dataset']}",
        f"--output-uri={uris['output']}",
        f"--epochs={args.epochs}",
        f"--imgsz={args.imgsz}",
        f"--batch={args.batch}",
    ]
    # Pull the trainer from GCS at start, then run it. gsutil and gcloud are
    # both normally present in the prebuilt image; try each before giving up,
    # so a missing tool fails with a clear message rather than a bare 127.
    fetch = (
        f"gsutil cp {uris['trainer']} /tmp/vertex_train.py "
        f"|| gcloud storage cp {uris['trainer']} /tmp/vertex_train.py "
        f'|| {{ echo "FATAL: no gsutil/gcloud in image to fetch {uris["trainer"]}"; exit 1; }}'
    )
    command = [
        "bash",
        "-c",
        f"set -euo pipefail; {fetch}; " 'exec python /tmp/vertex_train.py "$@"',
        "--",  # bash -c: $0 placeholder so "$@" starts at the first real arg
    ]
    return {
        "machineSpec": {
            "machineType": machine_type,
            "acceleratorType": accelerator,
            "acceleratorCount": 1,
        },
        "replicaCount": 1,
        "diskSpec": {"bootDiskType": "pd-ssd", "bootDiskSizeGb": 200},
        "containerSpec": {"imageUri": CONTAINER, "command": command, "args": trainer_args},
    }


def fetch_onnx(output_uri: str, imgsz: int) -> Path:
    stem = f"yolo11n-basketball-{imgsz}"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    local_onnx = MODELS_DIR / f"{stem}.onnx"
    run(["gcloud", "storage", "cp", f"{output_uri}/{stem}.onnx", str(local_onnx)])
    local_metrics = MODELS_DIR / f"{stem}.metrics.json"
    run(["gcloud", "storage", "cp", f"{output_uri}/{stem}.metrics.json", str(local_metrics)], check=False)
    if local_metrics.is_file():
        print("\n--- training metrics ---")
        print(local_metrics.read_text(encoding="utf-8"))
    return local_onnx


def main(argv=None) -> int:
    args = parse_args(argv)
    for field in ("project", "bucket"):
        if not getattr(args, field):
            print(f"Error: --{field} not set and not found in {ENV_FILE}", file=sys.stderr)
            return 1
    uris = prefixes(args)

    if args.upload_dataset:
        if not LOCAL_DATASET.is_dir():
            print(f"Error: local dataset not found at {LOCAL_DATASET}", file=sys.stderr)
            return 1
        run(["gcloud", "storage", "rsync", "-r", str(LOCAL_DATASET), uris["dataset"]])
        print(f"dataset -> {uris['dataset']}")
        return 0

    if args.fetch_only:
        local = fetch_onnx(uris["output"], args.imgsz)
        print(f"\nONNX -> {local}\nexport BASKETBALL_DETECT_MODEL_PATH={local.relative_to(REPO_ROOT)}")
        return 0

    if not TRAINER.is_file():
        print(f"Error: trainer not found at {TRAINER}", file=sys.stderr)
        return 1

    # Stage the trainer where the job can read it.
    run(["gcloud", "storage", "cp", str(TRAINER), uris["trainer"]])

    display_name = args.display_name or f"yolo11n-basketball-{time.strftime('%Y%m%d-%H%M%S')}"
    # gcloud --config wants a CustomJobSpec YAML keyed by workerPoolSpecs (JSON
    # is valid YAML, so we emit JSON). camelCase only — underscores are invalid.
    config_path = Path("/tmp/vertex_custom_job.yaml")
    config_path.write_text(json.dumps({"workerPoolSpecs": [make_worker_pool_spec(args, uris)]}, indent=2), encoding="utf-8")

    run(
        [
            "gcloud",
            "ai",
            "custom-jobs",
            "create",
            f"--region={args.region}",
            f"--project={args.project}",
            f"--display-name={display_name}",
            f"--config={config_path}",
        ]
    )
    print(f"\nSubmitted '{display_name}' to {args.region} ({args.gpu.upper()}).")
    print(f"Dataset: {uris['dataset']}")
    print(f"Output:  {uris['output']}")

    if args.no_wait:
        print(f"\nWhen it finishes: python {Path(__file__).name} --fetch-only")
        return 0

    print("\nPolling for completion (Ctrl-C is safe — the job keeps running)...")
    while True:
        time.sleep(60)
        listing = run(
            [
                "gcloud",
                "ai",
                "custom-jobs",
                "list",
                f"--region={args.region}",
                f"--project={args.project}",
                f"--filter=displayName={display_name}",
                "--format=value(state)",
            ],
            capture=True,
            check=False,
        )
        state = listing.splitlines()[0] if listing else "UNKNOWN"
        print(f"  state: {state}", file=sys.stderr)
        if "SUCCEEDED" in state:
            break
        if any(bad in state for bad in ("FAILED", "CANCELLED", "EXPIRED")):
            print(f"Job ended in state {state}. Check the logs.", file=sys.stderr)
            return 1

    local = fetch_onnx(uris["output"], args.imgsz)
    print(f"\nONNX -> {local}")
    print(f"export BASKETBALL_DETECT_MODEL_PATH={local.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
