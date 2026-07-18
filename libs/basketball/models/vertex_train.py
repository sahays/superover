"""YOLO11n basketball fine-tune — Vertex AI custom-job entrypoint (GPU).

This script does NOT run locally: ``scripts/basketball_train_vertex.py`` stages
it to GCS and a Vertex AI custom job executes it on a GPU node inside a
prebuilt PyTorch container. See libs/basketball/models/README.md.

Sequence: install the toolchain -> assert CUDA (fail fast, never silently
train on CPU) -> pull the pinned dataset snapshot from GCS -> fine-tune
YOLO11n -> export ONNX (static shape, the size the detect wrapper reads back)
-> upload the ONNX plus a metrics/provenance JSON to the output GCS prefix.

The dataset comes from GCS, not the Roboflow API: the snapshot is downloaded
once (see the ``--upload-dataset`` flow in the submitter) and reused, so runs
are reproducible and no Roboflow API key ever reaches the job spec.

The ultralytics toolchain is AGPL-3.0 and is used here for *training and
export only*, on an ephemeral Vertex node. No AGPL code ships in this repo or
its services — runtime inference is onnxruntime against the exported ONNX.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

LOCAL_DATASET = Path("/tmp/dataset")


def _run(*cmd: str) -> None:
    print(f"+ {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd)


def _pip_install() -> None:
    """Install the training toolchain into the prebuilt container."""
    _run(sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip")
    # onnx/onnxslim are needed by ultralytics' ONNX export; onnxruntime lets us
    # verify the export loads before we ship it.
    _run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        "ultralytics",
        "onnx",
        "onnxslim",
        "onnxruntime",
        "google-cloud-storage",
    )


def _assert_cuda() -> str:
    """Fail fast if pip resolved a CPU-only torch — a silent CPU train would
    burn hours of GPU-priced node time and look like a hang."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            f"CUDA is not available to torch (version {torch.__version__}). The pip install "
            "likely replaced the container's GPU torch with a CPU wheel. Refusing to train on "
            "CPU — pin a torch version compatible with the container instead."
        )
    name = torch.cuda.get_device_name(0)
    print(f"CUDA OK: {name} | torch {torch.__version__}", flush=True)
    return name


def _fetch_dataset(dataset_uri: str) -> Path:
    """Pull the dataset snapshot from GCS and pin data.yaml to absolute paths.

    Roboflow's data.yaml uses relative paths ('../train/images') that resolve
    against ultralytics' dataset root rather than the file, which breaks once
    the tree moves. Rewriting them absolute removes the ambiguity.
    """
    LOCAL_DATASET.mkdir(parents=True, exist_ok=True)
    _run("gcloud", "storage", "rsync", "-r", dataset_uri.rstrip("/"), str(LOCAL_DATASET))

    data_yaml = LOCAL_DATASET / "data.yaml"
    if not data_yaml.is_file():
        raise FileNotFoundError(f"no data.yaml under {dataset_uri} (got: {sorted(p.name for p in LOCAL_DATASET.iterdir())})")
    spec = yaml.safe_load(data_yaml.read_text())
    for split, sub in (("train", "train"), ("val", "valid"), ("test", "test")):
        images = LOCAL_DATASET / sub / "images"
        if images.is_dir():
            spec[split] = str(images)
    data_yaml.write_text(yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")
    counts = {s: len(list((LOCAL_DATASET / s / "images").glob("*"))) for s in ("train", "valid", "test") if (LOCAL_DATASET / s / "images").is_dir()}
    print(f"dataset ready at {LOCAL_DATASET}: {counts}", flush=True)
    print(f"classes ({spec.get('nc')}): {spec.get('names')}", flush=True)
    return data_yaml


def _upload(local: Path, uri: str) -> None:
    from google.cloud import storage

    assert uri.startswith("gs://"), uri
    bucket_name, _, blob_name = uri[len("gs://") :].partition("/")
    client = storage.Client()
    client.bucket(bucket_name).blob(blob_name).upload_from_filename(str(local))
    print(f"uploaded {local} -> {uri}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-uri", required=True, help="gs://.../basketball-player-detection-3-v18")
    parser.add_argument("--base-weights", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960, help="960: the ball and rim are small objects")
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--output-uri", required=True, help="gs://bucket/prefix for the ONNX + metrics")
    args = parser.parse_args()

    _pip_install()
    gpu_name = _assert_cuda()
    data_yaml = _fetch_dataset(args.dataset_uri)

    # --- Train ---
    from ultralytics import YOLO

    model = YOLO(args.base_weights)
    model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        patience=args.patience,
        name="yolo11n-basketball",
    )

    metrics = model.val()
    per_class = {}
    try:
        names = model.names
        for i, ap in enumerate(metrics.box.maps):
            per_class[str(names[i])] = round(float(ap), 4)
    except Exception as exc:  # metrics shape varies across ultralytics versions
        print(f"warning: could not extract per-class mAP: {exc}", flush=True)

    # --- Export ONNX (static shape: the detect wrapper reads size from the model) ---
    best = Path(model.trainer.best)
    exported = YOLO(str(best)).export(format="onnx", imgsz=args.imgsz, dynamic=False, simplify=True)
    onnx_path = Path(exported)
    print(f"exported {onnx_path} ({onnx_path.stat().st_size} bytes)", flush=True)

    # Verify the export loads and report its class table — detect.py reads these
    # names from ONNX metadata and maps them to canonical roles.
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    meta = session.get_modelmeta().custom_metadata_map or {}
    print(f"onnx input: {session.get_inputs()[0].shape}", flush=True)
    print(f"onnx names metadata: {meta.get('names')}", flush=True)

    summary = {
        "base_weights": args.base_weights,
        "dataset": {
            "uri": args.dataset_uri,
            "source": "Roboflow Universe roboflow-jvuqo/basketball-player-detection-3-ycjdo v18",
            "license": "CC BY 4.0",
        },
        "train": {
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "patience": args.patience,
            "gpu": gpu_name,
        },
        "metrics": {"mAP50_95_per_class": per_class, "mAP50_95_mean": round(float(metrics.box.map), 4)},
        "onnx": {"input_shape": [str(d) for d in session.get_inputs()[0].shape], "names": meta.get("names")},
    }

    out_prefix = args.output_uri.rstrip("/")
    stem = f"yolo11n-basketball-{args.imgsz}"
    local_summary = Path("/tmp/train_summary.json")
    local_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _upload(onnx_path, f"{out_prefix}/{stem}.onnx")
    _upload(local_summary, f"{out_prefix}/{stem}.metrics.json")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
