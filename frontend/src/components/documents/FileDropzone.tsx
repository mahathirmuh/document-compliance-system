import { FileArchive, FileSpreadsheet, FileText, UploadCloud, X } from 'lucide-react';
import {
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from 'react';

import {
  documentFileAccept,
  documentMaxFileSizeBytes,
  formatFileSize,
  getDocumentFileExtension,
  validateDocumentFile,
} from '../../utils/documentFiles';

export interface RejectedDocumentFile {
  fileName: string;
  reason: string;
}

interface FileDropzoneProps {
  files: readonly File[];
  onFilesChange: (files: File[]) => void;
  multiple?: boolean;
  maximumSize?: number;
  maximumFiles?: number;
  disabled?: boolean;
  label?: string;
}

const fileIcon = (name: string) => {
  const extension = getDocumentFileExtension(name);
  if (extension === 'xlsx') {
    return FileSpreadsheet;
  }
  if (extension === 'docx') {
    return FileText;
  }
  return FileArchive;
};

export function FileDropzone({
  disabled = false,
  files,
  label = 'Select document file',
  maximumFiles = 1,
  maximumSize = documentMaxFileSizeBytes,
  multiple = false,
  onFilesChange,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [rejections, setRejections] = useState<RejectedDocumentFile[]>([]);

  const acceptFiles = (incoming: readonly File[]): void => {
    const accepted: File[] = [];
    const rejected: RejectedDocumentFile[] = [];

    incoming.forEach((file) => {
      const validation = validateDocumentFile(file, maximumSize);
      if (!validation.valid) {
        rejected.push({
          fileName: file.name,
          reason: validation.message ?? 'File is not supported.',
        });
        return;
      }
      accepted.push(file);
    });

    const combined = multiple ? [...files, ...accepted] : accepted.slice(0, 1);
    const unique = combined.filter(
      (file, index, all) =>
        all.findIndex(
          (candidate) =>
            candidate.name === file.name &&
            candidate.size === file.size &&
            candidate.lastModified === file.lastModified,
        ) === index,
    );
    if (unique.length > maximumFiles) {
      unique.slice(maximumFiles).forEach((file) => {
        rejected.push({
          fileName: file.name,
          reason: `A maximum of ${maximumFiles} files can be selected.`,
        });
      });
    }

    onFilesChange(unique.slice(0, maximumFiles));
    setRejections(rejected);
    if (inputRef.current) {
      inputRef.current.value = '';
    }
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>): void => {
    acceptFiles(Array.from(event.target.files ?? []));
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setDragActive(false);
    if (!disabled) {
      acceptFiles(Array.from(event.dataTransfer.files));
    }
  };

  const openPicker = (): void => {
    if (!disabled) {
      inputRef.current?.click();
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>): void => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openPicker();
    }
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={label}
        aria-disabled={disabled}
        onClick={openPicker}
        onKeyDown={handleKeyDown}
        onDragEnter={(event) => {
          event.preventDefault();
          if (!disabled) {
            setDragActive(true);
          }
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) {
            setDragActive(false);
          }
        }}
        onDrop={handleDrop}
        className={`group flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed px-6 py-10 text-center outline-none transition focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 ${
          dragActive
            ? 'border-blue-600 bg-blue-50'
            : 'border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50'
        } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept={documentFileAccept}
          multiple={multiple}
          disabled={disabled}
          onChange={handleInput}
          aria-label="Browse document files"
        />
        <span className="grid size-14 place-items-center rounded-2xl bg-white text-blue-700 shadow-sm ring-1 ring-slate-200">
          <UploadCloud className="size-7" aria-hidden="true" />
        </span>
        <p className="mt-4 text-sm font-semibold text-slate-950">
          Drop {multiple ? 'files' : 'a file'} here or browse
        </p>
        <p className="mt-1.5 text-xs leading-5 text-slate-500">
          PDF, DOCX, or XLSX · Up to {formatFileSize(maximumSize)}
          {multiple ? ` each · Maximum ${maximumFiles} files` : ''}
        </p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2" aria-label="Selected files">
          {files.map((file, index) => {
            const Icon = fileIcon(file.name);
            return (
              <li
                key={`${file.name}-${file.lastModified}-${index}`}
                className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {file.name}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {formatFileSize(file.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onFilesChange(files.filter((_, candidate) => candidate !== index));
                  }}
                  disabled={disabled}
                  aria-label={`Remove ${file.name}`}
                  className="grid size-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {rejections.length > 0 && (
        <div
          role="alert"
          className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800"
        >
          <p className="font-semibold">Some files were rejected</p>
          <ul className="mt-2 space-y-1">
            {rejections.map((rejection) => (
              <li key={`${rejection.fileName}-${rejection.reason}`}>
                <span className="font-medium">{rejection.fileName}:</span>{' '}
                {rejection.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
