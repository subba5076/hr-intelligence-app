import type { ChatMessage } from "../types";

interface Props {
  message: ChatMessage;
  onRate?: (rating: 1 | -1) => void;
}

/**
 * Renders a single chat message. Assistant messages additionally show
 * which HR documents were used to ground the answer (sources) and
 * thumbs up/down buttons, which is what feeds the feedback table in
 * Postgres (see backend/app/db/models.py -> Feedback).
 */
export default function MessageBubble({ message, onRate }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`message-row ${isUser ? "message-row--user" : "message-row--assistant"}`}>
      <div className={`message-bubble ${isUser ? "message-bubble--user" : "message-bubble--assistant"}`}>
        <p>{message.content}</p>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <span className="message-sources__label">Sources:</span>{" "}
            {[...new Set(message.sources.map((s) => s.filename))].join(", ")}
          </div>
        )}

        {!isUser && onRate && (
          <div className="feedback-buttons">
            <button
              className={`feedback-btn ${message.feedback === 1 ? "feedback-btn--active" : ""}`}
              onClick={() => onRate(1)}
              aria-label="Helpful"
              title="Helpful"
            >
              👍
            </button>
            <button
              className={`feedback-btn ${message.feedback === -1 ? "feedback-btn--active" : ""}`}
              onClick={() => onRate(-1)}
              aria-label="Not helpful"
              title="Not helpful"
            >
              👎
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
