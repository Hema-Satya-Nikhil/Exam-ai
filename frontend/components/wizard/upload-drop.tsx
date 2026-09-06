'use client';

import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { CheckCircle2, FileUp, Loader2, TriangleAlert, X } from 'lucide-react';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export function UploadDrop({
  accept,
  title,
  hint,
  status,
  fileName,
  busyLabel,
  error,
  onFile,
  onRemove
}: {
  accept: string;
  title: string;
  hint: string;
  status: UploadStatus;
  fileName?: string;
  busyLabel?: string;
  error?: string | null;
  onFile: (file: File) => void;
  onRemove?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onFile(file);
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={handleChange}
        data-testid="upload-input"
      />
      <div
        role="button"
        tabIndex={0}
        aria-label={`${title} — browse or drop a file`}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-2xl border-2 border-dashed bg-white/45 p-8 text-center shadow-inner backdrop-blur-sm transition-all duration-micro ease-standard ${
          dragging
            ? 'border-primary bg-primary-soft/40'
            : status === 'error'
              ? 'border-danger/40 bg-danger-soft/40'
              : status === 'success'
                ? 'border-success/40 bg-success-soft/40'
                : 'border-white/80 hover:border-primary/50 hover:bg-white/70'
        }`}
      >
        {status === 'uploading' ? (
          <div className="flex flex-col items-center gap-2 text-sm text-text-secondary">
            <Loader2 className="h-7 w-7 animate-spin text-text-muted" data-testid="upload-spinner" />
            <span>{busyLabel ?? 'Uploading and processing…'}</span>
          </div>
        ) : status === 'success' ? (
          <div className="flex flex-col items-center gap-2 text-sm text-success">
            <CheckCircle2 className="h-7 w-7 text-success" />
            <span className="font-medium">{title} ready</span>
            {fileName ? <span className="text-xs text-success">File: {fileName}</span> : null}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <FileUp className="h-7 w-7 text-text-muted" />
            <p className="text-sm font-medium text-text-primary">{title}</p>
            <p className="text-xs leading-5 text-text-muted">Drag & drop a file here, or click to browse</p>
            <p className="text-xs text-text-muted">{hint}</p>
          </div>
        )}
      </div>

      {error ? (
        <div className="mt-3 flex items-start justify-between gap-2 rounded-2xl border border-danger/25 bg-danger-soft px-4 py-3 text-sm text-danger">
          <div className="flex items-start gap-2">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="shrink-0 rounded-full border border-red-300 bg-white px-3 py-1 text-xs font-semibold text-danger hover:bg-red-100"
          >
            Try again
          </button>
        </div>
      ) : null}

      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text-primary"
        >
          <X className="h-3.5 w-3.5" /> Remove file
        </button>
      ) : null}

      {status === 'error' ? <UploadAlert label={title.replace(/[.!?]+$/, '')} /> : null}
    </div>
  );
}

function UploadAlert({ label }: { label: string }) {
  return null;
}