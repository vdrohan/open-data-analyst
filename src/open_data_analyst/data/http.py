"""Download helper: identifies itself, retries, and records where each raw file came from."""

import hashlib
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

USER_AGENT = "open-data-analyst/0.1 (personal research; github.com/vdrohan/open-data-analyst)"


def raw_dir() -> Path:
    """Where raw downloads are cached (gitignored). Override with OPEN_DATA_RAW_DIR."""
    return Path(os.environ.get("OPEN_DATA_RAW_DIR", "data/raw"))


@dataclass(frozen=True)
class Fetched:
    """A raw file on disk plus the provenance needed to cite it."""

    source: str
    url: str
    path: Path
    sha256: str
    fetched_at: datetime


def get_bytes(url: str, params: dict[str, str] | None = None, retries: int = 3) -> bytes:
    """GET a URL and return the body, retrying transient failures with backoff."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(2 * 2**attempt)
    raise AssertionError("unreachable")


def download(source: str, url: str, dest: Path) -> Fetched:
    """Download `url` to `dest` and return its provenance."""
    body = get_bytes(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return Fetched(source, url, dest, hashlib.sha256(body).hexdigest(), datetime.now(UTC))
