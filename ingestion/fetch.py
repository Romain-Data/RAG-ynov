"""Download ynov.com formation pages into data/ with their sidecar manifest.

Usage:
    uv run python -m ingestion.fetch <url> [<url> ...] [--out data/formations]

The HTML is always refreshed; an existing manifest is left untouched so manual
edits survive a re-fetch.
"""
import argparse
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from ingestion.html_loader import is_formation_page, parse_formation_page

USER_AGENT = "Mozilla/5.0 (compatible; rag-ynov/0.1)"
DELAY_SECONDS = 1.0


def build_manifest(url: str, filename: str, html: str) -> dict:
    page = parse_formation_page(html)
    key_info = dict(page["sections"]).get("Infos clés", "")
    year = re.search(r"Prochaine rentrée : \S+ (\d{4})", key_info)
    path_parts = urlparse(url).path.strip("/").split("/")
    return {
        "source": filename,
        "doc_type": "formation",
        "program": path_parts[-1],
        "year": int(year.group(1)) if year else None,
        "title": page["formation"],
        "language": "fr",
        "extra": {
            "url": url,
            "filiere": path_parts[-2] if len(path_parts) >= 2 else None,
        },
    }


def fetch(url: str, out_dir: Path) -> Path:
    resp = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    html = resp.text
    if not is_formation_page(html):
        raise ValueError(f"Not a ynov.com formation page: {url}")

    slug = urlparse(url).path.strip("/").split("/")[-1]
    html_path = out_dir / f"{slug}.html"
    manifest_path = out_dir / f"{slug}.manifest.yml"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    if not manifest_path.exists():
        with manifest_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                build_manifest(url, html_path.name, html), f, allow_unicode=True, sort_keys=False
            )
    return html_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--out", type=Path, default=Path("data/formations"))
    args = parser.parse_args()
    for i, url in enumerate(args.urls):
        if i:
            time.sleep(DELAY_SECONDS)
        print(fetch(url, args.out))


if __name__ == "__main__":
    main()
