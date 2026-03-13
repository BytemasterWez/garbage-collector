import type { ItemDetail, RelatedItem } from "../types/items";

type ItemDetailPanelProps = {
  item: ItemDetail | null;
  isLoading: boolean;
  hasError: boolean;
  relatedItems: RelatedItem[];
  isRelatedLoading: boolean;
  relatedError: string | null;
  onSelectRelatedItem: (itemId: number) => void;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatItemType(value: "pasted_text" | "url" | "pdf"): string {
  if (value === "url") {
    return "URL";
  }

  if (value === "pdf") {
    return "PDF";
  }

  return "Text";
}

export function ItemDetailPanel({
  item,
  isLoading,
  hasError,
  relatedItems,
  isRelatedLoading,
  relatedError,
  onSelectRelatedItem
}: ItemDetailPanelProps) {
  const hasEntities =
    item &&
    (item.entities.people.length > 0 ||
      item.entities.organizations.length > 0 ||
      item.entities.places.length > 0 ||
      item.entities.dates.length > 0);

  return (
    <section className="panel detail-panel">
      <div className="section-heading">
        <h2>Item detail</h2>
        <p>Read the full saved text for the selected item.</p>
      </div>

      {isLoading ? <p className="status-message">Loading item...</p> : null}

      {!isLoading && !hasError && item === null ? (
        <p className="status-message">Select an item from the library to view it here.</p>
      ) : null}

      {item ? (
        <article className="detail-card">
          <h3>{item.title}</h3>
          <p className="detail-meta">Saved {formatDate(item.created_at)}</p>
          <p className="detail-meta">Item type: {item.item_type}</p>
          {item.source_filename ? (
            <p className="detail-source">Original filename: {item.source_filename}</p>
          ) : null}
          {item.source_url ? (
            <p className="detail-source">
              Source URL:{" "}
              <a href={item.source_url} rel="noreferrer" target="_blank">
                {item.source_url}
              </a>
            </p>
          ) : null}
          <section className="detail-section">
            <h4>Metadata</h4>
            <dl className="detail-grid">
              <div>
                <dt>Word count</dt>
                <dd>{item.metadata.word_count}</dd>
              </div>
              <div>
                <dt>Character count</dt>
                <dd>{item.metadata.character_count}</dd>
              </div>
              <div>
                <dt>Line count</dt>
                <dd>{item.metadata.line_count}</dd>
              </div>
              {item.metadata.hostname ? (
                <div>
                  <dt>Hostname</dt>
                  <dd>{item.metadata.hostname}</dd>
                </div>
              ) : null}
            </dl>
          </section>
          <section className="detail-section">
            <h4>Entities</h4>
            {hasEntities ? (
              <dl className="detail-grid">
                <div>
                  <dt>People</dt>
                  <dd>{item.entities.people.join(", ") || "None detected"}</dd>
                </div>
                <div>
                  <dt>Organizations</dt>
                  <dd>{item.entities.organizations.join(", ") || "None detected"}</dd>
                </div>
                <div>
                  <dt>Places</dt>
                  <dd>{item.entities.places.join(", ") || "None detected"}</dd>
                </div>
                <div>
                  <dt>Dates</dt>
                  <dd>{item.entities.dates.join(", ") || "None detected"}</dd>
                </div>
              </dl>
            ) : (
              <p className="status-message">No conservative entities were detected for this item.</p>
            )}
          </section>
          <section className="detail-section">
            <h4>Related items</h4>
            {isRelatedLoading ? <p className="status-message">Loading related items...</p> : null}
            {relatedError ? <p className="form-error">{relatedError}</p> : null}
            {!isRelatedLoading && !relatedError && relatedItems.length === 0 ? (
              <p className="status-message">No related items found yet for this item.</p>
            ) : null}
            <div className="related-items-list">
              {relatedItems.map((relatedItem) => (
                <button
                  key={relatedItem.item_id}
                  className="related-item"
                  onClick={() => onSelectRelatedItem(relatedItem.item_id)}
                  type="button"
                >
                  <div className="semantic-result-header">
                    <span className="library-item-title">{relatedItem.title}</span>
                    <span className="library-item-badge">{formatItemType(relatedItem.item_type)}</span>
                  </div>
                  <p className="semantic-result-score">Score {relatedItem.score.toFixed(4)}</p>
                  <p className="semantic-result-chunk">{relatedItem.matching_chunk_preview}</p>
                  <p className="detail-meta">{relatedItem.reason}</p>
                </button>
              ))}
            </div>
          </section>
          <pre className="detail-content">{item.content}</pre>
        </article>
      ) : null}
    </section>
  );
}
