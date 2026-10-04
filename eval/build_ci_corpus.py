"""Build the small frozen corpus of the CI (eval/ci_corpus/) from the full one (data/).

The full corpus is not in git; the CI needs one to run eval.retrieval. It holds the pages the
reference questions cite (eval/questions.yaml), plus a few other formations and RNCP fiches
so that the search is not trivial. Scripts, styles and SVG are stripped from the HTML (the
loaders ignore them): the script checks that every file gives exactly the same documents
before and after, so the retrieval results do not depend on the stripping.

The pages belong to ynov.com and francecompetences.fr, public pages kept here for teaching
purposes, with their source URL in the manifests.

Usage:
    uv run python -m eval.build_ci_corpus [--data data] [--out eval/ci_corpus] [--extra 8]
"""

import argparse
import shutil
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from ingestion.loaders import load_file

QUESTIONS = Path(__file__).parent / "questions.yaml"
STRIPPED_TAGS = ("script", "style", "svg", "noscript", "link", "template", "iframe")
# Folders of data/ that hold documents: `data/programs` (hand-added, excluded) is left out
FOLDERS = ("formations", "common", "rncp")


def cited_sources() -> set[str]:
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    questions = questions["questions"] if isinstance(questions, dict) else questions
    return {e["source"] for q in questions for e in q.get("expect", []) if "source" in e}


def strip_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(STRIPPED_TAGS):
        tag.decompose()
    return str(soup)


def pick_extra(data: Path, folder: str, cited: set[str], count: int) -> list[str]:
    """Evenly spread files of `folder` that no question cites (deterministic)."""
    names = sorted(p.name for p in (data / folder).glob("*.html") if p.name not in cited)
    if not names or count <= 0:
        return []
    step = max(len(names) // count, 1)
    return names[::step][:count]


def copy_source(src: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest = src.with_name(src.stem + ".manifest.yml")
    shutil.copy(manifest, dest_dir / manifest.name)
    dest = dest_dir / src.name
    if src.suffix == ".html":
        dest.write_text(strip_html(src.read_text(encoding="utf-8")), encoding="utf-8")
    else:
        shutil.copy(src, dest)
    before, after = load_file(src), load_file(dest)
    if before != after:
        raise SystemExit(f"{src.name}: the stripped file gives other documents, not kept")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("eval/ci_corpus"))
    parser.add_argument("--extra", type=int, default=8, help="other formations to add")
    parser.add_argument("--extra-rncp", type=int, default=3, help="other RNCP fiches to add")
    args = parser.parse_args()

    cited = cited_sources()
    wanted: dict[str, set[str]] = {f: set() for f in FOLDERS}
    for folder in FOLDERS:
        for path in (args.data / folder).iterdir():
            if path.name in cited:
                wanted[folder].add(path.name)
    missing = cited - {n for names in wanted.values() for n in names}
    if missing:
        raise SystemExit(f"Cited sources not found in {args.data}: {sorted(missing)}")
    wanted["formations"].update(pick_extra(args.data, "formations", cited, args.extra))
    wanted["rncp"].update(pick_extra(args.data, "rncp", cited, args.extra_rncp))

    if args.out.exists():
        shutil.rmtree(args.out)
    for folder, names in wanted.items():
        for name in sorted(names):
            copy_source(args.data / folder / name, args.out / folder)
    files = [p for p in args.out.rglob("*") if p.is_file()]
    size = sum(p.stat().st_size for p in files) / 1e6
    print(f"{len(files) // 2} sources, {size:.1f} MB in {args.out}")


if __name__ == "__main__":
    main()
