"""Per-clip stage cache.

Layout (all stages, all epics):

    <workdir>/<clip_id>/<stage>/
        output.json     # the stage's structured result — REQUIRED; a stage is
                        #   "warm" iff this file exists
        *.npz           # optional numpy arrays (frames, detections, embeddings)
        *               # any other stage-private artifacts via ClipCache.path()

``clip_id`` is ``<filename stem>-<first 8 hex chars of the file's sha256>`` so
a re-encoded clip with the same name never reuses stale cache.

JSON is used for structured data, ``.npz`` for arrays. Stages read prior
stages' outputs through the same ClipCache instance (see
``libs.basketball.stages.StageContext``).
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Union

import numpy as np

OUTPUT_JSON = "output.json"

_HASH_CHUNK = 1024 * 1024


def compute_clip_id(clip_path: Union[str, Path]) -> str:
    """``<stem>-<8-char sha256 prefix>`` of the clip file's content."""
    path = Path(clip_path)
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK):
            digest.update(chunk)
    return f"{path.stem}-{digest.hexdigest()[:8]}"


class ClipCache:
    """Read/write access to one clip's stage cache directory tree."""

    def __init__(self, workdir: Union[str, Path], clip_id: str) -> None:
        self.workdir = Path(workdir)
        self.clip_id = clip_id
        self.root = self.workdir / clip_id

    def stage_dir(self, stage: str, create: bool = True) -> Path:
        """Directory for one stage's artifacts (created by default)."""
        path = self.root / stage
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def path(self, stage: str, filename: str) -> Path:
        """Path for an arbitrary stage-private artifact."""
        return self.stage_dir(stage) / filename

    def is_warm(self, stage: str) -> bool:
        """A stage is warm iff its ``output.json`` exists."""
        return (self.root / stage / OUTPUT_JSON).is_file()

    # --- JSON ---

    def write_json(self, stage: str, data: Any, filename: str = OUTPUT_JSON) -> Path:
        path = self.path(stage, filename)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=False), encoding="utf-8")
        tmp.replace(path)  # atomic: never leaves a half-written output.json
        return path

    def read_json(self, stage: str, filename: str = OUTPUT_JSON) -> Any:
        path = self.root / stage / filename
        if not path.is_file():
            raise FileNotFoundError(f"No cached '{filename}' for stage '{stage}' (clip {self.clip_id}): {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # --- Arrays ---

    def write_arrays(self, stage: str, arrays: Dict[str, np.ndarray], filename: str = "arrays.npz") -> Path:
        path = self.path(stage, filename)
        np.savez_compressed(path, **arrays)
        return path

    def read_arrays(self, stage: str, filename: str = "arrays.npz") -> Dict[str, np.ndarray]:
        path = self.root / stage / filename
        if not path.is_file():
            raise FileNotFoundError(f"No cached '{filename}' for stage '{stage}' (clip {self.clip_id}): {path}")
        with np.load(path) as data:
            return {key: data[key] for key in data.files}
