from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Question utilisateur")


class Source(BaseModel):
    source: str
    page: int | None = None
    section: str | None = None
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    grade: str = Field(..., pattern="^(ok|refuse)$")


class HealthResponse(BaseModel):
    status: str
    qdrant: str
    embedding_model: str
    chat_model: str


class IngestRequest(BaseModel):
    # For now: we'll just trigger the pipeline on the data/ folder
    # Later: accept file uploads
    pass


class IngestResponse(BaseModel):
    status: str
    indexed_chunks: int
    collection: str