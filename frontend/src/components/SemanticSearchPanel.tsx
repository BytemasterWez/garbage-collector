import { useState } from "react";

import type { SemanticSearchResult } from "../types/items";

type SemanticSearchPanelProps = {
  isLoading: boolean;
  errorMessage: string | null;
  results: SemanticSearchResult[];
  onSearch: (query: string) => Promise<void>;
  onSelectItem: (itemId: number) => void;
};

function formatItemType(itemType: SemanticSearchResult["item_type"]): string {
  if (itemType === "url") {
    return "URL";
  }

  if (itemType === "pdf") {
    return "PDF";
  }

  return "Text";
}

export function SemanticSearchPanel({
  isLoading,
  errorMessage,
  results,
  onSearch,
  onSelectItem
}: SemanticSearchPanelProps) {
  const [query, setQuery] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSearch(query);
  }

  return (
    <section className="panel semantic-panel">
      <div className="section-heading">
        <h2>Semantic search</h2>
        <p>Find related chunks across saved items and jump back to the original record.</p>
      </div>

      <form className="semantic-search-form" onSubmit={(event) => void handleSubmit(event)}>
        <label className="field-label" htmlFor="semantic-query">
          Semantic query
        </label>
        <div className="semantic-search-row">
          <input
            id="semantic-query"
            className="search-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. Louisiana property insurance"
            type="search"
            value={query}
          />
          <button className="primary-button" disabled={isLoading} type="submit">
            {isLoading ? "Searching..." : "Search semantically"}
          </button>
        </div>
      </form>

      {errorMessage ? <p className="form-error">{errorMessage}</p> : null}

      {!errorMessage && !isLoading && results.length === 0 ? (
        <p className="status-message">No semantic matches yet. Run a query after saving a few items.</p>
      ) : null}

      <div className="semantic-results">
        {results.map((result) => (
          <button
            key={result.chunk_id}
            className="semantic-result"
            onClick={() => onSelectItem(result.item_id)}
            type="button"
          >
            <div className="semantic-result-header">
              <span className="library-item-title">{result.item_title}</span>
              <span className="library-item-badge">{formatItemType(result.item_type)}</span>
            </div>
            <p className="semantic-result-score">Score {result.score.toFixed(4)}</p>
            <p className="semantic-result-chunk">{result.chunk_text}</p>
          </button>
        ))}
      </div>
    </section>
  );
}
