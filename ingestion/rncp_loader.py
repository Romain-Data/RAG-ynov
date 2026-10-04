"""HTML parsing for France Compétences RNCP fiches (francecompetences.fr/recherche/rncp/N/).

A fiche has a header (title, état, "L'essentiel": niveau, NSF, échéance) and accordions
(résumé, blocs de compétences, emplois, voies d'accès…) split by h3 headings. Each h3
becomes one section, tables are flattened to "column: value" lines.
"""

import re

from bs4 import BeautifulSoup, Tag

from ingestion.html_loader import _clean, _to_text

# Sections that are navigation or a bare link, not content.
SKIPPED_SECTIONS = {
    "Lien internet vers le descriptif de la certification",
    "Référentiel d'activité, de compétences et d'évaluation",
}
# Equivalence tables and legal references: little value for a student, and the
# equivalence tables repeat other certifications' bloc titles, so they crowded out the
# actual skill blocs in retrieval. Matched as title prefixes.
SKIPPED_SECTION_PREFIXES = (
    "Certifications professionnelles enregistrées au RNCP en correspondance",
    "Anciennes versions de la certification professionnelle",
    "Référence des arrêtés et décisions",
    "Date du dernier Journal Officiel",
)


# "Compétences attestées" usually restates the blocs' skill lists word for word: dropped
# when at least this share of its lines already appears in the blocs.
ATTESTED_OVERLAP_THRESHOLD = 0.9
_BLOC_TITLE = re.compile(r"^RNCP\d+BC\d+")


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _restates_blocs(attested: str, sections: list[tuple[str, str]]) -> bool:
    blocs = _norm(" ".join(b for t, b in sections if _BLOC_TITLE.match(t)))
    lines = [_norm(line) for line in attested.splitlines() if len(line) > 60]
    if not lines or not blocs:
        return False
    found = sum(line[:120] in blocs for line in lines)
    return found / len(lines) >= ATTESTED_OVERLAP_THRESHOLD


def is_rncp_page(html: str) -> bool:
    return "fcpt-certification" in html


def _table_to_text(table: Tag) -> str:
    headers = [_clean(th.get_text(" ")) for th in table.select("thead th")]
    lines = []
    for row in table.select("tbody tr"):
        cells = [_to_text(td) for td in row.find_all(["td", "th"])]
        if len(headers) == len(cells) and len(headers) > 1:
            lines.append("\n".join(f"{h} : {c}" for h, c in zip(headers, cells, strict=True) if c))
        else:
            lines.append(" | ".join(c for c in cells if c))
        lines.append("")
    return "\n".join(lines).strip()


def _section_text(heading: Tag) -> str:
    """Content after an h3 up to the next h3 within the same accordion.

    The h3 sits in a div with its text; tables (blocs de compétences) follow that div.
    """
    parts: list[Tag] = list(heading.find_next_siblings())
    for sibling in heading.parent.find_next_siblings() if heading.parent else []:
        if sibling.name == "h3" or sibling.find("h3"):
            break
        parts.append(sibling)
    texts = []
    for el in parts:
        tables = [el] if el.name == "table" else el.find_all("table")
        texts += [_table_to_text(t) for t in tables] if tables else [_to_text(el)]
    return "\n".join(t for t in texts if t).strip()


def parse_rncp_page(html: str) -> dict:
    """Returns {"rncp", "title", "status", "level", "expiry", "sections", "referentiel_urls"}."""
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("h2.title--page--generic")
    title = _clean(title_el.get_text(" ")) if title_el else ""
    status = ""
    for tag in soup.select(".tag--fcpt-certification"):  # one tag for the number, one for état
        label = tag.select_one(".tag--fcpt-certification__title")
        value = tag.select_one(".tag--fcpt-certification__status")
        if label and value and _clean(label.get_text(" ")).lower().startswith("etat"):
            status = _clean(value.get_text(" "))
    number = re.search(r"\bRNCP\s?(\d{4,6})\b", soup.get_text(" "))
    rncp = f"RNCP{number.group(1)}" if number else ""

    essentials = {}
    for line in soup.select(".list--fcpt-certification--essential--desktop__line"):
        label = line.select_one(".list--fcpt-certification--essential--desktop__line__title")
        value = line.select_one(".list--fcpt-certification--essential--desktop__line__text")
        if label and value:
            essentials[_clean(label.get_text(" "))] = _clean(value.get_text(" "))

    referentiel_urls = [
        a["href"] for a in soup.select('a[href*="/wp-json/api/v1/activity/export/"]')
    ]

    key_info = [f"Titre : {title}", f"Numéro : {rncp}", f"État : {status}"]
    key_info += [f"{k} : {v}" for k, v in essentials.items()]
    sections = [("Infos clés", "\n".join(key_info))]

    for accordion in soup.select(".accordion--fcpt-certification"):
        button = accordion.select_one(".accordion--fcpt-certification__button")
        content = accordion.select_one(".accordion--fcpt-certification__content")
        if not button or not content:
            continue
        accordion_title = _clean(button.get_text(" "))
        headings = content.find_all("h3")
        if not headings:
            tables = content.find_all("table")
            text = "\n".join(_table_to_text(t) for t in tables) if tables else _to_text(content)
            if text:
                sections.append((accordion_title, text))
            continue
        for h in headings:
            section_title = _clean(h.get_text(" ")).rstrip(" :")
            if section_title in SKIPPED_SECTIONS or section_title.startswith(
                SKIPPED_SECTION_PREFIXES
            ):
                continue
            text = _section_text(h)
            if text and text != "-":
                sections.append((section_title, text))

    attested = dict(sections).get("Compétences attestées", "")
    if attested and _restates_blocs(attested, sections):
        sections = [(t, b) for t, b in sections if t != "Compétences attestées"]

    level = essentials.get("Nomenclature du niveau de qualification", "")
    return {
        "rncp": rncp,
        "title": title,
        "status": status,
        "level": level,
        "expiry": essentials.get("Date d’échéance de l’enregistrement"),
        "sections": sections,
        "referentiel_urls": referentiel_urls,
    }
