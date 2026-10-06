"""Tests for the pure helpers of the chat: sources block and history of a thread."""

import re

from chat.messages import AUTHOR, cited_numbers, history_from_steps, strip_sources, with_sources

SOURCES = [
    {"source": "bachelor-informatique.html", "section": "Infos clés", "page": 1},
    {"source": "bts-era.html", "section": "Lieux", "page": 1},
    {"source": "programme.pdf", "section": None, "page": 4},
]


class TestSources:
    def test_cited_numbers_reads_single_and_grouped_citations(self):
        assert cited_numbers("A [Source 3]. B [Source 1, Source 2]. C [Source 3]") == [1, 2, 3]
        assert cited_numbers("Aucune citation") == []

    def test_lists_only_the_cited_sources_numbered_like_the_text(self):
        text = with_sources("Dure 3 ans [Source 1]. Lieux : Lyon [Source 3].", SOURCES)
        assert text.endswith(
            "**Sources**\n1. bachelor-informatique.html — Infos clés\n3. programme.pdf (p. 4)"
        )

    def test_the_page_is_shown_for_pdfs_only(self):
        text = with_sources("A [Source 1]. B [Source 3].", SOURCES)
        assert "1. bachelor-informatique.html — Infos clés\n" in text + "\n"  # page 1: no "(p. 1)"
        assert "(p. 1)" not in text and "(p. 4)" in text

    def test_a_markdown_document_has_no_page_number(self):
        sources = [
            {"source": "informations-communes-formations.md", "section": "Paiement", "page": 1}
        ]
        assert with_sources("A [Source 1]", sources).endswith(
            "1. informations-communes-formations.md — Paiement"
        )

    def test_a_source_with_a_url_is_a_link_named_after_the_page(self):
        sources = [
            {
                "source": "bts-era.html",
                "title": "BTS ERA - Étude et Réalisation d'Agencement",
                "section": "Infos clés",
                "url": "https://www.ynov.com/formations/architecture-d-interieur/bts-era",
            }
        ]
        assert with_sources("Niveau [Source 1]", sources).endswith(
            "1. [BTS ERA - Étude et Réalisation d'Agencement — Infos clés]"
            "(https://www.ynov.com/formations/architecture-d-interieur/bts-era)"
        )

    def test_markdown_characters_of_a_title_cannot_break_the_link(self):
        sources = [
            {
                "source": "rncp-39583.html",
                "title": "RNCP39583 — Expert",
                "section": "Statistiques [RNCP39583] *x*",
                "url": "https://www.francecompetences.fr/recherche/rncp/39583/",
            }
        ]
        text = with_sources("A [Source 1]", sources)
        assert r"\[RNCP39583\] \*x\*](https://" in text

    def test_a_url_that_is_not_http_is_not_linked(self):
        sources = [{"source": "a.html", "section": "S", "url": "javascript:alert(1)"}]
        text = with_sources("A [Source 1]", sources)
        assert "](" not in text and text.endswith("1. a.html — S")

    def test_a_closing_parenthesis_in_the_url_is_encoded(self):
        sources = [{"source": "a.html", "url": "https://example.com/a_(b)"}]
        assert with_sources("A [Source 1]", sources).endswith("(https://example.com/a_(b%29)")

    def test_unknown_numbers_are_ignored(self):
        assert with_sources("Réponse [Source 9]", SOURCES) == "Réponse [Source 9]"

    def test_a_refusal_has_no_sources_block(self):
        assert with_sources("Je n'ai pas trouvé d'information.", []) == (
            "Je n'ai pas trouvé d'information."
        )

    def test_strip_sources_gives_back_the_answer(self):
        answer = "Dure 3 ans [Source 1]."
        assert strip_sources(with_sources(answer, SOURCES)) == answer
        assert strip_sources("Sans bloc") == "Sans bloc"


class TestHistoryFromSteps:
    def test_keeps_the_conversation_only(self):
        steps = [
            {"type": "assistant_message", "output": "Bonjour !"},  # the greeting
            {"type": "user_message", "output": "Durée du Bachelor ?"},
            {"type": "run", "output": "internal"},
            {"type": "assistant_message", "output": "3 ans [Source 1]\n\n**Sources**\n1. x.html"},
            {"type": "user_message", "output": "  "},
            {"type": "user_message", "output": "Et à Lyon ?"},
        ]
        assert history_from_steps(steps, skip="Bonjour !") == [
            {"role": "user", "content": "Durée du Bachelor ?"},
            {"role": "assistant", "content": "3 ans [Source 1]"},
            {"role": "user", "content": "Et à Lyon ?"},
        ]


def test_author_is_accepted_by_the_avatar_route_of_chainlit():
    # chainlit/server.py get_avatar: ^[a-zA-Z0-9_ .-]+$ (a 400 gives a blank avatar)
    assert re.match(r"^[a-zA-Z0-9_ .-]+$", AUTHOR)
