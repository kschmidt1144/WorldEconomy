"""Download layer: polite, cached, manifest-tracked.

Every raw artifact lands in data/raw/<source>/ with an entry in that dir's
_manifest.json (url, fetched_at, sha256, bytes). A file is only re-downloaded
when --force is passed or the recorded URL changed, so `econ refresh` is
idempotent and a clean clone reproduces the exact raw layer.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import RAW

USER_AGENT = "econlab/0.1 (personal research; kschmidt1144@gmail.com)"


def _manifest_path(source: str) -> Path:
    return RAW / source / "_manifest.json"


def _load_manifest(source: str) -> dict:
    p = _manifest_path(source)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _save_manifest(source: str, manifest: dict) -> None:
    p = _manifest_path(source)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def _record(source: str, filename: str, url: str, sha256: str, nbytes: int) -> None:
    manifest = _load_manifest(source)
    manifest[filename] = {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256,
        "bytes": nbytes,
    }
    _save_manifest(source, manifest)


def download(
    source: str,
    url: str,
    filename: str | None = None,
    *,
    force: bool = False,
    headers: dict | None = None,
    timeout: int = 600,
) -> Path:
    """Stream `url` into data/raw/<source>/<filename>; skip if already fetched from same url."""
    filename = filename or url.rsplit("/", 1)[-1].split("?")[0]
    dest_dir = RAW / source
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    manifest = _load_manifest(source)
    if dest.exists() and not force and manifest.get(filename, {}).get("url") == url:
        return dest

    h = {"User-Agent": USER_AGENT, **(headers or {})}
    tmp = dest.with_name(dest.name + ".part")
    sha = hashlib.sha256()
    with requests.get(url, headers=h, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                sha.update(chunk)
    tmp.replace(dest)
    _record(source, filename, url, sha.hexdigest(), dest.stat().st_size)
    return dest


def download_first(
    source: str,
    urls: list[str],
    filename: str,
    *,
    force: bool = False,
    headers: dict | None = None,
) -> Path:
    """Try candidate URLs in order (sources whose hosting moves around)."""
    dest = RAW / source / filename
    manifest = _load_manifest(source)
    if dest.exists() and not force and manifest.get(filename, {}).get("url") in urls:
        return dest
    last_err: Exception | None = None
    for url in urls:
        try:
            return download(source, url, filename, force=force, headers=headers)
        except Exception as e:  # try next candidate
            last_err = e
    raise RuntimeError(f"{source}: all candidate URLs failed for {filename}") from last_err


def save_bytes(source: str, filename: str, data: bytes, url: str) -> Path:
    """For connectors that assemble raw data themselves (paginated APIs):
    persist the assembled artifact into the raw layer with a manifest entry."""
    dest_dir = RAW / source
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    dest.write_bytes(data)
    _record(source, filename, url, hashlib.sha256(data).hexdigest(), len(data))
    return dest


def get_text(url: str, *, timeout: int = 120) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return r.text


def get_json(url: str, *, params: dict | None = None, timeout: int = 120) -> dict:
    r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    return r.json()
