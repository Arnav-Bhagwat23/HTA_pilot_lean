from __future__ import annotations

from pathlib import Path

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0 Safari/537.36"
    )
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def download_file(session: requests.Session, url: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with session.get(url, timeout=60, stream=True) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)

    return destination
