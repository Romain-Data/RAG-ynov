import httpx

from app.core.config import settings
from graph.state import GraphState

# Rules 2-3 fix EC-03 (a shared footnote listing campuses was read as the places of an
# online-only formation), rule 4 EC-06 (general questions drowned in per-formation
# tariffs), rule 5 EC-12 (other schools pass the grading threshold), the end of rule 1
# EC-13 (an invented "all BTS are on Parcoursup"). See eval/.
SYSTEM_PROMPT = (
    "Tu es l'assistant d'information d'Ynov Campus. Tu réponds aux questions sur les "
    "formations Ynov (BTS, Bachelors, Mastères), l'admission, les tarifs, le financement "
    "et la vie étudiante, UNIQUEMENT à partir du contexte fourni.\n\n"
    "Règles :\n"
    "1. N'utilise que le contexte. S'il ne contient pas la réponse, dis-le honnêtement, "
    "sans rien inventer. N'ajoute aucune déduction ni généralisation qui n'est pas écrite "
    "dans le contexte : s'il ne cite que certaines formations, ne conclus rien sur les "
    "autres.\n"
    "2. Chaque extrait commence par un en-tête « Formation (durée, lieux) — Section ». "
    "La durée et les lieux indiqués entre parenthèses font foi : une formation "
    "« 100 % en ligne, aucun campus » n'est proposée sur aucun campus, même si un autre "
    "passage cite des villes.\n"
    "3. Un passage commun à toutes les formations (par exemple la liste des campus où un "
    "type de contrat est possible) ne signifie pas qu'une formation donnée y est "
    "proposée.\n"
    "4. Pour une question générale (paiement, admission, alternance…), donne d'abord la "
    "règle commune à toutes les formations avec ses détails (montants, échéances, "
    "conditions, délais) ; ne détaille des formations particulières que si la question "
    "le demande.\n"
    "5. Tu ne réponds que sur Ynov : si la question porte sur une autre école ou sur un "
    "sujet sans rapport, dis que tu ne peux répondre qu'aux questions sur Ynov.\n"
    "6. Réponds en français, de façon concise, et cite tes sources avec [Source X]."
)


def generate_node(state: GraphState) -> dict:
    """Generate answer using Mammouth LLM with retrieved context."""
    # The standalone rewrite of a follow-up is unambiguous; the history lets the model
    # keep the thread of the conversation.
    question = state.get("rewritten") or state.get("question", "")
    history = state.get("history") or []
    retrieved = state.get("retrieved", [])

    if not retrieved:
        return {"answer": "", "sources": []}

    # Build context from retrieved chunks
    context_parts = []
    sources = []
    for i, r in enumerate(retrieved):
        text = r.get("text", "")
        source = r.get("source", "")
        page = r.get("page")
        score = r.get("score", 0.0)
        source_label = f"[Source {i+1}: {source}"
        if page:
            source_label += f", p.{page}"
        source_label += "]"
        context_parts.append(f"{source_label}\n{text}")
        sources.append({
            "source": source,
            "page": page,
            "section": r.get("section"),
            "score": score,
        })

    context = "\n\n".join(context_parts)

    # Build prompt
    system_prompt = SYSTEM_PROMPT
    user_prompt = f"""Contexte :
{context}

Question : {question}

Réponse :"""

    # Call Mammouth API
    url = f"{settings.mammouth_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.mammouth_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.mammouth_chat_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    answer = data["choices"][0]["message"]["content"].strip()

    return {"answer": answer, "sources": sources}
