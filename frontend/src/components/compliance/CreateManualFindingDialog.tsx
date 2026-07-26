import { useEffect, useState } from 'react';

import {
  findingSeverities,
  type FindingSeverity,
  type ManualFindingRequest,
} from '../../types/finding';

interface ManualFindingDefaults {
  documentId?: string;
  documentRevisionId?: string;
  documentFileId?: string;
}

export function CreateManualFindingDialog({
  defaults = {},
  errorMessage,
  isOpen,
  isPending,
  onClose,
  onSubmit,
}: {
  isOpen: boolean;
  isPending: boolean;
  defaults?: ManualFindingDefaults;
  errorMessage?: string | null;
  onClose: () => void;
  onSubmit: (payload: ManualFindingRequest) => void;
}) {
  const [documentId, setDocumentId] = useState('');
  const [documentRevisionId, setDocumentRevisionId] = useState('');
  const [documentFileId, setDocumentFileId] = useState('');
  const [severity, setSeverity] = useState<FindingSeverity>('MAJOR');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [recommendation, setRecommendation] = useState('');
  const [sourceReference, setSourceReference] = useState('');
  const [pageNumber, setPageNumber] = useState('');
  const [worksheetName, setWorksheetName] = useState('');
  const [cellCoordinate, setCellCoordinate] = useState('');
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    setDocumentId(defaults.documentId ?? '');
    setDocumentRevisionId(defaults.documentRevisionId ?? '');
    setDocumentFileId(defaults.documentFileId ?? '');
    setSeverity('MAJOR');
    setTitle('');
    setDescription('');
    setRecommendation('');
    setSourceReference('');
    setPageNumber('');
    setWorksheetName('');
    setCellCoordinate('');
    setValidationMessage(null);
  }, [
    defaults.documentFileId,
    defaults.documentId,
    defaults.documentRevisionId,
    isOpen,
  ]);

  if (!isOpen) {
    return null;
  }

  const submit = (): void => {
    if (
      !documentId.trim() ||
      !documentRevisionId.trim() ||
      !documentFileId.trim() ||
      !title.trim() ||
      !description.trim()
    ) {
      setValidationMessage(
        'Document, revision, file, title, and description are required.',
      );
      return;
    }
    const parsedPage = pageNumber ? Number(pageNumber) : null;
    if (parsedPage !== null && (!Number.isInteger(parsedPage) || parsedPage < 1)) {
      setValidationMessage('Page number must be a positive whole number.');
      return;
    }
    onSubmit({
      documentId: documentId.trim(),
      documentRevisionId: documentRevisionId.trim(),
      documentFileId: documentFileId.trim(),
      severity,
      title: title.trim(),
      description: description.trim(),
      recommendation: recommendation.trim() || null,
      sourceReference: sourceReference.trim() || null,
      pageNumber: parsedPage,
      worksheetName: worksheetName.trim() || null,
      cellCoordinate: cellCoordinate.trim() || null,
    });
  };

  return (
    <div
      className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-slate-950/50 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="manual-finding-title"
    >
      <div className="my-6 w-full max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <h2 id="manual-finding-title" className="text-lg font-semibold text-slate-950">
          Create manual finding
        </h2>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          Record a review finding without changing extracted or source document content.
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <TextInput
            label="Document ID"
            value={documentId}
            disabled={defaults.documentId !== undefined}
            onChange={setDocumentId}
          />
          <TextInput
            label="Revision ID"
            value={documentRevisionId}
            disabled={defaults.documentRevisionId !== undefined}
            onChange={setDocumentRevisionId}
          />
          <TextInput
            label="Document file ID"
            value={documentFileId}
            disabled={defaults.documentFileId !== undefined}
            onChange={setDocumentFileId}
          />
          <label className="block text-xs font-semibold text-slate-700">
            Severity
            <select
              value={severity}
              onChange={(event) => setSeverity(event.target.value as FindingSeverity)}
              className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm"
            >
              {findingSeverities.map((candidate) => (
                <option key={candidate} value={candidate}>
                  {candidate}
                </option>
              ))}
            </select>
          </label>
          <div className="sm:col-span-2">
            <TextInput label="Title" value={title} onChange={setTitle} />
          </div>
          <label className="block text-xs font-semibold text-slate-700 sm:col-span-3">
            Description
            <textarea
              rows={4}
              maxLength={4000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-xs font-semibold text-slate-700 sm:col-span-3">
            Recommendation
            <textarea
              rows={3}
              maxLength={4000}
              value={recommendation}
              onChange={(event) => setRecommendation(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <TextInput
            label="Source reference"
            value={sourceReference}
            onChange={setSourceReference}
          />
          <TextInput
            label="Page number"
            type="number"
            value={pageNumber}
            onChange={setPageNumber}
          />
          <TextInput
            label="Worksheet"
            value={worksheetName}
            onChange={setWorksheetName}
          />
          <TextInput
            label="Cell coordinate"
            value={cellCoordinate}
            onChange={setCellCoordinate}
          />
        </div>
        {(validationMessage || errorMessage) && (
          <p role="alert" className="mt-3 text-xs text-rose-700">
            {validationMessage ?? errorMessage}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            className="min-h-10 rounded-xl border border-slate-300 px-4 text-sm font-semibold text-slate-700 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={isPending}
            className="min-h-10 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {isPending ? 'Creating…' : 'Create Finding'}
          </button>
        </div>
      </div>
    </div>
  );
}

function TextInput({
  disabled = false,
  label,
  onChange,
  type = 'text',
  value,
}: {
  label: string;
  value: string;
  type?: 'text' | 'number';
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-semibold text-slate-700">
      {label}
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 min-h-11 w-full rounded-xl border border-slate-300 px-3 text-sm disabled:bg-slate-100"
      />
    </label>
  );
}
