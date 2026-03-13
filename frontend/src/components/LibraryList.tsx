import type { ItemSummary } from "../types/items";

type LibraryListProps = {
  items: ItemSummary[];
  selectedItemId: number | null;
  isLoading: boolean;
  hasError: boolean;
  onSelect: (itemId: number) => void;
};

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatItemType(itemType: ItemSummary["item_type"]): string {
  if (itemType === "url") {
    return "URL";
  }

  if (itemType === "pdf") {
    return "PDF";
  }

  return "Text";
}

export function LibraryList({
  items,
  selectedItemId,
  isLoading,
  hasError,
  onSelect
}: LibraryListProps) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Library</h2>
        <p>Newest saved items appear first.</p>
      </div>

      {isLoading ? <p className="status-message">Loading library...</p> : null}

      {!isLoading && !hasError && items.length === 0 ? (
        <p className="status-message">No items yet. Save your first pasted note.</p>
      ) : null}

      <div className="library-list">
        {items.map((item) => (
          <button
            key={item.id}
            className={`library-item ${selectedItemId === item.id ? "selected" : ""}`}
            onClick={() => onSelect(item.id)}
            type="button"
          >
            <span className="library-item-meta-row">
              <span className="library-item-title">{item.title}</span>
              <span className="library-item-badge">{formatItemType(item.item_type)}</span>
            </span>
            <span className="library-item-preview">{item.preview}</span>
            <span className="library-item-date">{formatDate(item.created_at)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
