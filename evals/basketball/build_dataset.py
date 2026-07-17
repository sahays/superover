#!/usr/bin/env python3
"""Download the basketball eval clips and record their checksums.

Clip URLs are never committed: the base URL comes from the gitignored
``datasets/sources.local.yaml`` (``base_url`` + ``clips`` list) or from the
``BASKETBALL_CLIPS_BASE_URL`` environment variable (which takes precedence).
Clips land in the gitignored ``datasets/clips/`` directory; each file's
sha256 is written back into the committed ``datasets/manifest.yaml``.

    python evals/basketball/build_dataset.py            # download all clips
    python evals/basketball/build_dataset.py --force    # re-download
    python evals/basketball/build_dataset.py --clips shot_0013 shot_0017

A URL that no longer resolves is reported and skipped; the script continues
with the remaining clips and exits 1 if any download failed.
"""

import argparse
import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
DEFAULT_MANIFEST = DATASETS_DIR / "manifest.yaml"
DEFAULT_SOURCES = DATASETS_DIR / "sources.local.yaml"
DEFAULT_CLIPS_DIR = DATASETS_DIR / "clips"

ENV_BASE_URL = "BASKETBALL_CLIPS_BASE_URL"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources(sources_path: Path, manifest: dict) -> tuple:
    """(base_url, clip names) from env/sources.local.yaml, clips falling back to the manifest."""
    base_url = os.environ.get(ENV_BASE_URL, "").strip()
    clips = []
    if sources_path.is_file():
        data = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or {}
        base_url = base_url or str(data.get("base_url") or "").strip()
        clips = list(data.get("clips") or [])
    if not clips:
        clips = list((manifest.get("clips") or {}).keys())
    return base_url.rstrip("/"), clips


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "super-over-alchemy-basketball-eval/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, tmp.open("wb") as out:
        while chunk := response.read(1024 * 256):
            out.write(chunk)
    tmp.replace(dest)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--clips-dir", type=Path, default=DEFAULT_CLIPS_DIR)
    parser.add_argument("--clips", nargs="*", default=None, help="Subset of clip names (default: all)")
    parser.add_argument("--force", action="store_true", help="Re-download clips that already exist")
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"Error: manifest not found: {args.manifest}", file=sys.stderr)
        return 1
    manifest = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))

    base_url, clip_names = load_sources(args.sources, manifest)
    if not base_url:
        print(
            f"Error: no clip source configured. Create {args.sources} with a 'base_url' "
            f"(and optional 'clips' list) or set {ENV_BASE_URL}.",
            file=sys.stderr,
        )
        return 1
    if args.clips:
        clip_names = args.clips

    args.clips_dir.mkdir(parents=True, exist_ok=True)
    manifest_clips = manifest.setdefault("clips", {})
    downloaded, present, failed = [], [], []

    for name in clip_names:
        filename = f"{name}.mp4"
        dest = args.clips_dir / filename
        url = f"{base_url}/{filename}"
        if dest.is_file() and not args.force:
            present.append(name)
        else:
            try:
                download(url, dest)
                downloaded.append(name)
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                detail = getattr(exc, "code", None) or exc
                print(f"  FAILED  {name}: {url} ({detail}) — continuing", file=sys.stderr)
                failed.append(name)
                continue
        checksum = sha256_of(dest)
        entry = manifest_clips.setdefault(name, {"file": filename, "sha256": None, "events": []})
        entry["sha256"] = checksum
        print(f"  ok      {name}  sha256={checksum[:16]}...  ({dest.stat().st_size} bytes)")

    if downloaded or present:
        args.manifest.write_text(yaml.safe_dump(manifest, sort_keys=False, width=100), encoding="utf-8")
    print(
        f"\nDone: {len(downloaded)} downloaded, {len(present)} already present, "
        f"{len(failed)} failed (of {len(clip_names)})."
        + (f" Checksums written to {args.manifest.name}." if downloaded or present else " Manifest left unchanged.")
    )
    if failed:
        print(f"Failed clips: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
