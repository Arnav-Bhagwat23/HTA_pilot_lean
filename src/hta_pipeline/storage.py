from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from urllib.parse import urlparse

from .config import project_root
from .models import RetrievalRun


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return cleaned.strip("-") or "query"


def results_dir() -> Path:
    path = project_root() / "results"
    path.mkdir(parents=True, exist_ok=True)
    return path


def downloads_dir() -> Path:
    path = project_root() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_download_path(country: str, source_id: str, url: str) -> Path:
    parsed = urlparse(url)
    filename = Path(parsed.path).name or "document.pdf"
    if "." not in filename:
        filename = f"{filename}.pdf"
    if len(filename) > 120:
        stem = Path(filename).stem[:80].rstrip("-_.")
        extension = Path(filename).suffix or ".pdf"
        digest = sha1(filename.encode("utf-8")).hexdigest()[:10]
        filename = f"{stem}-{digest}{extension}"
    return downloads_dir() / slugify(country) / slugify(source_id) / filename


def save_manifest(run: RetrievalRun) -> Path:
    timestamp = run.generated_at.replace(":", "-")
    filename = (
        f"{slugify(run.request.country)}__{slugify(run.request.product_name)}__{timestamp}.json"
    )
    destination = results_dir() / filename
    destination.write_text(json.dumps(asdict(run), indent=2), encoding="utf-8")
    return destination
