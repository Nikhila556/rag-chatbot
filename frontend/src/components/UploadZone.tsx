import { useCallback, useState } from "react";
import { Upload, Loader2 } from "lucide-react";
import { uploadDocument } from "../api";

interface Props {
  onUploaded: () => void;
}

export function UploadZone({ onUploaded }: Props) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ALLOWED = [".pdf", ".docx", ".doc", ".txt"];

  const handleFile = useCallback(async (file: File) => {
    const ext = file.name.toLowerCase().match(/\.[^.]+$/)?.[0] ?? "";
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported file. Allowed: ${ALLOWED.join(", ")}`);
      return;
    }
    setError(null);
    setUploading(true);
    try {
      await uploadDocument(file);
      onUploaded();
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [onUploaded]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <div className="p-4 border-t border-gray-800">
      <label
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center gap-2 border-2 border-dashed rounded-xl p-5 cursor-pointer transition-colors ${dragging ? "border-sky-500 bg-sky-950" : "border-gray-700 hover:border-gray-500"}`}
      >
        <input
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
          disabled={uploading}
        />
        {uploading ? (
          <Loader2 size={20} className="text-sky-400 animate-spin" />
        ) : (
          <Upload size={20} className="text-gray-400" />
        )}
        <p className="text-xs text-gray-400 text-center">
          {uploading ? "Processing file…" : "Drop PDF, DOCX, or TXT here or click to upload"}
        </p>
      </label>
      {error && <p className="text-xs text-red-400 mt-1 text-center">{error}</p>}
    </div>
  );
}
