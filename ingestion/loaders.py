"""Document loaders for various formats."""
from pathlib import Path

import yaml
from pypdf import PdfReader


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


def load_file(path: Path) -> list[dict]:
    """Dispatch to appropriate loader by extension."""
    suffix = path.suffix.lower()
    if suffix == ".md":
        return load_markdown(path)
    elif suffix == ".pdf":
        return load_pdf(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def load_directory(dir_path: Path) -> list[dict]:
    """Load all supported files in a directory."""
    all_chunks = []
    for path in dir_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".md", ".pdf"):
            all_chunks.extend(load_file(path))
    return all_chunks
