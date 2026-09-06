'use client';

import { Edit3, Lock, RefreshCw, Save, Unlock } from 'lucide-react';

import { Badge } from '@/components/ui/badge';

export interface QuestionArticleProps {
  question: Record<string, any>;
  displayLabel: string;
  isEditing: boolean;
  editText: string;
  onEditTextChange: (value: string) => void;
  onSaveEdit: () => void;
  onEditStart: () => void;
  onToggleLock: () => void;
  instruction: string;
  onInstructionChange: (value: string) => void;
  onRegenerate: () => void;
  regenPending: boolean;
}

/**
 * Premium individual question card for the Review workspace.
 *
 * Visual hierarchy (per spec):
 *   Q<n>  <marks> marks
 *   Topic heading
 *   Question text (document-style readability)
 *   [metadata chips — secondary]
 *   Actions: Edit | Lock/Unlock
 *   Regeneration instruction field + Regenerate
 *
 * Metadata is never mixed into question_text.
 * Internal ids (choice_group_id, choice_member_id, source_references) are NOT printed.
 */
export function QuestionArticle({
  question, displayLabel, isEditing, editText,
  onEditTextChange, onSaveEdit, onEditStart, onToggleLock,
  instruction, onInstructionChange, onRegenerate, regenPending,
}: QuestionArticleProps) {
  const locked = Boolean(question.locked);
  const showUnsaved = isEditing;
  const showLockedHint = locked && !isEditing;

  return (
    <article
      data-testid="question-card"
      className="group relative rounded-lg border border-line bg-surface p-5 shadow-low transition-shadow duration-micro hover:shadow-medium"
    >
      {/* Header: Q-number + mark badge + lock state */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span
            data-testid="question-number"
            className="inline-flex items-center rounded-sm bg-primary px-3 py-1 text-metadata font-semibold tracking-[0.2em] text-white"
          >
            Q{displayLabel}
          </span>
          <Badge tone="neutral" className="!border-slate-200">
            {question.marks} marks
          </Badge>

          {locked ? (
            <span
              data-testid="lock-state"
              className="inline-flex items-center gap-1 rounded-full border border-success/30 bg-success-soft px-3 py-1 text-metadata font-medium text-success"
            >
              <Lock className="h-3.5 w-3.5" /> Locked
            </span>
          ) : (
                      <span
              data-testid="unlock-state"
              className="inline-flex items-center gap-1 rounded-full border border-warning/30 bg-warning-soft px-3 py-1 text-metadata font-medium text-warning"
            >
              Unlocked
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isEditing ? (
            <button
              type="button"
              onClick={onSaveEdit}
              data-testid="save-edit"
              className="inline-flex items-center gap-1.5 rounded-[0.5rem] bg-primary px-3 py-1 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-primary-hover focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <Save className="h-3.5 w-3.5" /> Save
            </button>
          ) : (
            <button
              type="button"
              onClick={onEditStart}
              data-testid="edit-question"
              className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-line bg-surface px-3 py-1 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
            >
              <Edit3 className="h-3.5 w-3.5" /> Edit
            </button>
          )}

          <button
            type="button"
            onClick={onToggleLock}
            disabled={regenPending}
            data-testid="lock-toggle"
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
          >
            {locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
            {locked ? 'Unlock' : 'Lock'}
          </button>
        </div>
      </header>

      {/* Body: topic heading + question text */}
      <div className="mt-3 space-y-2">
        <h2
          data-testid="question-topic"
          className="text-section-heading text-text-primary"
        >
          {question.topic || `Question ${displayLabel}`}
        </h2>

        {showUnsaved ? (
          <Badge tone="warning" data-testid="unsaved-changes" className="text-xs">
            Unsaved changes
          </Badge>
        ) : null}

        {showLockedHint ? (
          <span
            data-testid="locked-hint"
            className="text-metadata text-danger"
          >
            This question is locked and cannot be regenerated.
          </span>
        ) : null}
      </div>

      {isEditing ? (
        <textarea
          value={editText}
          onChange={(event) => onEditTextChange(event.target.value)}
          aria-label="Question text"
          data-testid="edit-textarea"
          className="mt-3 w-full rounded-[0.5rem] border border-line bg-surface p-3 text-body text-text-primary outline-none transition-colors duration-micro placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          rows={3}
        />
      ) : (
        <p
          data-testid="question-text"
          className="mt-3 whitespace-pre-wrap text-body leading-7 text-text-primary"
        >
          {question.question_text || 'No question text yet.'}
        </p>
      )}

      {/* Metadata chips — secondary, never internal ids */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-metadata text-text-muted">
          Difficulty: {question.difficulty} · Type: {question.question_type}
          {(question.choice_group || question.choice_group_id) ? ` · Choice: ${question.choice_group || question.choice_group_id}` : ''}
        </span>
      </div>

      {/* Regeneration controls */}
      <div className="mt-4 flex items-end gap-3 border-t border-line pt-4">
        <div className="flex-1">
          <label
            htmlFor={`regen-instructions-${displayLabel.replace(/[^a-z0-9]/gi, '')}`}
            className="sr-only"
          >
            Regeneration instructions
          </label>
          <input
            id={`regen-instructions-${displayLabel.replace(/[^a-z0-9]/gi, '')}`}
            value={instruction}
            onChange={(event) => onInstructionChange(event.target.value)}
            placeholder="Optional: what to improve in the rewrite"
            aria-label="Regeneration instructions"
            data-testid="regen-input"
            className="w-full rounded-[0.5rem] border border-line bg-surface px-3 py-2 text-body text-text-primary outline-none transition-colors duration-micro placeholder:text-text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={locked || regenPending}
          data-testid="regenerate-question"
          className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-primary/40 bg-transparent px-4 py-2 text-metadata font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        >
          {regenPending ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Regenerating…
            </>
          ) : (
            <>
              <RefreshCw className="h-3.5 w-3.5" /> Regenerate
            </>
          )}
        </button>
      </div>
    </article>
  );
}

