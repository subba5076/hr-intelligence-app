from pydantic import BaseModel


class DocumentInfo(BaseModel):
    filename: str
    title: str
    chunk_count: int
    ingested_at: str


class IngestResponse(BaseModel):
    documents_ingested: int
    total_chunks: int


class UploadResponse(BaseModel):
    filename: str
    title: str
    chunk_count: int
