// Shared TypeScript types, mirroring the Pydantic schemas in
// backend/app/schemas/chat.py. Keeping these in sync manually is fine at
// this scale; a larger app might generate these from the OpenAPI schema.

export interface SourceChunk {
  filename: string;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  // Only assistant messages can be rated.
  feedback?: 1 | -1 | null;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  sources: SourceChunk[];
}

export interface DocumentInfo {
  filename: string;
  title: string;
  chunk_count: number;
  ingested_at: string;
}

export interface UploadResponse {
  filename: string;
  title: string;
  chunk_count: number;
}
