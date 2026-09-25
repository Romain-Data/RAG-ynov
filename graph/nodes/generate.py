import httpx

from app.core.config import settings
from graph.state import GraphState


def generate_node(state: GraphState) -> dict:
    """Generate answer using Mammouth LLM with retrieved context."""
    question = state.get("question", "")
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
    system_prompt = (
        "Tu es un assistant pédagogique pour Ynov. Réponds à la question en t'appuyant "
        "UNIQUEMENT sur le contexte fourni. Si le contexte ne contient pas la réponse, "
        "dis-le honnêtement. Cite tes sources avec [Source X]."
    )
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
