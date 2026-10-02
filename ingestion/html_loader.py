"""HTML parsing for scraped ynov.com formation pages.

A formation page is a stack of CMS blocks (`div.landing-page__block.block_*`).
We keep the blocks that describe *this* formation and drop navigation, CTAs and
boilerplate repeated on every formation page, so the index is not flooded with
near-identical chunks. Each kept section becomes one document, so chunks never
straddle two sections and carry their section title in metadata.
"""
import re
import unicodedata

from bs4 import BeautifulSoup, NavigableString, Tag

# Blocks that are navigation, marketing or group-wide (identical on every page).
# block_reinsurance = "14 campus, 9 000 étudiants…" — group figures, not this formation's.
EXCLUDED_BLOCKS = {
    "block_anchor_menu",
    "block_slider_student_project",
    "block_reinsurance",
    "block_bridge",
    "block_jpo_banner",
}

# Accordion sections whose content is Ynov-wide boilerplate (>= 80 % identical across
# the 42 formation pages). Matched on the normalized title: lowercase, no accents, straight
# quotes, leading article dropped ("Les modalités…" == "Modalités…").
# Tarifs is deliberately NOT here: the wording is shared but the prices differ.
GENERIC_SECTIONS = {
    "processus d'admission",
    "voie d'acces",
    "methodes mobilisees",
    "modalites d'evaluation continue",
    "modalites d'evaluation certificative",
    "modalites d'evaluation certificatives",
    "modalites d'evaluations certificatives",
    "passerelles",
    "accessibilite aux personnes en situation de handicap",
}

_BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "section"}
_NOISE_TAGS = ["script", "style", "svg", "img", "button", "noscript", "form", "iframe"]


def _normalize_title(title: str) -> str:
    title = unicodedata.normalize("NFKD", title.replace("’", "'"))
    title = "".join(c for c in title if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", title).strip().lower()


def _is_generic(title: str) -> bool:
    return re.sub(r"^(les|le|la) ", "", _normalize_title(title)) in GENERIC_SECTIONS


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u200b", "").replace("\xa0", " ")).strip()


def _to_text(el: Tag) -> str:
    """Flatten an element to text, one line per block element, '- ' for list items.

    Mutates `el`: callers pass elements from a soup parsed for this load only.
    """
    for noise in el.find_all(_NOISE_TAGS):
        noise.decompose()
    for br in el.find_all("br"):
        br.replace_with(NavigableString("\n"))
    for block in el.find_all(_BLOCK_TAGS):
        if block.name == "li":
            block.insert(0, NavigableString("\n- "))
        else:
            block.insert(0, NavigableString("\n"))
        block.append(NavigableString("\n"))
    lines = (_clean(line) for line in el.get_text("").split("\n"))
    return "\n".join(line for line in lines if line and not re.fullmatch(r"-+", line))


def _block_type(block: Tag) -> str:
    return next((c for c in block.get_attribute_list("class") if c and c.startswith("block_")), "")


def _formation_name(soup: Tag) -> str:
    sticky_title = soup.select_one(".block_sticky_formation h3")
    if sticky_title:
        return _clean(sticky_title.get_text(" "))
    h1 = soup.find("h1")
    return _clean(h1.get_text(" ")) if h1 else ""


def _split_campuses(raw: str) -> list[str]:
    parts = re.split(r",|\bet\b", raw)
    return [p.strip() for p in parts if p.strip()]


def _key_info(soup: Tag) -> tuple[str, list[str]]:
    """Hero + recap card (rentrée, durée, niveau, campus). Returns (text, campuses)."""
    lines = []
    hero = soup.select_one(".HeroFormation-Content")
    if hero:
        for cls in ("HeroFormation-Subtitle", "HeroFormation-Rncp"):
            el = hero.find(class_=cls)
            if el:
                lines.append(_clean(el.get_text(" ")))

    campuses: list[str] = []
    online = False
    # The recap card is rendered twice (mobile + desktop): read the first one only.
    card = soup.select_one(".block_sticky_formation .Bloc-Info")
    if card:
        for label in card.find_all(class_="StickyFormation-Label"):
            info = label.find_next_sibling(class_="StickyFormation-Info")
            key = _clean(label.get_text(" ")).rstrip(" :")
            value = _clean(info.get_text(" ")) if info else ""
            if key.lower().startswith("campus"):
                campuses = _split_campuses(value)
            elif key.lower() == "connect":
                online = True
            else:
                lines.append(f"{key} : {value}")

    # Campus lines are replaced by a sentence spelling the count out: the page footer
    # advertises Ynov's 14 campus overall, and the LLM must not confuse that with where
    # *this* formation is taught.
    if campuses:
        sentence = (
            f"Cette formation est proposée sur {len(campuses)} campus Ynov : "
            f"{', '.join(campuses)}."
        )
        if online:
            sentence += " Elle est aussi disponible 100 % en ligne via Ynov Connect."
        lines.append(sentence)
    elif online:
        lines.append(
            "Cette formation est proposée uniquement 100 % en ligne via Ynov Connect, "
            "sur aucun campus physique."
        )
    return "\n".join(lines), campuses


def _programme_years(content: Tag) -> str:
    """Rewrite the year/module accordion so each module heading names its year."""
    parts = []
    for year in content.select(".ProgramYears-Year"):
        year_title_el = year.find(class_="ProgramYears-YearTitle")
        year_title = _clean(year_title_el.get_text(" ")) if year_title_el else ""
        for header in year.select(".js-accordion__header"):
            panel = header.find_next_sibling(class_="js-accordion__panel")
            module = _clean(header.get_text(" "))
            body = _to_text(panel) if panel else ""
            parts.append(f"### {year_title} — {module}\n{body}")
        footer = year.find(class_="ProgramYears-Footer")
        if footer:
            parts.append(_to_text(footer))
        year.decompose()
    return "\n".join(parts)


def _accordion_sections(block: Tag, item_cls: str, title_cls: str) -> list[tuple[str, str]]:
    sections = []
    for item in block.select(f".{item_cls}"):
        title_el = item.find(class_=title_cls)
        panel = item.find(class_="js-accordion__panel")
        if not title_el or not panel:
            continue
        title = _clean(title_el.get_text(" "))
        if _is_generic(title):
            continue
        programme = _programme_years(panel) if panel.select_one(".ProgramYears-Year") else ""
        body = "\n".join(t for t in (_to_text(panel), programme) if t)
        sections.append((title, body))
    return sections


def parse_formation_page(html: str) -> dict:
    """Parse a ynov.com formation page.

    Returns {"formation", "campuses", "last_modified", "sections": [(title, text)]}.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    formation = _formation_name(main)
    key_info, campuses = _key_info(main)

    sections: list[tuple[str, str]] = [("Infos clés", key_info)] if key_info else []
    presentation: list[str] = []
    last_modified = None

    for block in main.select("div.landing-page__block"):
        btype = _block_type(block)
        if btype in EXCLUDED_BLOCKS or btype == "block_sticky_formation":
            continue
        if btype == "block_richtext":
            text = _clean(block.get_text(" "))
            match = re.search(r"Date de dernière modification\s*:\s*(\S+)", text)
            if match:
                last_modified = match.group(1)
                continue
        if btype in ("block_media_key_figure", "block_richtext_advanced"):
            presentation.append(_to_text(block))
        elif btype == "block_programme_details":
            sections += _accordion_sections(
                block, "Bloc-ProgrammeDetails-Item", "Bloc-ProgrammeDetails-Item-Title"
            )
        elif btype == "block_faq":
            sections += _accordion_sections(block, "Bloc-Faq-Item", "Bloc-Faq-TitleText")
        elif btype == "block_keyword_cloud" and block.get("id") != "poursuites":
            continue  # "Les autres BTS…": a link list to other formations
        else:
            text = _to_text(block)
            heading = block.find(["h2", "h3"])
            title = _clean(heading.get_text(" ")) if heading else btype
            if text:
                sections.append((title, text))

    if presentation:
        sections.insert(1 if key_info else 0, ("Présentation", "\n".join(presentation)))

    return {
        "formation": formation,
        "campuses": campuses,
        "last_modified": last_modified,
        "sections": [(t, b) for t, b in sections if b.strip()],
    }


def is_formation_page(html: str) -> bool:
    return "landing-page__block" in html and "block_sticky_formation" in html


def parse_generic_page(html: str) -> str:
    """Fallback for non-Ynov HTML: main content without page chrome."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("main") or soup.body or soup
    for chrome in root.find_all(["nav", "header", "footer", "aside"]):
        chrome.decompose()
    return _to_text(root)
