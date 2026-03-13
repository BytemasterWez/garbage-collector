import { ChangeEvent, FormEvent, useState } from "react";

type PdfComposerProps = {
  isSaving: boolean;
  onSave: (file: File) => Promise<boolean>;
};

export function PdfComposer({ isSaving, onSave }: PdfComposerProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null;
    setSelectedFile(nextFile);
    if (error) {
      setError(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setError("Choose a PDF file before uploading.");
      return;
    }

    setError(null);
    const didSave = await onSave(selectedFile);
    if (didSave) {
      setSelectedFile(null);
      const input = document.getElementById("item-pdf") as HTMLInputElement | null;
      if (input) {
        input.value = "";
      }
    }
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Upload PDF</h2>
        <p>Save a text-based PDF, keep the original file locally, and index its text.</p>
      </div>

      <form className="composer-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="item-pdf">
          PDF file
        </label>
        <input
          id="item-pdf"
          className="file-input"
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
        />

        {selectedFile ? <p className="selected-file">Selected: {selectedFile.name}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}

        <button className="primary-button" disabled={isSaving} type="submit">
          {isSaving ? "Uploading..." : "Upload and save"}
        </button>
      </form>
    </section>
  );
}
