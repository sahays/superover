# Detection models (`detect` stage)

ONNX model binaries live in this directory but are **never committed**
(`.gitignore` here excludes `*.onnx`). Every developer/CI environment obtains
a model via one of the two paths below, then points the pipeline at it:

```bash
export BASKETBALL_DETECT_MODEL_PATH=libs/basketball/models/<model>.onnx
```

The wrapper (`libs/basketball/detect.py`) reads class names from the ONNX
metadata and translates them to the pipeline's canonical roles — `ball`,
`rim`, `ball_in_basket`, `player`, `number`, `referee` — via the
`BASKETBALL_DETECT_CLASSES` map (see `libs/basketball/config.py`; the default
map already covers both models below). Runtime is onnxruntime CPU only.

---

## 1. Production model — YOLO11n fine-tuned on basketball data

- **Dataset**: Roboflow Universe `basketball-player-detection-3` (workspace
  `roboflow-jvuqo`), 10 classes including `ball`, `rim`, `ball-in-basket`,
  `number`, `referee`, `player`. **Verify the dataset license on its Universe
  page before exporting** (expected CC BY 4.0) and record it here alongside
  the training metrics.
- **Base weights**: `yolo11n.pt` (fallback if training is unstable: YOLO26n).
- **License note**: the ultralytics toolchain is AGPL-3.0 — it is used for
  *training and export only*, on Colab, never at runtime. The exported ONNX
  is run by onnxruntime; no AGPL code ships in this repo or its services.

### Training (Google Colab, GPU runtime)

```python
# 1. Install the toolchain
!pip install ultralytics roboflow

# 2. Download the dataset in YOLO format (Roboflow API key: Universe -> Export)
from roboflow import Roboflow
rf = Roboflow(api_key="<YOUR_ROBOFLOW_API_KEY>")
project = rf.workspace("roboflow-jvuqo").project("basketball-player-detection-3")
dataset = project.version(project.versions()[0].version).download("yolov11")

# 3. Fine-tune YOLO11n. imgsz=960: the ball and rim are small objects.
from ultralytics import YOLO
model = YOLO("yolo11n.pt")
model.train(
    data=f"{dataset.location}/data.yaml",
    epochs=100,
    imgsz=960,
    batch=16,          # reduce if the GPU OOMs at 960
    patience=20,
    name="yolo11n-basketball",
)

# 4. Validate — record mAP50/mAP50-95 per class in this README.
metrics = model.val()
print(metrics.box.maps)
```

### ONNX export (static shape — the wrapper reads the size from the model)

```python
best = YOLO("runs/detect/yolo11n-basketball/weights/best.pt")
best.export(format="onnx", imgsz=960, dynamic=False, simplify=True)
# -> yolo11n-basketball-960.onnx; download it into libs/basketball/models/
```

### INT8 variant (optional, ~2x smaller / often faster on CPU)

```python
# Ultralytics static INT8 quantization, calibrated on the training data:
best.export(format="onnx", imgsz=960, dynamic=False, simplify=True, int8=True,
            data=f"{dataset.location}/data.yaml")
```

Alternatively quantize an existing FP32 ONNX with onnxruntime:

```python
from onnxruntime.quantization import quantize_dynamic, QuantType
quantize_dynamic("yolo11n-basketball-960.onnx",
                 "yolo11n-basketball-960-int8.onnx", weight_type=QuantType.QUInt8)
```

Benchmark both variants (see the benchmark note below) and record the
accuracy delta before switching the default.

### Wiring it up

```bash
export BASKETBALL_DETECT_MODEL_PATH=libs/basketball/models/yolo11n-basketball-960.onnx
```

The dataset's class names are already in the default
`BASKETBALL_DETECT_CLASSES` map (`ball-in-basket` -> `ball_in_basket`, etc.).
If the exported names differ, override the map with JSON:

```bash
export BASKETBALL_DETECT_CLASSES='{"Ball": "ball", "Rim": "rim", "made-basket": "ball_in_basket"}'
```

Record here after training: dataset version + license, training config,
per-class mAP, ONNX sha256 (`sha256sum *.onnx`).

---

## 2. COCO smoke-test fallback (no training needed)

For wiring/integration tests without the fine-tuned model: a stock `yolo11n`
COCO export. COCO has no rim/number/referee classes — the default class map
routes `person` -> `player` and `sports ball` -> `ball`, which is enough to
exercise the full stage end-to-end. **Not for eval numbers.**

Produce it in a *throwaway* venv (ultralytics + torch must never enter
`.venv-basketball`):

```bash
python3 -m venv /tmp/yolo-export-venv
/tmp/yolo-export-venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
/tmp/yolo-export-venv/bin/pip install ultralytics onnx onnxslim onnxruntime
cd /tmp && /tmp/yolo-export-venv/bin/python - <<'EOF'
from ultralytics import YOLO
for imgsz in (640, 960):
    onnx_path = YOLO("yolo11n.pt").export(format="onnx", imgsz=imgsz, dynamic=False, simplify=True, device="cpu")
    print("exported", onnx_path, "at", imgsz)
EOF
# rename/copy the exports into the repo, then delete the venv:
#   libs/basketball/models/yolo11n-coco-640.onnx
#   libs/basketball/models/yolo11n-coco-960.onnx
rm -rf /tmp/yolo-export-venv
```

```bash
export BASKETBALL_DETECT_MODEL_PATH=libs/basketball/models/yolo11n-coco-640.onnx
```

The integration tests in `tests/basketball/test_detect.py`
(`-m integration`) pick up `yolo11n-coco-640.onnx` automatically and are
skipped when it is absent.

### Measured CPU benchmarks (this repo's wrapper, 2026-07-17)

50 random 1280x720 frames, full `detect()` (letterbox + inference + NMS +
un-mapping), dev VM with 8 vCPUs, onnxruntime 1.27.0, ultralytics 8.4.98
export of `yolo11n.pt`:

| Model                  | Input | Threads | ms/frame |
|------------------------|-------|---------|----------|
| yolo11n-coco-640.onnx  | 640   | auto    | 17.9     |
| yolo11n-coco-640.onnx  | 640   | 4       | 15.8     |
| yolo11n-coco-960.onnx  | 960   | auto    | 37.0     |
| yolo11n-coco-960.onnx  | 960   | 4       | 36.8     |

Both comfortably meet the story's ≤ 100 ms/frame acceptance criterion; 960
stays the default (`detect_input_size`) because ball/rim are small objects.

sha256 of the smoke exports produced above (informational — regenerated
exports may differ byte-wise with newer ultralytics/onnx versions):

```
f1ec4fc4c9c0612ec4431f4250cb3d2835c2b843ec5377b50eeb043364a98807  yolo11n-coco-640.onnx
f057bad93ad4986ad74b2b19e2f34b5eb1ce78a8eb6eb102e0e7151cf61cc79b  yolo11n-coco-960.onnx
```
