"""HTML parsing for scraped ynov.com pages.

A formation page is a stack of CMS blocks (`div.landing-page__block.block_*`).
We keep the blocks that describe *this* formation and drop navigation, CTAs and
boilerplate repeated on every formation page, so the index is not flooded with
near-identical chunks. Each kept section becomes one document, so chunks never
straddle two sections and carry their section title in metadata.

The boilerplate dropped here is not lost: ingestion.build_common gathers it into a
single "informations communes" document. Info pages (admission, alternance, VAE…)
use another template and are parsed by parse_info_page.
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
# the 42 formation pages, one variant per diploma type at most). Matched on the normalized
# title: lowercase, no accents, straight quotes, leading article dropped.
# Not here: Tarifs (shared wording, different prices) and évaluations certificatives
# (7 variants, the jury and rules depend on the RNCP title).
GENERIC_SECTIONS = {
    "processus d'admission",
    "voie d'acces",
    "methodes mobilisees",
    "modalites d'evaluation continue",
    "passerelles",
    "accessibilite aux personnes en situation de handicap",
}

# Tarifs lines shared by every formation (payment terms, alternance, formation continue).
# Removed from each formation's Tarifs section, kept once in the common document.
TARIF_BOILERPLATE_PREFIXES = (
    "le paiement comptant correspond",
    "le paiement echelonne correspond",
    "les frais de formation sont pris en charge",
    "pour toute demande d'inscription dans le cadre d'une action de formation",
)
TARIF_BOILERPLATE_HEADERS = {"alternance", "formation professionnelle continue"}

# Info-page blocks (CMS block id) that carry no content.
EXCLUDED_INFO_BLOCK_IDS = {
    "Menu-d-ancres",
    "Reassurance",
    "Slider-Logo",
    "Separateur",
    "Media-Simple",
}

_BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "section"}
_NOISE_TAGS = ["script", "style", "svg", "img", "button", "noscript", "form", "iframe"]


def _normalize_title(title: str) -> str:
    title = unicodedata.normalize("NFKD", title.replace("’", "'"))
    title = "".join(c for c in title if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", title).strip().lower()


def _is_generic(title: str) -> bool:
    return re.sub(r"^(les|le|la) ", "", _normalize_title(title)) in GENERIC_SECTIONS


def _decode_cf_emails(soup: BeautifulSoup) -> None:
    """Replace Cloudflare-obfuscated e-mails ("[email\xa0protected]") with the address.

    The hex payload is XOR-encoded with its first byte as the key.
    """

    def decode(hex_str: str) -> str:
        key = int(hex_str[:2], 16)
        return "".join(chr(int(hex_str[i : i + 2], 16) ^ key) for i in range(2, len(hex_str), 2))

    for el in soup.select("[data-cfemail]"):
        el.replace_with(NavigableString(decode(str(el["data-cfemail"]))))
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        address = decode(str(a["href"]).split("#", 1)[1])
        a.replace_with(NavigableString(address))


def _strip_tarif_boilerplate(text: str) -> str:
    kept = []
    for line in text.splitlines():
        norm = _normalize_title(line)
        if norm in TARIF_BOILERPLATE_HEADERS or norm.startswith(TARIF_BOILERPLATE_PREFIXES):
            continue
        kept.append(line)
    return "\n".join(kept)


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
    # "http://name@ynov.com": a mailto mistyped as a URL on the site
    text = re.sub(r"\bhttps?://([\w.+-]+@[\w-]+\.[\w.]+)", r"\1", el.get_text(""))
    lines = (_clean(line) for line in text.split("\n"))
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


# Recap-card facts written as question + answer: the paraphrase embedding model matches
# a user question far better against a question than against "Durée : 2 ans".
_KEY_QUESTIONS = {
    "prochaine rentrée": "Quand a lieu la prochaine rentrée de la formation {name} ? {value}.",
    "durée": "Combien de temps dure la formation {name} ? {value}.",
    "niveau d'entrée": "Quel niveau faut-il pour entrer dans la formation {name} ? {value}.",
}


def _key_info(soup: Tag, name: str) -> dict:
    """Hero + recap card (rentrée, durée, niveau, campus).

    Returns {"text", "places", "campuses", "online", "duration"}: `text` holds the key
    facts, `places` where the formation is taught (its own section, so a "où / dans
    quelles villes" question finds a short, focused chunk).
    """
    lines = []
    duration = ""
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
                template = _KEY_QUESTIONS.get(key.lower(), "{key} : {value}")
                lines.append(template.format(name=name, key=key, value=value))
                if key.lower().startswith("durée"):
                    duration = value

    # The count is spelled out: the page footer advertises Ynov's 14 campus overall, and
    # the LLM must not confuse that with where *this* formation is taught.
    question = f"Où est proposée la formation {name}, dans quelles villes ?"
    if campuses:
        if len(campuses) == 1:
            places = f"{question} Uniquement à {campuses[0]} (un seul campus Ynov)."
        else:
            places = (
                f"{question} Dans {len(campuses)} villes (campus Ynov) : {', '.join(campuses)}."
            )
        if online:
            places += " Elle est aussi disponible 100 % en ligne via Ynov Connect."
    elif online:
        places = (
            f"{question} Uniquement 100 % en ligne via Ynov Connect, sur aucun campus physique."
        )
    else:
        places = ""
    return {
        "text": "\n".join(lines),
        "places": places,
        "campuses": campuses,
        "online": online,
        "duration": duration,
    }


def _key_facts(info: dict) -> str:
    """Short "durée, lieux" summary added to every chunk prefix of the formation, so a
    chunk about tarifs or admission still says how and where it is taught. Kept short:
    the embedding model only reads 128 tokens (the full campus list is in Infos clés)."""
    count = len(info["campuses"])
    if count:
        where = f"{count} campus" if count > 1 else f"campus de {info['campuses'][0]}"
        if info["online"]:
            where += " et en ligne"
    elif info["online"]:
        where = "100 % en ligne, aucun campus"
    else:
        where = ""
    return ", ".join(f for f in (info["duration"], where) if f)


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


def _accordion_sections(
    block: Tag, item_cls: str, title_cls: str, keep_generic: bool
) -> list[tuple[str, str]]:
    sections = []
    for item in block.select(f".{item_cls}"):
        title_el = item.find(class_=title_cls)
        panel = item.find(class_="js-accordion__panel")
        if not title_el or not panel:
            continue
        title = _clean(title_el.get_text(" "))
        if _is_generic(title) and not keep_generic:
            continue
        programme = _programme_years(panel) if panel.select_one(".ProgramYears-Year") else ""
        body = "\n".join(t for t in (_to_text(panel), programme) if t)
        # Some panels repeat their own title as first words ("Passerelles Ce programme…")
        if _normalize_title(body).startswith(_normalize_title(title)):
            body = body[len(title) :].lstrip(" \n:")
        if title == "Tarifs" and not keep_generic:
            body = _strip_tarif_boilerplate(body)
        if programme:
            sections += _split_programme(title, body)
        else:
            sections.append((title, body))
    return sections


def _split_programme(title: str, body: str) -> list[tuple[str, str]]:
    """One section per year/module of a programme ("Programme du Mastère — Mastère 2 —
    Module 1"), so the per-section cap of retrieval applies per module, not to the whole
    programme (EC-05)."""
    parts = re.split(r"^### (.+)$", body, flags=re.MULTILINE)
    sections = [(title, parts[0].strip())] if parts[0].strip() else []
    sections += [(f"{title} — {h.strip()}", b.strip()) for h, b in zip(parts[1::2], parts[2::2])]
    return sections


def parse_formation_page(html: str, keep_generic: bool = False) -> dict:
    """Parse a ynov.com formation page.

    Returns {"formation", "campuses", "key_facts", "last_modified",
    "sections": [(title, text)]}.
    keep_generic=True keeps the boilerplate sections and Tarifs lines (for build_common).
    """
    soup = BeautifulSoup(html, "html.parser")
    _decode_cf_emails(soup)
    main = soup.find("main") or soup
    formation = _formation_name(main)
    info = _key_info(main, formation)
    key_info, campuses = info["text"], info["campuses"]

    sections: list[tuple[str, str]] = [("Infos clés", key_info)] if key_info else []
    if info["places"]:
        sections.append(("Lieux", info["places"]))
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
                block,
                "Bloc-ProgrammeDetails-Item",
                "Bloc-ProgrammeDetails-Item-Title",
                keep_generic,
            )
        elif btype == "block_faq":
            sections += _accordion_sections(
                block, "Bloc-Faq-Item", "Bloc-Faq-TitleText", keep_generic
            )
        elif btype == "block_keyword_cloud" and block.get("id") != "poursuites":
            continue  # "Les autres BTS…": a link list to other formations
        else:
            text = _to_text(block)
            heading = block.find(["h2", "h3"])
            title = _clean(heading.get_text(" ")) if heading else btype
            if text:
                sections.append((title, text))

    if presentation:
        sections.insert(
            len(sections) if not sections else 1 + bool(info["places"]),
            ("Présentation", "\n".join(presentation)),
        )

    return {
        "formation": formation,
        "campuses": campuses,
        "key_facts": _key_facts(info),
        "last_modified": last_modified,
        "sections": [(t, b) for t, b in sections if b.strip()],
    }


def is_formation_page(html: str) -> bool:
    return "landing-page__block" in html and "block_sticky_formation" in html


def is_info_page(html: str) -> bool:
    """ynov.com editorial page (admission, alternance, VAE…), not a formation page."""
    return "ezlandingpage-field" in html and not is_formation_page(html)


_SUBSECTION_MARK = "§§h3§§"


def _split_by_subheadings(block: Tag, block_title: str) -> list[list[str]]:
    """One section per h3 of a block: "<block title> — <h3>", plus the intro if any.

    Lists of items under h3 subheadings (success rates per RNCP title, FAQ questions,
    contacts per campus) were cut into 300-character chunks across items, so a chunk
    could hold one item's figures and the next item's name (EC-14).
    """
    for subheading in block.find_all("h3"):
        subheading.insert(0, NavigableString(_SUBSECTION_MARK))
    sections: list[list[str]] = [[block_title, ""]]
    awaiting_title = False  # h3 text may sit on the line after the mark (nested tags)
    for line in _to_text(block).split("\n"):
        if line.startswith(_SUBSECTION_MARK):
            subtitle = line[len(_SUBSECTION_MARK) :].strip()
            sections.append([f"{block_title} — {subtitle}", ""])
            awaiting_title = not subtitle
        elif awaiting_title:
            sections[-1][0] += line
            awaiting_title = False
        elif line != block_title and not re.fullmatch(r"\d+\.", line):  # "03." numbering
            sections[-1][1] += line + "\n"
    return [[t, b.strip()] for t, b in sections if b.strip()]


def parse_info_page(html: str) -> dict:
    """Parse a ynov.com info page into sections, one per CMS block with a heading.

    Blocks without a heading continue the previous section (e.g. the admission steps);
    blocks with several h3 subheadings get one section per subheading.
    Returns {"title", "last_modified", "sections": [(title, text)]}.
    """
    soup = BeautifulSoup(html, "html.parser")
    _decode_cf_emails(soup)
    main = soup.find("main") or soup
    h1 = main.find("h1")
    title = _clean(h1.get_text(" ")) if h1 else ""

    sections: list[list[str]] = []
    last_modified = None
    for block in main.select("div.landing-page__block"):
        if block.get("id") in EXCLUDED_INFO_BLOCK_IDS:
            continue
        match = re.search(r"Date de dernière modification\s*:\s*(\S+)", block.get_text(" "))
        if match:
            last_modified = match.group(1)
            continue
        if len(block.find_all("h3")) >= 2:
            h2 = block.find("h2")
            sections += _split_by_subheadings(block, _clean(h2.get_text(" ")) if h2 else title)
            continue
        heading = block.find(["h2", "h3"])
        heading_text = _clean(heading.get_text(" ")) if heading else ""
        text = _to_text(block)
        if not text:
            continue
        if heading_text and not heading_text.isdigit():
            sections.append([heading_text, text])
        elif sections:
            sections[-1][1] += "\n" + text
        else:
            sections.append([title, text])

    return {
        "title": title,
        "last_modified": last_modified,
        "sections": [(t, b) for t, b in sections],
    }


def parse_generic_page(html: str) -> str:
    """Fallback for non-Ynov HTML: main content without page chrome."""
    soup = BeautifulSoup(html, "html.parser")
    _decode_cf_emails(soup)
    root = soup.find("main") or soup.body or soup
    for chrome in root.find_all(["nav", "header", "footer", "aside"]):
        chrome.decompose()
    return _to_text(root)
