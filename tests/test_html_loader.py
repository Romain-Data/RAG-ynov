"""Unit tests for the HTML loader (ynov.com formation pages + generic fallback)."""
from pathlib import Path

from ingestion.chunking import chunk_documents
from ingestion.html_loader import parse_formation_page
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
      <div class="js-accordion__panel"><p>Mastère 1 : 9 000 €</p></div>
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
            "Présentation",
            "Programme du Mastère",
            "Tarifs",
            "Ce titre en quelques chiffres",
        ]
        all_text = "\n".join(b for _, b in page["sections"])
        for noise in ("14 campus", "Moodle", "Projets", "Candidater", "Mentions légales",
                      "Formations Cybersécurité", "Date de dernière modification"):
            assert noise not in all_text

    def test_campus_count_is_explicit_and_not_duplicated(self):
        page = parse_formation_page(FORMATION_HTML)
        key_info = dict(page["sections"])["Infos clés"]
        assert page["campuses"] == ["Lyon", "Paris", "Strasbourg"]
        assert "proposée sur 3 campus Ynov : Lyon, Paris, Strasbourg." in key_info
        assert "en ligne via Ynov Connect" in key_info
        assert key_info.count("Lyon") == 1  # recap card is rendered twice in the page

    def test_modules_are_prefixed_with_their_year(self):
        programme = dict(parse_formation_page(FORMATION_HTML)["sections"])["Programme du Mastère"]
        assert "### Mastère 1 — Module 1\n- Fondamentaux du ML" in programme
        assert "### Mastère 2 — Module 1\n- Systèmes RAG avancés" in programme

    def test_last_modified_goes_to_metadata(self):
        assert parse_formation_page(FORMATION_HTML)["last_modified"] == "01/10/26"


class TestLoadHtml:
    def test_one_document_per_section_with_metadata(self, tmp_path: Path):
        docs = load_file(_write_page(tmp_path))
        assert len(docs) == 5
        meta = docs[0]["metadata"]
        assert meta["section"] == "Infos clés"
        assert meta["formation"] == "Mastère Expert en intelligence artificielle"
        assert meta["doc_type"] == "formation"  # manifest merged
        assert meta["campuses"] == ["Lyon", "Paris", "Strasbourg"]

    def test_every_chunk_carries_formation_and_section(self, tmp_path: Path):
        chunks = chunk_documents(load_file(_write_page(tmp_path)), chunk_size=60, chunk_overlap=0)
        programme = [c for c in chunks if c["metadata"]["section"] == "Programme du Mastère"]
        assert len(programme) > 1
        prefix = "Mastère Expert en intelligence artificielle — Programme du Mastère\n"
        assert all(c["text"].startswith(prefix) for c in programme)

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
        assert len(load_directory(tmp_path)) == 5
