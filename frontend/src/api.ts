import axios from "axios";

export const api = axios.create({ baseURL: "" });

export interface Document {
  id: string;
  filename: string;
  total_chunks: number;
  created_at: string;
}

export interface Source {
  chunk_index: number;
  content: string;
  score: number;
  page_number?: number;
  document_name?: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  document_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvalResult {
  faithfulness: number;
  answer_relevancy: number;
  context_relevancy: number;
  answer: string;
  chunks_used: number;
}

// ── REST calls ──────────────────────────────────────────────────────────────

export const uploadDocument = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post<Document>("/api/documents/upload", fd);
};

export const listDocuments = () => api.get<Document[]>("/api/documents/");
export const deleteDocument = (id: string) => api.delete(`/api/documents/${id}`);

export const reingestDocument = (id: string, file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.put<Document>(`/api/documents/${id}/reingest`, fd);
};

export const sendMessage = (payload: {
  conversation_id?: string;
  document_id?: string;
  message: string;
}) => api.post<{ conversation_id: string; answer: string; sources: Source[] }>("/api/chat/", payload);

export const listConversations = () => api.get<Conversation[]>("/api/history/conversations");
export const getMessages = (id: string) =>
  api.get<{ conversation: Conversation; messages: Message[] }>(`/api/history/conversations/${id}/messages`);
export const deleteConversation = (id: string) => api.delete(`/api/history/conversations/${id}`);

export const evaluateQuestion = (payload: { question: string; document_id?: string }) =>
  api.post<EvalResult>("/api/evaluate/", payload);

// ── Streaming helper ─────────────────────────────────────────────────────────

export type StreamEvent =
  | { type: "meta"; conversation_id: string; sources: Source[] }
  | { type: "token"; content: string }
  | { type: "done"; message_id?: string }
  | { type: "error"; message: string };

export async function* streamChat(payload: {
  conversation_id?: string;
  document_id?: string;
  message: string;
}): AsyncGenerator<StreamEvent> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? ""; // keep the last (possibly incomplete) line

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (!raw || raw === "[DONE]") continue;
      try {
        yield JSON.parse(raw) as StreamEvent;
      } catch {
        // ignore malformed SSE lines
      }
    }
  }
}
