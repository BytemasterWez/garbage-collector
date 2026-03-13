import { useState } from "react";

import type { ChatAnswerResponse } from "../types/items";

type GroundedChatPanelProps = {
  answer: ChatAnswerResponse | null;
  errorMessage: string | null;
  isLoading: boolean;
  onAsk: (question: string) => Promise<void>;
  onSelectItem: (itemId: number) => void;
};

function formatItemType(itemType: "pasted_text" | "url" | "pdf"): string {
  if (itemType === "url") {
    return "URL";
  }

  if (itemType === "pdf") {
    return "PDF";
  }

  return "Text";
}

export function GroundedChatPanel({
  answer,
  errorMessage,
  isLoading,
  onAsk,
  onSelectItem
}: GroundedChatPanelProps) {
  const [question, setQuestion] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onAsk(question);
  }

  return (
    <section className="panel chat-panel">
      <div className="section-heading">
        <h2>Grounded chat</h2>
        <p>Ask one question. Answers must stay tied to retrieved source chunks.</p>
      </div>

      <form className="semantic-search-form" onSubmit={(event) => void handleSubmit(event)}>
        <label className="field-label" htmlFor="chat-question">
          Question
        </label>
        <div className="semantic-search-row">
          <input
            id="chat-question"
            className="search-input"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="e.g. What have I saved about Louisiana property insurance?"
            type="search"
            value={question}
          />
          <button className="primary-button" disabled={isLoading} type="submit">
            {isLoading ? "Thinking..." : "Ask"}
          </button>
        </div>
      </form>

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      {!errorMessage && answer ? (
        <div className="chat-answer-card">
          <p className="chat-answer-text">{answer.answer}</p>
          <div className="chat-citations">
            <h3>Sources</h3>
            {answer.citations.length > 0 ? (
              answer.citations.map((citation) => (
                <button
                  key={`${citation.source_id}-${citation.chunk_id}`}
                  className="semantic-result"
                  onClick={() => onSelectItem(citation.item_id)}
                  type="button"
                >
                  <div className="semantic-result-header">
                    <span className="library-item-title">{citation.item_title}</span>
                    <span className="library-item-badge">{formatItemType(citation.item_type)}</span>
                  </div>
                  <p className="semantic-result-score">
                    {citation.source_id} · Score {citation.score.toFixed(4)}
                  </p>
                  <p className="semantic-result-chunk">{citation.chunk_text}</p>
                </button>
              ))
            ) : (
              <p className="status-message">No grounded citations were returned for this answer.</p>
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
