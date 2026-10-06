"""Unit tests for the HTML loader (ynov.com formation pages + generic fallback)."""

from pathlib import Path

from ingestion.build_common import build
from ingestion.chunking import chunk_documents
from ingestion.html_loader import parse_formation_page, parse_info_page
from ingestion.loaders import load_directory, load_file

# Trimmed-down copy of a ynov.com formation page: same CMS block classes, tiny content.
_STICKY = """
<div class="landing-page__block block_sticky_formation">
  <h3>Mastère Expert en intelligence artificielle</h3>
  <div class="Bloc-Info">
    <p class="StickyFormation-Label">Prochaine rentrée :</p>
    <p class="StickyFormation-Info">Septembre 2027</p>
    <p class="StickyFormation-Label">Campus concernés :</p>
    <p class="StickyFormation-Info">Lyon,
        Paris,
        et
        Strasbourg</p>
    <p class="StickyFormation-Label">Connect</p>
    <p class="StickyFormation-Info">Formation disponible en ligne</p>
  </div>
  <a>Candidater</a>
</div>
"""

FORMATION_HTML = f"""<!doctype html><html><body>
<header><h3>Formations Cybersécurité →</h3></header>
<main>
  <nav class="Breadcrumb">Accueil Formations</nav>
  <div class="HeroFormation-Content">
    <p class="HeroFormation-Subtitle">4ème &amp; 5ème année</p>
    <p class="HeroFormation-Rncp">Titre RNCP de niveau 7</p>
    <button>Candidater</button>
  </div>
  <div class="landing-page__block block_anchor_menu"><ul><li>Programme</li></ul></div>
  {_STICKY}
  <div class="landing-page__block block_media_key_figure" id="presentation">
    <h2>Apprends à construire l'IA</h2><p>Deux ans en alternance.</p>
  </div>
  {_STICKY}
  <div class="landing-page__block block_programme_details">
    <div class="Bloc-ProgrammeDetails-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-ProgrammeDetails-Item-Title">Programme du Mastère</span>
        <span class="Bloc-ProgrammeDetails-Item-Subtitle">Détails et rythme</span>
      </h3>
      <div class="js-accordion__panel">
        <div class="ProgramYears-Year">
          <h3 class="ProgramYears-YearTitle"><p>Mastère 1</p></h3>
          <div class="js-accordion">
            <h3 class="js-accordion__header"><p>Module 1</p></h3>
            <div class="js-accordion__panel"><ul><li>Fondamentaux du ML</li></ul></div>
          </div>
        </div>
        <div class="ProgramYears-Year">
          <h3 class="ProgramYears-YearTitle"><p>Mastère 2</p></h3>
          <div class="js-accordion">
            <h3 class="js-accordion__header"><p>Module 1</p></h3>
            <div class="js-accordion__panel"><ul><li>Systèmes RAG avancés</li></ul></div>
          </div>
        </div>
      </div>
    </div>
    <div class="Bloc-ProgrammeDetails-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-ProgrammeDetails-Item-Title">Tarifs</span>
      </h3>
      <div class="js-accordion__panel">
        <p>Mastère 1 : 9 000 €</p>
        <p>Le paiement échelonné correspond à un paiement en 4 échéances.</p>
        <p>Alternance</p>
        <p>Les frais de formation sont pris en charge par l’entreprise.</p>
      </div>
    </div>
    <div class="Bloc-ProgrammeDetails-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-ProgrammeDetails-Item-Title">Le processus d’admission</span>
      </h3>
      <div class="js-accordion__panel"><p>Découvre notre processus d'admission.</p></div>
    </div>
  </div>
  <div class="landing-page__block block_slider_student_project"><h2>Projets</h2></div>
  <div class="landing-page__block block_faq">
    <div class="Bloc-Faq-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-Faq-TitleText">Ce titre en quelques chiffres</span></h3>
      <div class="js-accordion__panel"><p>Taux de réussite : 80%</p></div>
    </div>
    <div class="Bloc-Faq-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-Faq-TitleText">Méthodes mobilisées</span></h3>
      <div class="js-accordion__panel"><p>LinkedIn Learning, Moodle</p></div>
    </div>
    <div class="Bloc-Faq-Item">
      <h3 class="js-accordion__header">
        <span class="Bloc-Faq-TitleText">Passerelles</span></h3>
      <div class="js-accordion__panel">
        <p>Passerelles La mobilité géographique est possible.</p>
      </div>
    </div>
  </div>
  <div class="landing-page__block block_reinsurance"><p>14 campus dont Connect</p></div>
  <div class="landing-page__block block_richtext">
    <p>Date de dernière modification : 01/10/26</p>
  </div>
</main>
<footer>Mentions légales</footer>
</body></html>
"""

MANIFEST = (
    "source: mastere-ia.html\ndoc_type: formation\nprogram: mastere-ia\nyear: 2027\n"
    "title: Mastère IA\nlanguage: fr\n"
)


def _write_page(tmp_path: Path, html: str = FORMATION_HTML) -> Path:
    page = tmp_path / "mastere-ia.html"
    page.write_text(html, encoding="utf-8")
    (tmp_path / "mastere-ia.manifest.yml").write_text(MANIFEST, encoding="utf-8")
    return page


class TestFormationPage:
    def test_keeps_formation_sections_only(self):
        page = parse_formation_page(FORMATION_HTML)
        titles = [t for t, _ in page["sections"]]
        assert titles == [
            "Infos clés",
            "Lieux",
            "Présentation",
            "Programme du Mastère — Mastère 1 — Module 1",
            "Programme du Mastère — Mastère 2 — Module 1",
            "Tarifs",
            "Ce titre en quelques chiffres",
        ]
        all_text = "\n".join(b for _, b in page["sections"])
        for noise in (
            "14 campus",
            "Moodle",
            "Projets",
            "Candidater",
            "Mentions légales",
            "Formations Cybersécurité",
            "Date de dernière modification",
        ):
            assert noise not in all_text

    def test_campus_count_is_explicit_and_not_duplicated(self):
        page = parse_formation_page(FORMATION_HTML)
        places = dict(page["sections"])["Lieux"]
        assert page["campuses"] == ["Lyon", "Paris", "Strasbourg"]
        assert places.startswith("Où est proposée la formation Mastère Expert en intelligence")
        assert "Dans 3 villes (campus Ynov) : Lyon, Paris, Strasbourg." in places
        assert "en ligne via Ynov Connect" in places
        assert places.count("Lyon") == 1  # recap card is rendered twice in the page
        assert "Lyon" not in dict(page["sections"])["Infos clés"]

    def test_single_campus_wording(self):
        one = FORMATION_HTML.replace(
            """Lyon,
        Paris,
        et
        Strasbourg""",
            "Strasbourg",
        )
        places = dict(parse_formation_page(one)["sections"])["Lieux"]
        assert places.endswith(
            "Uniquement à Strasbourg (un seul campus Ynov). "
            "Elle est aussi disponible 100 % en ligne via Ynov Connect."
        )

    def test_key_facts_are_written_as_questions(self):
        key_info = dict(parse_formation_page(FORMATION_HTML)["sections"])["Infos clés"]
        assert (
            "Quand a lieu la prochaine rentrée de la formation Mastère Expert en "
            "intelligence artificielle ? Septembre 2027."
        ) in key_info

    def test_key_facts_summary(self):
        assert parse_formation_page(FORMATION_HTML)["key_facts"] == "3 campus et en ligne"

    def test_online_only_formation_says_so(self):
        online_only = FORMATION_HTML.replace(
            """Lyon,
        Paris,
        et
        Strasbourg""",
            "",
        )
        page = parse_formation_page(online_only)
        assert page["campuses"] == []
        assert "Uniquement 100 % en ligne via Ynov Connect" in dict(page["sections"])["Lieux"]
        assert page["key_facts"] == "100 % en ligne, aucun campus"

    def test_generic_title_matching_ignores_leading_article(self):
        html = FORMATION_HTML.replace("Méthodes mobilisées", "Les méthodes mobilisées")
        assert "Moodle" not in "\n".join(b for _, b in parse_formation_page(html)["sections"])

    def test_one_programme_section_per_module_named_with_its_year(self):
        sections = dict(parse_formation_page(FORMATION_HTML)["sections"])
        assert sections["Programme du Mastère — Mastère 1 — Module 1"] == "- Fondamentaux du ML"
        assert sections["Programme du Mastère — Mastère 2 — Module 1"] == "- Systèmes RAG avancés"
        assert "Programme du Mastère" not in sections

    def test_tarifs_keep_prices_but_not_shared_payment_terms(self):
        tarifs = dict(parse_formation_page(FORMATION_HTML)["sections"])["Tarifs"]
        assert tarifs == "Mastère 1 : 9 000 €"

    def test_keep_generic_returns_boilerplate_for_build_common(self):
        sections = dict(parse_formation_page(FORMATION_HTML, keep_generic=True)["sections"])
        assert "Moodle" in sections["Méthodes mobilisées"]
        assert "4 échéances" in sections["Tarifs"]
        # the panel repeating its own title is trimmed
        assert sections["Passerelles"] == "La mobilité géographique est possible."

    def test_last_modified_goes_to_metadata(self):
        assert parse_formation_page(FORMATION_HTML)["last_modified"] == "01/10/26"


class TestLoadHtml:
    def test_one_document_per_section_with_metadata(self, tmp_path: Path):
        docs = load_file(_write_page(tmp_path))
        assert len(docs) == 7
        meta = docs[0]["metadata"]
        assert meta["section"] == "Infos clés"
        assert meta["formation"] == "Mastère Expert en intelligence artificielle"
        assert meta["doc_type"] == "formation"  # manifest merged
        assert meta["campuses"] == ["Lyon", "Paris", "Strasbourg"]

    def test_every_chunk_carries_formation_and_section(self, tmp_path: Path):
        chunks = chunk_documents(load_file(_write_page(tmp_path)), chunk_size=60, chunk_overlap=0)
        programme = [c for c in chunks if c["metadata"]["section"].startswith("Programme du")]
        assert len(programme) > 1
        for c in programme:
            prefix = (
                "Mastère Expert en intelligence artificielle (3 campus et en ligne) — "
                f"{c['metadata']['section']}\n"
            )
            assert c["text"].startswith(prefix)

    def test_generic_html_fallback(self, tmp_path: Path):
        page = _write_page(
            tmp_path,
            "<html><body><nav>Menu</nav><main><h1>Titre</h1><p>Contenu utile</p></main>"
            "<footer>Pied</footer></body></html>",
        )
        docs = load_file(page)
        assert len(docs) == 1
        assert docs[0]["text"] == "Titre\nContenu utile"

    def test_load_directory_picks_up_html(self, tmp_path: Path):
        _write_page(tmp_path)
        assert len(load_directory(tmp_path)) == 7


INFO_HTML = """<!doctype html><html><body><main>
  <div class="HeroBanner"><h1>Admission - Comment rejoindre Ynov</h1></div>
  <div class="ezlandingpage-field">
    <div class="landing-page__block" id="Menu-d-ancres"><ul><li>Profil</li></ul></div>
    <div class="landing-page__block" id="Processus"><h2>Un processus clair</h2></div>
    <div class="landing-page__block" id="Processus"><h3>1</h3><p>Tu candidates en ligne.</p></div>
    <div class="landing-page__block" id="FAQ">
      <h2>Coordonnées</h2>
      <p>email : <a href="/cdn-cgi/l/email-protection" class="__cf_email__"
         data-cfemail="72111d1c061311065f0213001b01320b1c1d045c111d1f">[email&#160;protected]</a></p>
    </div>
    <div class="landing-page__block" id="Reassurance"><p>14 campus</p></div>
    <div class="landing-page__block"><p>Date de dernière modification : 01/10/2026</p></div>
  </div>
</main></body></html>
"""


class TestInfoPage:
    def test_sections_merge_headingless_blocks_and_skip_chrome(self):
        page = parse_info_page(INFO_HTML)
        assert page["title"] == "Admission - Comment rejoindre Ynov"
        assert page["last_modified"] == "01/10/2026"
        assert [t for t, _ in page["sections"]] == ["Un processus clair", "Coordonnées"]
        assert "Tu candidates en ligne." in dict(page["sections"])["Un processus clair"]
        assert "14 campus" not in "\n".join(b for _, b in page["sections"])

    def test_cloudflare_emails_are_decoded(self):
        coords = dict(parse_info_page(INFO_HTML)["sections"])["Coordonnées"]
        assert "contact-paris@ynov.com" in coords
        assert "protected" not in coords

    def test_info_page_loads_with_page_title_prefix(self, tmp_path: Path):
        page = tmp_path / "condition-admission.html"
        page.write_text(INFO_HTML, encoding="utf-8")
        (tmp_path / "condition-admission.manifest.yml").write_text(MANIFEST, encoding="utf-8")
        docs = load_file(page)
        assert docs[0]["prefix"] == "Admission - Comment rejoindre Ynov — Un processus clair\n"
        assert docs[0]["metadata"]["last_modified"] == "01/10/2026"


class TestBuildCommon:
    def test_gathers_boilerplate_once_and_keeps_particularities(self, tmp_path: Path):
        (tmp_path / "a.html").write_text(FORMATION_HTML, encoding="utf-8")
        (tmp_path / "b.html").write_text(FORMATION_HTML, encoding="utf-8")
        (tmp_path / "c.html").write_text(
            FORMATION_HTML.replace("LinkedIn Learning, Moodle", "Pronote uniquement, rien d'autre"),
            encoding="utf-8",
        )
        md = build(tmp_path)
        assert md.count("## Méthodes mobilisées\n") == 1
        assert "S'applique aux formations : Mastères." in md
        assert "## Méthodes mobilisées — particularité : Mastère Expert en intelligence" in md
        assert "Pronote uniquement" in md
        assert "## Modalités de paiement et prise en charge des frais" in md
        assert "### Alternance" in md
        assert "4 échéances" in md
        assert "9 000 €" not in md  # prices stay on the formation pages


CFA_HTML = """<!doctype html><html><body><main>
  <div class="HeroBanner"><h1>Ynov, Centre de formation des apprentis (CFA)</h1></div>
  <div class="ezlandingpage-field">
    <div class="landing-page__block" id="Media-Texte">
      <h2>Taux de réussite apprentis</h2>
      <h3><strong>Expert en Cybersécurité – [RNCP40897]</strong></h3>
      <ul><li>Taux de réussite des apprentis : 79%</li></ul>
      <p>Résultat obtenu de 121 certifiés sur 154 candidats</p>
      <p>02.</p>
      <h3><span><p>Expert en Développement Logiciel – [RNCP39583]</p></span></h3>
      <ul><li>Taux de réussite des apprentis : 77%</li></ul>
    </div>
  </div>
</main></body></html>
"""


class TestInfoPageSubheadings:
    def test_one_section_per_h3_keeps_figures_with_their_title(self):
        sections = dict(parse_info_page(CFA_HTML)["sections"])
        cyber = sections["Taux de réussite apprentis — Expert en Cybersécurité – [RNCP40897]"]
        dev = sections[
            "Taux de réussite apprentis — Expert en Développement Logiciel – [RNCP39583]"
        ]
        assert "79%" in cyber and "121 certifiés" in cyber
        assert dev == "- Taux de réussite des apprentis : 77%"  # h3 text in nested tags
        assert "02." not in cyber  # numbering of the next item is dropped
