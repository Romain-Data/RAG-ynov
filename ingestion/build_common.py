"""Build the "informations communes" document from scraped formation pages.

The HTML loader drops the boilerplate sections repeated on every formation page
(GENERIC_SECTIONS) and the shared Tarifs lines. This script gathers them once:

- per section, the majority wording for each diploma type (BTS, Bachelor, Mastère),
  merged when the types share the same wording;
- formations whose wording differs from their type's get a "particularité" section,
  so nothing the loader dropped is lost;
- the shared payment / alternance / formation continue terms from Tarifs;
- the list of campuses, from the map of the /campus page (data/common/campus.html), which
  only lists city names with no sentence saying that they are the campuses.

Usage:
    uv run python -m ingestion.build_common [--formations data/formations] [--out data/common]
"""

import argparse
import collections
import difflib
import functools
from datetime import date
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from ingestion.html_loader import (
    TARIF_BOILERPLATE_HEADERS,
    TARIF_BOILERPLATE_PREFIXES,
    _is_generic,
    _normalize_title,
    parse_formation_page,
)

SIMILARITY_THRESHOLD = 0.9
TITLE = "Informations communes à toutes les formations Ynov"
OUT_NAME = "informations-communes-formations"
DIPLOMA_TYPES = {"BTS": "BTS", "Bachelor": "Bachelors", "Mastère": "Mastères"}


def _similar(a: str, b: str) -> bool:
    if a == b:
        return True
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    # quick_ratio() is a cheap upper bound of ratio(): skip the expensive call when it fails
    return matcher.quick_ratio() >= SIMILARITY_THRESHOLD and matcher.ratio() >= SIMILARITY_THRESHOLD


@functools.cache
def _similar_cached(a: str, b: str) -> bool:
    return _similar(a, b)


def _majority(bodies: list[str]) -> str:
    """The wording most other bodies are similar to (exact duplicates count first)."""
    counts = collections.Counter(bodies)
    return max(counts, key=lambda b: sum(n for o, n in counts.items() if _similar_cached(b, o)))


def _diploma_type(formation: str) -> str | None:
    first = formation.split(" ", 1)[0]
    return first if first in DIPLOMA_TYPES else None


def _tarif_boilerplate(tarifs: str) -> list[str]:
    lines = []
    for line in tarifs.splitlines():
        norm = _normalize_title(line)
        if norm in TARIF_BOILERPLATE_HEADERS:
            lines.append(f"### {line}")
        elif norm.startswith(TARIF_BOILERPLATE_PREFIXES):
            lines.append(line)
    return lines


def _campus_section(campus_html: str) -> list[str]:
    """The "Où sont les campus ?" section, from the map pins of the /campus page."""
    soup = BeautifulSoup(campus_html, "html.parser")
    cities = [str(a["aria-label"]) for a in soup.select("a.CampusMap-Pin[aria-label]")]
    if not cities:
        return []
    return [
        "",
        "## Où sont les campus d'Ynov ? Liste des villes",
        f"Ynov compte {len(cities)} campus en France, situés à : {', '.join(cities)}. "
        "Ynov Connect est le campus 100 % en ligne et en alternance.",
    ]


def build(formations_dir: Path, campus_html: str | None = None) -> str:
    # generic title key -> list of (formation, diploma type, display title, body)
    sections: dict[str, list[tuple[str, str | None, str, str]]] = collections.defaultdict(list)
    tarif_lines: list[list[str]] = []

    for path in sorted(formations_dir.glob("*.html")):
        page = parse_formation_page(path.read_text(encoding="utf-8"), keep_generic=True)
        dtype = _diploma_type(page["formation"])
        for title, body in page["sections"]:
            if _is_generic(title):
                key = _normalize_title(title)
                sections[key].append((page["formation"], dtype, title, body))
            elif title == "Tarifs":
                tarif_lines.append(_tarif_boilerplate(body))

    out = [f"# {TITLE}", ""]
    out.append(
        "Ces informations s'appliquent à l'ensemble des formations Ynov (BTS, Bachelors, "
        "Mastères), sauf mention contraire. Les tarifs propres à chaque formation figurent "
        "sur sa fiche."
    )

    if campus_html:
        out += _campus_section(campus_html)

    if tarif_lines:
        common = max(collections.Counter(map(tuple, tarif_lines)).items(), key=lambda kv: kv[1])
        out += ["", "## Modalités de paiement et prise en charge des frais", *common[0]]

    for entries in sections.values():
        display = collections.Counter(t for _, _, t, _ in entries).most_common(1)[0][0]
        global_ref = _majority([b for *_, b in entries])

        # Majority wording per diploma type, then merge types sharing the same wording.
        by_type: dict[str, str] = {}
        for dtype in DIPLOMA_TYPES:
            bodies = [b for _, t, _, b in entries if t == dtype]
            if bodies:
                by_type[dtype] = _majority(bodies)
        groups: list[tuple[list[str], str]] = []
        for dtype, body in by_type.items():
            for types, ref in groups:
                if _similar(body, ref):
                    types.append(dtype)
                    break
            else:
                groups.append(([dtype], body))

        for types, body in groups:
            scope = ", ".join(DIPLOMA_TYPES[t] for t in types)
            heading = display if len(groups) == 1 else f"{display} ({scope})"
            out += ["", f"## {heading}", f"S'applique aux formations : {scope}.", body]

        for formation, dtype, _, body in entries:
            ref = by_type.get(dtype, global_ref) if dtype else global_ref
            if not _similar(body, ref):
                out += ["", f"## {display} — particularité : {formation}", body]

    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--formations", type=Path, default=Path("data/formations"))
    parser.add_argument("--out", type=Path, default=Path("data/common"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    md_path = args.out / f"{OUT_NAME}.md"
    campus_path = args.out / "campus.html"
    campus_html = campus_path.read_text(encoding="utf-8") if campus_path.exists() else None
    md_path.write_text(build(args.formations, campus_html), encoding="utf-8")
    manifest = {
        "source": md_path.name,
        "doc_type": "info",
        "program": None,
        "year": date.today().year,
        "title": TITLE,
        "language": "fr",
        "extra": {"generated_from": str(args.formations)},
    }
    with (args.out / f"{OUT_NAME}.manifest.yml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f, allow_unicode=True, sort_keys=False)
    print(md_path)


if __name__ == "__main__":
    main()
