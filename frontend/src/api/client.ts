// Thin fetch wrapper for the FastAPI backend. Centralizing this here means
// the base URL and error handling only need to be correct in one place.
import type { ChatResponse, DocumentInfo, UploadResponse } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function parseErrorMessage(response: Response): Promise<string> {
  // FastAPI error responses are JSON like {"detail": "..."} -- surface that
  // directly (e.g. "Unsupported file type") instead of a generic message.
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON -- fall through to the generic message below
  }
  return `Request failed with status ${response.status}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }
  return response.json() as Promise<T>;
}

export function sendChatMessage(question: string, conversationId: string | null): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
}

export function submitFeedback(messageId: string, rating: 1 | -1): Promise<{ status: string }> {
  return request(`/api/feedback`, {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, rating }),
  });
}

export function listDocuments(): Promise<DocumentInfo[]> {
  return request<DocumentInfo[]>("/api/documents");
}

export async function uploadDocument(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // No explicit Content-Type here -- the browser sets
  // "multipart/form-data; boundary=..." itself, which is why this doesn't
  // go through the shared `request()` helper (that one hardcodes JSON).
  const response = await fetch(`${BASE_URL}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await parseErrorMessage(response));
  }
  return response.json() as Promise<UploadResponse>;
}
