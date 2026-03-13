import type { ItemDetail } from "../types/items";

type ItemDetailPanelProps = {
  item: ItemDetail | null;
  isLoading: boolean;
  hasError: boolean;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function ItemDetailPanel({ item, isLoading, hasError }: ItemDetailPanelProps) {
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
          <pre className="detail-content">{item.content}</pre>
        </article>
      ) : null}
    </section>
  );
}
