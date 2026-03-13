import { useEffect, useState } from "react";

import { createItem, createPdfItem, createUrlItem, fetchItem, fetchItems } from "./api/items";
import { ItemComposer } from "./components/ItemComposer";
import { ItemDetailPanel } from "./components/ItemDetailPanel";
import { LibraryList } from "./components/LibraryList";
import { PdfComposer } from "./components/PdfComposer";
import { SearchBox } from "./components/SearchBox";
import { UrlComposer } from "./components/UrlComposer";
import type { ItemDetail, ItemSummary } from "./types/items";

export default function App() {
  const [items, setItems] = useState<ItemSummary[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [selectedItem, setSelectedItem] = useState<ItemDetail | null>(null);
  const [query, setQuery] = useState("");
  const [isListLoading, setIsListLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  useEffect(() => {
    void loadItems(query);
  }, [query]);

  useEffect(() => {
    if (selectedItemId === null) {
      setSelectedItem(null);
      return;
    }

    void loadItem(selectedItemId);
  }, [selectedItemId]);

  async function loadItems(searchQuery: string) {
    try {
      setIsListLoading(true);
      setPageError(null);
      const nextItems = await fetchItems(searchQuery);
      setItems(nextItems);

      if (nextItems.length === 0) {
        setSelectedItemId(null);
        return;
      }

      const itemStillExists = nextItems.some((item) => item.id === selectedItemId);
      if (!itemStillExists) {
        setSelectedItemId(nextItems[0].id);
      }
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to load items.");
    } finally {
      setIsListLoading(false);
    }
  }

  async function loadItem(itemId: number) {
    try {
      setIsDetailLoading(true);
      setPageError(null);
      setSelectedItem(null);
      const item = await fetchItem(itemId);
      setSelectedItem(item);
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to load item.");
      setSelectedItem(null);
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function handleSave(content: string): Promise<boolean> {
    try {
      setIsSaving(true);
      setPageError(null);
      const item = await createItem({ content });
      if (query) {
        setQuery("");
        await loadItems("");
      } else {
        await loadItems("");
      }
      setSelectedItemId(item.id);
      return true;
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to save item.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUrlSave(url: string): Promise<boolean> {
    try {
      setIsSaving(true);
      setPageError(null);
      const item = await createUrlItem({ url });
      if (query) {
        setQuery("");
        await loadItems("");
      } else {
        await loadItems("");
      }
      setSelectedItemId(item.id);
      return true;
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to save URL.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function handlePdfSave(file: File): Promise<boolean> {
    try {
      setIsSaving(true);
      setPageError(null);
      const item = await createPdfItem({ file });
      if (query) {
        setQuery("");
        await loadItems("");
      } else {
        await loadItems("");
      }
      setSelectedItemId(item.id);
      return true;
    } catch (error) {
      setPageError(error instanceof Error ? error.message : "Failed to save PDF.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Localhost thin slice</p>
          <h1>Garbage Collector</h1>
        </div>
        <p className="header-copy">
          Paste text, keep it locally, browse the library, and search by keyword.
        </p>
      </header>

      {pageError ? <p className="page-error">{pageError}</p> : null}

      <section className="top-grid">
        <ItemComposer isSaving={isSaving} onSave={handleSave} />
        <UrlComposer isSaving={isSaving} onSave={handleUrlSave} />
        <PdfComposer isSaving={isSaving} onSave={handlePdfSave} />
        <section className="panel">
          <div className="section-heading">
            <h2>Find items</h2>
            <p>Simple keyword search over saved titles and contents.</p>
          </div>
          <SearchBox query={query} onQueryChange={setQuery} />
        </section>
      </section>

      <section className="bottom-grid">
        <LibraryList
          items={items}
          selectedItemId={selectedItemId}
          isLoading={isListLoading}
          hasError={pageError !== null}
          onSelect={setSelectedItemId}
        />
        <ItemDetailPanel
          item={selectedItem}
          isLoading={isDetailLoading}
          hasError={pageError !== null}
        />
      </section>
    </main>
  );
}
