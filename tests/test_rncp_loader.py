"""Unit tests for the France Compétences RNCP fiche parser."""
from pathlib import Path

from ingestion.fetch import cited_rncp_numbers
from ingestion.loaders import load_file
from ingestion.rncp_loader import parse_rncp_page

_SKILL_1 = "Élaborer une stratégie de collecte de données en définissant les données utiles."
_SKILL_2 = "Construire une base de données en sélectionnant la technologie SQL ou NoSQL adaptée."


def _fiche(attested: str = f"<p>{_SKILL_1}</p><p>{_SKILL_2}</p>", status: str = "Active") -> str:
    return f"""<html><body><main>
  <h2 class="title--page--generic">Ingénieur en science des données</h2>
  <p class="tag--fcpt-certification">
    <span class="tag--fcpt-certification__title">N° de fiche</span>
    <span class="tag--fcpt-certification__status">RNCP39586</span></p>
  <p class="tag--fcpt-certification">
    <span class="tag--fcpt-certification__title">Etat :</span>
    <span class="tag--fcpt-certification__status">{status}</span></p>
  <div class="list--fcpt-certification--essential--desktop__line">
    <p class="list--fcpt-certification--essential--desktop__line__title">
      Nomenclature du niveau de qualification</p>
    <p class="list--fcpt-certification--essential--desktop__line__text">Niveau 7</p>
  </div>
  <div class="accordion--fcpt-certification">
    <button class="accordion--fcpt-certification__button">Certificateur(s)</button>
    <div class="accordion--fcpt-certification__content">
      <table><thead><tr><th>Nom légal</th><th>Siret</th></tr></thead>
      <tbody><tr><td>YNOV</td><td>53056211500101</td></tr></tbody></table>
    </div>
  </div>
  <div class="accordion--fcpt-certification">
    <button class="accordion--fcpt-certification__button">Résumé</button>
    <div class="accordion--fcpt-certification__content">
      <div class="text--fcpt-certification">
        <h3>Activités visées :</h3><p>Collecte de données</p></div>
      <div class="text--fcpt-certification"><h3>Compétences attestées :</h3>{attested}</div>
    </div>
  </div>
  <div class="accordion--fcpt-certification">
    <button class="accordion--fcpt-certification__button">Blocs de compétences</button>
    <div class="accordion--fcpt-certification__content">
      <div class="text--fcpt-certification"><h3>RNCP39586BC01 - Collecter des données</h3></div>
      <div class="table--fcpt-certification__wrapper"><table>
        <thead><tr><th>Liste de compétences</th><th>Modalités d'évaluation</th></tr></thead>
        <tbody><tr><td><p>{_SKILL_1}</p><p>{_SKILL_2}</p></td><td>Étude de cas</td></tr></tbody>
      </table></div>
    </div>
  </div>
  <div class="accordion--fcpt-certification">
    <button class="accordion--fcpt-certification__button">Liens</button>
    <div class="accordion--fcpt-certification__content">
      <div class="text--fcpt-certification">
        <h3>Certifications professionnelles enregistrées au RNCP en correspondance partielle :</h3>
        <p>RNCP12345BC01 - Un bloc d'une autre certification</p>
      </div>
    </div>
  </div>
  <div class="accordion--fcpt-certification">
    <button class="accordion--fcpt-certification__button">Pour plus d'informations</button>
    <div class="accordion--fcpt-certification__content">
      <div class="text--fcpt-certification">
        <h3>Référentiel d'activité, de compétences et d'évaluation :</h3>
        <a href="/wp-json/api/v1/activity/export/26527/541987">Référentiel</a>
      </div>
    </div>
  </div>
</main></body></html>"""


class TestParseRncpPage:
    def test_header_fields(self):
        fiche = parse_rncp_page(_fiche())
        assert fiche["rncp"] == "RNCP39586"
        assert fiche["status"] == "Active"  # not the number, which uses the same tag style
        assert fiche["level"] == "Niveau 7"
        assert fiche["referentiel_urls"] == ["/wp-json/api/v1/activity/export/26527/541987"]

    def test_sections_and_tables(self):
        sections = dict(parse_rncp_page(_fiche())["sections"])
        assert sections["Certificateur(s)"] == "Nom légal : YNOV\nSiret : 53056211500101"
        bloc = sections["RNCP39586BC01 - Collecter des données"]
        assert bloc.startswith("Liste de compétences : ")
        assert "Modalités d'évaluation : Étude de cas" in bloc
        assert "Référentiel d'activité, de compétences et d'évaluation" not in sections

    def test_equivalence_sections_are_skipped(self):
        titles = [t for t, _ in parse_rncp_page(_fiche())["sections"]]
        assert not any(t.startswith("Certifications professionnelles") for t in titles)

    def test_attested_skills_dropped_when_restating_blocs(self):
        assert "Compétences attestées" not in dict(parse_rncp_page(_fiche())["sections"])

    def test_attested_skills_kept_when_different(self):
        other = "<p>Piloter un projet data de bout en bout avec les parties prenantes métier.</p>"
        assert "Compétences attestées" in dict(parse_rncp_page(_fiche(other))["sections"])

    def test_loads_with_rncp_prefix(self, tmp_path: Path):
        page = tmp_path / "rncp-39586.html"
        page.write_text(_fiche(), encoding="utf-8")
        (tmp_path / "rncp-39586.manifest.yml").write_text(
            "doc_type: fiche_rncp\nrncp: '39586'\n", encoding="utf-8"
        )
        docs = load_file(page)
        assert docs[0]["prefix"] == "RNCP39586 Ingénieur en science des données — Infos clés\n"
        assert all(d["metadata"]["rncp_status"] == "Active" for d in docs)


def test_cited_rncp_numbers(tmp_path: Path):
    (tmp_path / "a.html").write_text(
        '<a href="https://www.francecompetences.fr/recherche/rncp/39586/">x</a>'
        '<a href="https://safelinks.example/?url=https%3A%2F%2Fwww.francecompetences.fr'
        '%2Frecherche%2Frncp%2F41123%2F">y</a>',
        encoding="utf-8",
    )
    assert cited_rncp_numbers(tmp_path) == ["39586", "41123"]
