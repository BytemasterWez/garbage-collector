import { FormEvent, useState } from "react";

type UrlComposerProps = {
  isSaving: boolean;
  onSave: (url: string) => Promise<boolean>;
};

export function UrlComposer({ isSaving, onSave }: UrlComposerProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!url.trim()) {
      setError("Paste a URL before saving.");
      return;
    }

    setError(null);
    const didSave = await onSave(url);
    if (didSave) {
      setUrl("");
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Save URL</h2>
        <p>Fetch a basic HTML page and store its title and visible text.</p>
      </div>

      <form className="composer-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="item-url">
          Source URL
        </label>
        <input
          id="item-url"
          className="search-input"
          type="url"
          value={url}
          onChange={(event) => {
            setUrl(event.target.value);
            if (error) {
              setError(null);
            }
          }}
          placeholder="https://example.com/article"
        />

        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={isSaving} type="submit">
          {isSaving ? "Saving..." : "Fetch and save"}
        </button>
      </form>
    </section>
  );
}
