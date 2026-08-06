import { useEffect, useRef, useState } from "react";
import type { DocumentInfo } from "../types";
import { listDocuments, uploadDocument } from "../api/client";

const ACCEPTED_EXTENSIONS = ".md,.txt,.pdf";

/**
 * Shows which HR documents are currently indexed, and lets an admin add a
 * new one on the fly. Pulled from GET /api/documents, which reflects
 * whatever scripts/ingest_docs.py last indexed OR whatever's been uploaded
 * here -- both write to the same place (see backend/app/api/routes/documents.py).
 *
 * Uploading does NOT touch ChatWindow's state at all (separate component,
 * separate local state) -- an in-progress conversation is completely
 * unaffected by a document upload happening alongside it, and the newly
 * uploaded document becomes answerable on the very next question asked
 * (see the "incremental indexing" note in backend/app/rag/chain.py).
 */
export default function Sidebar() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function refreshDocuments() {
    listDocuments()
      .then((result) => {
        setDocs(result);
        setLoadError(null);
      })
      .catch(() => setLoadError("Could not load indexed documents."));
  }

  useEffect(refreshDocuments, []);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset the input immediately so selecting the same filename twice in a
    // row still fires a change event (browsers otherwise suppress it).
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const result = await uploadDocument(file);
      setUploadSuccess(`Added "${result.title}" (${result.chunk_count} chunks) -- ready to ask about now.`);
      refreshDocuments();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <aside className="sidebar">
      <h2>HR Assistant</h2>
      <p className="sidebar__hint">Ask about onboarding, benefits, leave, or company policy.</p>

      <h3>Indexed documents</h3>
      {loadError && <p className="sidebar__error">{loadError}</p>}
      {!loadError && docs.length === 0 && (
        <p className="sidebar__hint">
          None yet. Upload one below, or run <code>python scripts/ingest_docs.py</code> in the backend.
        </p>
      )}
      <ul className="sidebar__doc-list">
        {docs.map((d) => (
          <li key={d.filename}>
            {d.title} <span className="sidebar__doc-meta">({d.chunk_count} chunks)</span>
          </li>
        ))}
      </ul>

      <h3>Add a document</h3>
      <label className={`upload-button ${isUploading ? "upload-button--disabled" : ""}`}>
        {isUploading ? "Uploading & indexing…" : "Upload .md / .txt / .pdf"}
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={handleFileSelected}
          disabled={isUploading}
          hidden
        />
      </label>
      {uploadError && <p className="sidebar__error">{uploadError}</p>}
      {uploadSuccess && <p className="sidebar__success">{uploadSuccess}</p>}
    </aside>
  );
}
