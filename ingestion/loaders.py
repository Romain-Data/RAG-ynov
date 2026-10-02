"""Document loaders for various formats."""
from pathlib import Path

import yaml
from pypdf import PdfReader

from ingestion.html_loader import is_formation_page, parse_formation_page, parse_generic_page

HTML_SUFFIXES = (".html", ".htm")
SUPPORTED_SUFFIXES = (".md", ".pdf", *HTML_SUFFIXES)


def _load_manifest(path: Path) -> dict:
    """Load sidecar manifest.yml if it exists, else raise."""
    manifest_path = path.with_name(path.stem + ".manifest.yml")
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found for {path.name}: expected {manifest_path}")
    with manifest_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _merge_metadata(base: dict, manifest: dict) -> dict:
    """Merge loader metadata (source, page) with manifest metadata.
    Manifest wins on conflicts (source of truth).
    """
    merged = base.copy()
    merged.update(manifest)
    extra = merged.pop("extra", None)
    if isinstance(extra, dict):
        merged.update(extra)
    return merged


def load_markdown(path: Path) -> list[dict]:
    """Load a markdown file, return list of {text, metadata}."""
    text = path.read_text(encoding="utf-8")
    manifest = _load_manifest(path)
    base_meta = {"source": path.name, "page": 1, "section": None}
    metadata = _merge_metadata(base_meta, manifest)
    return [{
        "text": text,
        "metadata": metadata,
    }]


def load_pdf(path: Path) -> list[dict]:
    """Load a PDF, return list of {text, metadata} per page."""
    manifest = _load_manifest(path)
    reader = PdfReader(path)
    chunks = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            base_meta = {"source": path.name, "page": i + 1, "section": None}
            metadata = _merge_metadata(base_meta, manifest)
            chunks.append({
                "text": text,
                "metadata": metadata,
            })
    return chunks


def load_html(path: Path) -> list[dict]:
    """Load an HTML page, return list of {text, metadata, prefix}.

    ynov.com formation pages yield one document per section, with boilerplate removed
    (see ingestion.html_loader). `prefix` ("<formation> — <section>") is prepended to
    every chunk so chunks from the middle of a section still say what they are about.
    Other HTML falls back to a single document of the main content.
    """
    html = path.read_text(encoding="utf-8")
    manifest = _load_manifest(path)

    if not is_formation_page(html):
        base_meta = {"source": path.name, "page": 1, "section": None}
        return [{
            "text": parse_generic_page(html),
            "metadata": _merge_metadata(base_meta, manifest),
        }]

    page = parse_formation_page(html)
    docs = []
    for title, body in page["sections"]:
        base_meta = {
            "source": path.name,
            "page": 1,
            "section": title,
            "formation": page["formation"],
            "campuses": page["campuses"],
            "last_modified": page["last_modified"],
        }
        docs.append({
            "text": body,
            "metadata": _merge_metadata(base_meta, manifest),
            "prefix": f"{page['formation']} — {title}\n",
        })
    return docs


def load_file(path: Path) -> list[dict]:
    """Dispatch to appropriate loader by extension."""
    suffix = path.suffix.lower()
    if suffix == ".md":
        return load_markdown(path)
    elif suffix == ".pdf":
        return load_pdf(path)
    elif suffix in HTML_SUFFIXES:
        return load_html(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def load_directory(dir_path: Path) -> list[dict]:
    """Load all supported files in a directory."""
    all_chunks = []
    for path in dir_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            all_chunks.extend(load_file(path))
    return all_chunks
