import { FormEvent, useState } from "react";

type ItemComposerProps = {
  isSaving: boolean;
  onSave: (content: string) => Promise<boolean>;
};

export function ItemComposer({ isSaving, onSave }: ItemComposerProps) {
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!content.trim()) {
      setError("Paste some text before saving.");
      return;
    }

    setError(null);
    const didSave = await onSave(content);
    if (didSave) {
      setContent("");
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Paste text</h2>
        <p>Save raw notes first. Organizing can come later.</p>
      </div>

      <form className="composer-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="item-content">
          Pasted text
        </label>
        <textarea
          id="item-content"
          className="composer-textarea"
          value={content}
          onChange={(event) => {
            setContent(event.target.value);
            if (error) {
              setError(null);
            }
          }}
          placeholder="Paste text here..."
          rows={10}
        />

        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={isSaving} type="submit">
          {isSaving ? "Saving..." : "Save to library"}
        </button>
      </form>
    </section>
  );
}
