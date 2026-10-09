"""Download ynov.com pages into data/ with their sidecar manifest.

Usage:
    uv run python -m ingestion.fetch <url> [<url> ...] [--out data/formations]
    uv run python -m ingestion.fetch --sitemap   # every Bachelor, BTS and Mastère page
    uv run python -m ingestion.fetch --common    # admission, alternance, VAE… pages
    uv run python -m ingestion.fetch --rncp      # France Compétences fiches + référentiels

Formation pages go to data/formations, info pages (--common) to data/common, RNCP
fiches and référentiels (--rncp) to data/rncp. --rncp reads the RNCP numbers cited in
already fetched pages and keeps active certifications only.
The HTML is always refreshed; an existing manifest is left untouched so manual
edits survive a re-fetch.
"""

import argparse
import hashlib
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from ingestion.html_loader import (
    is_formation_page,
    is_info_page,
    parse_formation_page,
    parse_info_page,
)
from ingestion.rncp_loader import parse_rncp_page

USER_AGENT = "Mozilla/5.0 (compatible; rag-ynov/0.1)"
DELAY_SECONDS = 1.0
BASE_URL = "https://www.ynov.com"
# Formation detail pages only. The other formation sitemaps list filière/campus index pages.
FORMATION_SITEMAPS = (
    f"{BASE_URL}/sitemap.site_mastere_univers.xml",
    f"{BASE_URL}/sitemap.site_bachelor_univers.xml",
)
# Ynov-wide info linked from every formation page. Left out: /candidature (the form, its
# text is a subset of condition-admission), /faq (an index) and the /faq/* articles (old
# SEO content contradicting current terms, e.g. half-day classes, "frais de dossier").
COMMON_PAGES = (
    "/experience-ynov/condition-admission",
    "/alternance",
    "/experience-ynov/centre-de-formation-des-apprentis",
    "/experience-ynov/vae-ynov",
    "/handicap",
    "/guide-parents-scolarite-enfant",
    "/experience-ynov/certification-qualiopi",
    "/campus",
)


RNCP_URL = "https://www.francecompetences.fr/recherche/rncp/{}/"
RNCP_BASE = "https://www.francecompetences.fr"


RETRIES = 4


def _get(url: str) -> httpx.Response:
    """GET with retries: francecompetences.fr often drops connections mid-response."""
    for attempt in range(RETRIES):
        try:
            resp = httpx.get(
                url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60
            )
            resp.raise_for_status()
            return resp
        except httpx.TransportError:
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


def _write_manifest(path: Path, manifest: dict) -> None:
    if not path.exists():
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)


def cited_rncp_numbers(*dirs: Path) -> list[str]:
    """RNCP numbers linked to France Compétences from the fetched HTML pages."""
    pattern = re.compile(r"francecompetences\.fr(?:/|%2F)recherche(?:/|%2F)rncp(?:/|%2F)(\d+)")
    numbers: set[str] = set()
    for d in dirs:
        for path in d.glob("*.html"):
            numbers.update(pattern.findall(path.read_text(encoding="utf-8")))
    return sorted(numbers)


def fetch_rncp(number: str, out_dir: Path, data_dir: Path) -> str:
    """Fetch one fiche; if active, save it and its référentiel(s). Returns a status line."""
    slug = f"rncp-{number}"
    html = _get(RNCP_URL.format(number)).text
    fiche = parse_rncp_page(html)
    if fiche["status"] != "Active":
        return f"SKIPPED RNCP{number}: état « {fiche['status'] or 'inconnu'} »"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{slug}.html").write_text(html, encoding="utf-8")
    common = {
        "program": None,
        "year": None,
        "title": f"{fiche['rncp']} — {fiche['title']}",
        "language": "fr",
    }
    _write_manifest(
        out_dir / f"{slug}.manifest.yml",
        {
            "source": f"{slug}.html",
            "doc_type": "fiche_rncp",
            **common,
            "rncp": number,
            "extra": {
                "url": RNCP_URL.format(number),
                "level": fiche["level"],
                "expiry": fiche["expiry"],
            },
        },
    )

    # A référentiel already in data/ (e.g. added by hand) is not downloaded twice.
    known = {hashlib.sha256(p.read_bytes()).hexdigest() for p in data_dir.rglob("*.pdf")}
    saved, duplicates = 0, 0
    for i, href in enumerate(fiche["referentiel_urls"]):
        name = f"{slug}-referentiel" + (f"-{i + 1}" if i else "")
        if (out_dir / f"{name}.pdf").exists():  # resuming an interrupted run
            saved += 1
            continue
        time.sleep(DELAY_SECONDS)
        pdf = _get(RNCP_BASE + href).content
        if not pdf.startswith(b"%PDF") or hashlib.sha256(pdf).hexdigest() in known:
            duplicates += 1
            continue
        (out_dir / f"{name}.pdf").write_bytes(pdf)
        _write_manifest(
            out_dir / f"{name}.manifest.yml",
            {
                "source": f"{name}.pdf",
                "doc_type": "referentiel",
                **common,
                "rncp": number,
                "extra": {"url": RNCP_BASE + href, "level": fiche["level"]},
            },
        )
        saved += 1
    return (
        f"RNCP{number} active: fiche + {saved} référentiel(s)"
        + (f", {duplicates} ignoré(s) (doublon ou non-PDF)" if duplicates else "")
        + ("" if fiche["referentiel_urls"] else ", pas de référentiel publié")
    )


def sitemap_urls() -> list[str]:
    urls: list[str] = []
    for sitemap in FORMATION_SITEMAPS:
        resp = httpx.get(sitemap, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        urls += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text)
    return sorted(set(urls))


def build_manifest(url: str, filename: str, html: str) -> dict:
    path_parts = urlparse(url).path.strip("/").split("/")
    if is_info_page(html):
        page = parse_info_page(html)
        modified = re.search(r"(\d{4})$", page["last_modified"] or "")
        return {
            "source": filename,
            "doc_type": "info",
            "program": None,
            "year": int(modified.group(1)) if modified else None,
            "title": page["title"],
            "language": "fr",
            "extra": {"url": url},
        }

    page = parse_formation_page(html)
    key_info = dict(page["sections"]).get("Infos clés", "")
    year = re.search(r"Prochaine rentrée : \S+ (\d{4})", key_info)
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
    html = _get(url).text
    if not (is_formation_page(html) or is_info_page(html)):
        raise ValueError(f"Not a ynov.com formation or info page: {url}")

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
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--sitemap", action="store_true", help="fetch all formation pages")
    parser.add_argument("--common", action="store_true", help="fetch Ynov-wide info pages")
    parser.add_argument("--out", type=Path, default=Path("data/formations"))
    parser.add_argument("--common-out", type=Path, default=Path("data/common"))
    parser.add_argument("--rncp", action="store_true", help="fetch active RNCP fiches")
    parser.add_argument("--rncp-out", type=Path, default=Path("data/rncp"))
    args = parser.parse_args()

    if args.rncp:
        numbers = cited_rncp_numbers(args.out, args.common_out)
        print(f"{len(numbers)} RNCP numbers cited")
        for i, number in enumerate(numbers):
            if i:
                time.sleep(DELAY_SECONDS)
            try:
                print(fetch_rncp(number, args.rncp_out, Path("data")))
            except httpx.HTTPError as exc:
                print(f"SKIPPED RNCP{number}: {exc}")
        if not (args.urls or args.sitemap or args.common):
            return

    jobs = [(url, args.out) for url in args.urls]
    if args.sitemap:
        jobs += [(url, args.out) for url in sitemap_urls()]
    if args.common:
        jobs += [(BASE_URL + path, args.common_out) for path in COMMON_PAGES]
    if not jobs:
        parser.error("give at least one URL, --sitemap or --common")

    failures = []
    for i, (url, out_dir) in enumerate(jobs):
        if i:
            time.sleep(DELAY_SECONDS)
        try:
            print(fetch(url, out_dir))
        except (httpx.HTTPError, ValueError) as exc:
            failures.append(url)
            print(f"SKIPPED {url}: {exc}")
    print(f"{len(jobs) - len(failures)}/{len(jobs)} pages fetched")


if __name__ == "__main__":
    main()
