import { useState, type FormEvent } from "react";
import type { ChatMessage } from "../types";
import { sendChatMessage, submitFeedback } from "../api/client";
import MessageBubble from "./MessageBubble";

/**
 * The main conversational interface. Owns the message list + conversation
 * id in component state (no global state library needed at this scale),
 * and calls the FastAPI backend for each turn.
 */
export default function ChatWindow() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || isLoading) return;

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const response = await sendChatMessage(question, conversationId);
      setConversationId(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        {
          id: response.message_id,
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          feedback: null,
        },
      ]);
    } catch {
      setError("Something went wrong reaching the HR assistant. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRate(messageId: string, rating: 1 | -1) {
    // Optimistic UI update, then persist to the feedback table.
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback: rating } : m)));
    try {
      await submitFeedback(messageId, rating);
    } catch {
      // Non-critical: feedback failing to save shouldn't disrupt the chat.
      console.error("Failed to submit feedback");
    }
  }

  return (
    <div className="chat-window">
      <div className="chat-window__messages">
        {messages.length === 0 && (
          <p className="chat-window__empty">
            Try asking: "How much PTO do I get?" or "What's the parental leave policy?"
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            message={m}
            onRate={m.role === "assistant" ? (r) => handleRate(m.id, r) : undefined}
          />
        ))}
        {isLoading && <p className="chat-window__typing">HR Assistant is thinking…</p>}
        {error && <p className="chat-window__error">{error}</p>}
      </div>

      <form className="chat-window__input-row" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about HR policy, onboarding, or benefits…"
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
