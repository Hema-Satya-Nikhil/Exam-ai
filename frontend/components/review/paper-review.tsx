'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  Download,
  Edit3,
  Loader2,
  Lock,
  RefreshCw,
  Unlock
} from 'lucide-react';

import { Badge, StatusBadge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/contexts/auth-context';
import {
  clusterGroupsByChoice,
  getBlockingValidationIssues,
  getPartAHeader,
  getPartAQuestions,
  getPartBGroups,
  getValidationWarnings,
  hasPartLevelChoice,
  isCompositePaper,
  partDisplayLabel,
  partKey,
  questionActionKey,
  questionIdentity,
} from '@/lib/composite-review';
import {
  listPaperDownloads,
  listPaperVersions,
  restorePaperVersion
} from '@/lib/api';
import {
  usePaperDraft,
  usePaperExport,
  usePaperLock,
  usePaperQuestionUpdate,
  usePaperRegeneration,
  usePaperUnlock
} from '@/hooks/use-paper-review';

export function PaperReview() {
  const { user, loading: authLoading } = useAuth();
  const searchParams = useSearchParams();
  const paperId = searchParams.get('paper_id');

  const { data: paperDraft, isLoading, isError } = usePaperDraft(paperId ?? '');
  const lockMutation = usePaperLock();
  const unlockMutation = usePaperUnlock();
  const regenerateMutation = usePaperRegeneration();
  const updateQuestionMutation = usePaperQuestionUpdate();
  const exportMutation = usePaperExport();

  const [editingQuestionKey, setEditingQuestionKey] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [regenerationInstructions, setRegenerationInstructions] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<{ tone: 'ok' | 'error'; message: string } | null>(null);
  const [referenceDraft, setReferenceDraft] = useState<any>(null);
  const [versions, setVersions] = useState<Array<{ id: string; version_number: number; paper_json: Record<string, unknown> }>>([]);
  const [downloads, setDownloads] = useState<Array<{ version_id: string; version_number: number; pdf_available: boolean; docx_available: boolean }>>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [restoringVersion, setRestoringVersion] = useState<string | null>(null);

  const draft = paperDraft ?? referenceDraft;
  const status: string = draft?.status ?? 'draft';
  const paperJson = draft?.paper_json ?? {};
  const questions: Array<Record<string, any>> = paperJson.questions ?? [];

  useEffect(() => {
    if (!paperId || !user) return;
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    Promise.all([listPaperVersions(paperId), listPaperDownloads(paperId)])
      .then(([versionResult, downloadResult]) => {
        if (cancelled) return;
        setVersions(versionResult.versions);
        setDownloads(downloadResult.downloads);
      })
      .catch((error: unknown) => {
        if (!cancelled) setHistoryError(messageOf(error));
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => { cancelled = true; };
  }, [paperId, user]);

  async function restoreVersion(versionId: string) {
    if (!paperId || restoringVersion) return;
    setRestoringVersion(versionId);
    try {
      await restorePaperVersion(paperId, versionId);
      const refreshed = await listPaperVersions(paperId);
      setVersions(refreshed.versions);
      flash('ok', 'Version restored as a new auditable version.');
    } catch (error) {
      flash('error', messageOf(error));
    } finally {
      setRestoringVersion(null);
    }
  }

  const isComposite = isCompositePaper(paperJson);
  const partAHeader = getPartAHeader(paperJson);
  const partAQuestions = isComposite ? getPartAQuestions(paperJson) : [];
  const partBClusters = isComposite ? clusterGroupsByChoice(getPartBGroups(paperJson)) : [];

  function flash(tone: 'ok' | 'error', message: string) {
    setFeedback({ tone, message });
  }

  function toggleLock(question: Record<string, any>) {
    if (!paperId) return;
    if (lockMutation.isPending || unlockMutation.isPending) return;
    const target = questionIdentity(question);

    const mutate = question.locked ? unlockMutation : lockMutation;
    mutate.mutate(
      { paper_id: paperId, question: target },
      {
        onSuccess: (draft: any) => setReferenceDraft(draft),
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function saveEdit(question: Record<string, any>) {
    if (!paperId) return;
    updateQuestionMutation.mutate(
      { paper_id: paperId, question: questionIdentity(question), updates: { question_text: editText } as never },
      {
        onSuccess: (draft: any) => {
          setReferenceDraft(draft);
          setEditingQuestionKey(null);
          flash('ok', 'Question text updated.');
        },
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function handleRegenerate(question: Record<string, any>) {
    if (!paperId) return;
    const key = questionActionKey(questionIdentity(question));
    const instructions = regenerationInstructions[key] ?? '';
    regenerateMutation.mutate(
      { paper_id: paperId, question: questionIdentity(question), instructions },
      {
        onSuccess: (draft: any) => {
          setReferenceDraft(draft);
          flash('ok', `Question ${key} regenerated.`);
        },
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function handleExport(format: 'pdf' | 'docx') {
    if (!paperId) return;
    if (blockingIssues.length > 0) {
      flash('error', 'Resolve the highlighted validation issues before exporting.');
      return;
    }
    exportMutation.mutate(
      { paper_id: paperId, format },
      {
        onSuccess: () => flash('ok', `${format.toUpperCase()} download started.`),
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  // Final-check state — derived from the PERSISTED validation record
  // (paper_json.validation), never from a manual approval action. Composite
  // papers use the composite shape (errors/warnings); legacy flat papers keep
  // their existing ValidationSummary shape.
  const blockingIssues: string[] = isComposite
    ? getBlockingValidationIssues(paperJson)
    : (Array.isArray(paperJson.validation?.issues)
        ? paperJson.validation.issues
            .filter((issue: any) => issue?.severity === 'error')
            .map((issue: any) => String(issue?.message ?? 'Validation issue'))
        : paperJson.validation?.passed === false
          ? ['Paper validation has not passed yet.']
          : []);
  const warnings: string[] = isComposite ? getValidationWarnings(paperJson) : [];
  const finalCheckPassed = blockingIssues.length === 0;

  const totalMarks = isComposite
    ? Number(paperJson.total_marks || 0)
    : questions.reduce((sum, question) => sum + Number(question.marks || 0), 0);
  const lockedCount = questions.filter((question) => Boolean(question.locked)).length;

  function renderQuestion(req: Record<string, any>, displayLabel?: string) {
    const key = questionActionKey(questionIdentity(req));
    return (
      <QuestionArticle
        key={key}
        question={req}
        displayLabel={displayLabel ?? String(Number(req.question_number))}
        isEditing={editingQuestionKey === key}
        editText={editText}
        onEditTextChange={setEditText}
        onSaveEdit={() => saveEdit(req)}
        onEditStart={() => {
          setEditingQuestionKey(key);
          setEditText(String(req.question_text ?? ''));
        }}
        onToggleLock={() => toggleLock(req)}
        instruction={regenerationInstructions[key] ?? ''}
        onInstructionChange={(value) =>
          setRegenerationInstructions((current) => ({ ...current, [key]: value }))
        }
        onRegenerate={() => handleRegenerate(req)}
        regenPending={regenerateMutation.isPending}
      />
    );
  }

  if (authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-md space-y-3">
          <Skeleton className="h-7 w-56" />
          <Skeleton className="h-4 w-80 max-w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background text-text-primary">
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">Review Question Paper</p>
            <h1 className="text-heading tracking-tight text-text-primary">{draft?.title || 'Question paper'}</h1>
            <p className="mt-1 text-small text-text-secondary">Review, refine, and export your examination paper.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {draft && !isLoading && !isError ? (
              <span data-testid="review-status" className="inline-flex items-center">
                <Badge tone={finalCheckPassed ? 'success' : 'danger'}>{finalCheckPassed ? 'Valid' : 'Needs attention'}</Badge>
              </span>
            ) : null}
            <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-[0.5rem] border border-line bg-surface px-4 py-2 text-small font-semibold text-text-secondary transition-colors duration-micro ease-standard hover:bg-slate-50">
              <ArrowLeft className="h-4 w-4" /> Back to Dashboard
            </Link>
          </div>
        </div>

        {!paperId ? (
          <div className="mt-8 rounded-lg border border-dashed border-line bg-surface p-10 text-center">
            <h2 className="text-lg font-semibold text-slate-900">No paper selected</h2>
            <p className="mt-2 text-sm text-slate-600">Generate a paper first, then open it here for review.</p>
            <Link href="/create" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Create a paper
            </Link>
          </div>
        ) : isLoading ? (
          <div className="mt-8 rounded-lg border border-line bg-surface p-8 shadow-low">
            <div className="space-y-3">
              <Skeleton className="h-7 w-64" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          </div>
        ) : isError || !draft ? (
          <div className="mt-8 rounded-lg border border-danger/25 bg-danger-soft p-10 text-center">
            <h2 className="text-body font-semibold text-danger">Unable to load this question paper.</h2>
            <p className="mt-2 text-small text-danger">It may have been created in a different session. Please try again.</p>
            <button
              type="button"
              onClick={() => { if (typeof window !== 'undefined') window.location.reload(); }}
              className="mt-5 inline-flex rounded-[0.5rem] bg-primary px-5 py-2.5 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover"
            >
              Retry
            </button>
            <Link href="/create" className="mt-3 block text-small font-medium text-primary hover:underline">Create a new paper</Link>
          </div>
        ) : !user ? (
          <div className="mt-8 rounded-lg border border-warning/25 bg-warning-soft p-10 text-center">
            <h2 className="text-lg font-semibold text-amber-900">Sign in to review papers</h2>
            <p className="mt-2 text-sm text-amber-800">Approval and export require a faculty or administrator account.</p>
            <Link href="/login" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Sign in
            </Link>
          </div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-5">
              <div className="rounded-lg border border-line bg-surface p-4 shadow-low" data-testid="paper-summary">
                <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">Paper summary</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(paperJson.subject_name || paperJson.subject || draft?.subject) ? (
                    <Badge tone="primary">{paperJson.subject_name || paperJson.subject || draft?.subject}</Badge>
                  ) : null}
                  {(paperJson.exam_type || paperJson.exam_title || draft?.exam_type) ? (
                    <Badge tone="neutral">{paperJson.exam_type || paperJson.exam_title || draft?.exam_type}</Badge>
                  ) : null}
                  <Badge tone="neutral">{totalMarks} Marks</Badge>
                  <Badge tone="neutral">{paperJson.duration_minutes || '—'} Minutes</Badge>
                  <Badge tone="neutral">{questions.length} Questions</Badge>
                  <StatusBadge status={status} />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-4">
                <StatCard label="Status" value={statusLabel(status)} />
                <StatCard label="Total marks" value={`${totalMarks}`} />
                <StatCard label="Questions" value={String(questions.length)} />
                <StatCard label="Locked" value={String(lockedCount)} />
              </div>

              {feedback ? (
                <div
                  role={feedback.tone === 'error' ? 'alert' : 'status'}
                  className={`rounded-lg border px-4 py-3 text-small ${
                    feedback.tone === 'ok' ? 'border-success/25 bg-success-soft text-success' : 'border-danger/25 bg-danger-soft text-danger'
                  }`}
                >
                  {feedback.message}
                </div>
              ) : null}

              {questions.length === 0 && !isComposite ? (
                <div className="rounded-lg border border-dashed border-line bg-surface p-10 text-center">
                  <p className="text-sm text-slate-600">This paper has no questions yet.</p>
                </div>
              ) : isComposite ? (
                <div className="space-y-8" data-testid="composite-exam">
                  {/* PART A - SHORT ANSWER */}
                  <section data-testid="part-a-section" className="space-y-4">
                    <PartBanner name="PART A — SHORT ANSWER"
                      meta={`${partAHeader.questionCount} × ${partAHeader.marksPerQuestion} Marks · ${partAHeader.totalMarks} Marks · ${partAHeader.durationMinutes ?? '—'} Minutes`} />
                    {partAQuestions.map((question) => renderQuestion(question))}
                  </section>

                  {/* PART B - MAIN QUESTION PAPER */}
                  <section data-testid="part-b-section" className="space-y-4">
                    <PartBanner name="PART B — MAIN QUESTION PAPER"
                      meta={`${Number(paperJson.parts?.part_b?.total_marks || 0)} Marks · ${Number(paperJson.parts?.part_b?.duration_minutes || 0)} Minutes`} />

                    {partBClusters.map((cluster, clusterIndex) => (
                      <div key={cluster.choiceGroupId ?? `standalone-${clusterIndex}`}
                        data-testid={cluster.choiceGroupId ? 'choice-cluster' : 'standalone-cluster'}
                        className="space-y-4">
                        {cluster.groups.map((group, groupIndex) => {
                          const betweenGroups = cluster.choiceGroupId && groupIndex > 0 ? (
                            <OrDivider />
                          ) : null;
                          const parts = Array.isArray(group.parts) ? group.parts : []
                          const partLevel = hasPartLevelChoice(group)
                          return (
                            <div key={String(group.group_number)}>
                              {betweenGroups}
                              <div
                                data-testid={cluster.choiceGroupId ? 'or-alternative' : undefined}
                                className="rounded-lg border border-line bg-surface p-5 shadow-low">
                              <h3 data-testid="group-header"
                                className="text-small font-bold uppercase tracking-[0.2em] text-text-secondary">
                                Question Group {group.group_number}
                                {cluster.choiceGroupId && cluster.groups.length > 1 ? ' — choose ONE' : ''}
                              </h3>
                              {parts.map((part, partIndex) => (
                                <div key={partKey(Number(group.group_number), part)}>
                                  {partLevel && partIndex > 0 ? <OrDivider /> : null}
                                  <div className="my-3 flex items-center gap-2">
                                    <span data-testid="part-label"
                                      className="rounded-pill border border-line bg-surface px-3 py-0.5 text-metadata font-bold text-text-primary">
                                      {partDisplayLabel(Number(group.group_number), part)} · {part.marks} Marks
                                    </span>
                                  </div>
                                  {renderQuestion(part, `${group.group_number}${part.part_label ?? ''}`)}
                                </div>
                              ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    ))}
                  </section>
                </div>
              ) : (
                questions.map((question) => renderQuestion(question))
              )}
            </div>

            <aside className="space-y-5">
              <div className="rounded-lg border border-line bg-surface p-5 shadow-low">
                <p className="text-sm font-medium text-slate-500">Final Check</p>
                <ul className="mt-3 space-y-2 text-sm" data-testid="final-check-list">
                  <li className="flex items-center gap-2 text-slate-700">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Syllabus confirmed
                  </li>
                  <li className="flex items-center gap-2 text-slate-700">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Paper structure valid
                  </li>
                  {finalCheckPassed ? (
                    <li className="flex items-center gap-2 text-slate-700" data-testid="final-check-passed">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Question validation passed
                    </li>
                  ) : (
                    <li className="text-sm" data-testid="final-check-blocked">
                      <p className="flex items-center gap-2 font-semibold text-rose-700">
                        Question distribution needs attention.
                      </p>
                      <ul className="mt-1 list-disc pl-5 text-xs leading-5 text-rose-700">
                        {blockingIssues.slice(0, 5).map((issue, index) => (
                          <li key={index}>{issue}</li>
                        ))}
                      </ul>
                      <p className="mt-1 text-xs text-rose-600">
                        Resolve the highlighted validation issues before exporting.
                      </p>
                    </li>
                  )}
                </ul>
                {warnings.length > 0 && finalCheckPassed ? (
                  <div className="mt-3" data-testid="final-check-warnings">
                    <p className="text-xs font-semibold uppercase tracking-wider text-amber-700">
                      Warnings
                    </p>
                    <ul className="mt-1 list-disc pl-5 text-xs leading-5 text-amber-700">
                      {warnings.slice(0, 5).map((warning, index) => (
                        <li key={index}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>

              <div className="rounded-lg border border-line bg-surface p-5 shadow-low" data-testid="version-history">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium text-slate-500">Version History</p>
                  <span className="text-xs text-slate-400">{versions.length} version{versions.length === 1 ? '' : 's'}</span>
                </div>
                {historyLoading ? <p className="mt-3 text-xs text-slate-500">Loading history…</p> : null}
                {historyError ? <p className="mt-3 text-xs text-rose-600" role="alert">{historyError}</p> : null}
                {!historyLoading && !historyError && versions.length === 0 ? <p className="mt-3 text-xs text-slate-500">No saved versions.</p> : null}
                <div className="mt-3 space-y-2">
                  {versions.map((version) => (
                    <div key={version.id} className="flex items-center justify-between gap-2 rounded-md border border-line px-3 py-2 text-xs">
                      <span>Version {version.version_number}</span>
                      {version.id === versions[0]?.id ? <Badge tone="success">Current</Badge> : (
                        <button type="button" disabled={restoringVersion !== null} onClick={() => void restoreVersion(version.id)} className="rounded-md border border-line px-2 py-1 font-semibold text-primary disabled:opacity-50">
                          {restoringVersion === version.id ? 'Restoring…' : 'Restore'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-lg border border-line bg-surface p-5 shadow-low">
                <p className="text-sm font-medium text-slate-500">Export</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  {finalCheckPassed
                    ? 'Download the validated paper as PDF or DOCX. You can export the same version as many times as needed.'
                    : 'Resolve the highlighted validation issues before exporting.'}
                </p>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleExport('pdf')}
                    disabled={!finalCheckPassed || exportMutation.isPending}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    <Download className="h-3.5 w-3.5" /> PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('docx')}
                    disabled={!finalCheckPassed || exportMutation.isPending}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    <Download className="h-3.5 w-3.5" /> DOCX
                  </button>
                </div>
                {exportMutation.isPending ? (
                  <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> Preparing download…
                  </p>
                ) : null}
                <div className="mt-4 border-t border-line pt-3" data-testid="download-center">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Download Center</p>
                  {downloads.length === 0 ? <p className="mt-2 text-xs text-slate-500">No export history yet.</p> : (
                    <ul className="mt-2 space-y-1 text-xs text-slate-600">
                      {downloads.map((item) => <li key={item.version_id}>Version {item.version_number}: {item.pdf_available ? 'PDF' : ''}{item.pdf_available && item.docx_available ? ' · ' : ''}{item.docx_available ? 'DOCX' : ''}</li>)}
                    </ul>
                  )}
                </div>
              </div>
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3 shadow-low">
      <p className="text-metadata uppercase tracking-[0.18em] text-text-muted">{label}</p>
      <p className="mt-1 text-body font-semibold text-text-primary">{value}</p>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="rounded-pill border border-line bg-surface px-2.5 py-0.5 text-metadata font-medium text-text-secondary">{children}</span>;
}

function statusLabel(status: string): string {
  switch (status) {
    case 'approved':
      return 'Approved';
    case 'under_review':
      return 'Under review';
    case 'exported':
      return 'Exported';
    default:
      return 'Draft';
  }
}

function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Something went wrong. Please try again.';
}

function OrDivider() {
  return (
    <div role="separator" aria-label="OR" data-testid="or-divider"
      className="my-5 flex items-center gap-3">
      <span className="h-0.5 flex-1 bg-slate-300" />
      <span data-testid="or-label"
        className="rounded-pill border-2 border-primary bg-surface px-6 py-1.5 text-small font-extrabold uppercase tracking-[0.3em] text-primary shadow-low">
        OR
      </span>
      <span className="h-0.5 flex-1 bg-slate-300" />
    </div>
  );
}

function PartBanner({ name, meta }: { name: string; meta: string }) {
  return (
    <div data-testid="part-banner"
      className="rounded-2xl bg-slate-950 px-5 py-4 text-white shadow-md">
      <p className="text-xs font-bold uppercase tracking-[0.28em] text-slate-400">{name}</p>
      <p className="mt-1 text-lg font-semibold">{meta}</p>
    </div>
  );
}

interface QuestionArticleProps {
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

function QuestionArticle({
  question, displayLabel, isEditing, editText,
  onEditTextChange, onSaveEdit, onEditStart, onToggleLock,
  instruction, onInstructionChange, onRegenerate, regenPending,
}: QuestionArticleProps) {
  const locked = Boolean(question.locked);
  return (
    <article data-testid="question-card" className="rounded-lg border border-line bg-surface p-5 shadow-low">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span data-testid="question-number"
            className="rounded-sm bg-primary px-3 py-1 text-metadata font-semibold tracking-[0.2em] text-white">
            Q{displayLabel}
          </span>
          <Pill>
            {question.marks} marks
            {Number(question.unit) > 0 ? ` · Unit ${question.unit}` : ''}
            {question.topic ? ` · ${question.topic}` : ''}
            {question.bloom_level ? ` · ${question.bloom_level}` : ''}
          </Pill>
          {locked ? (
            <span data-testid="lock-state" className="inline-flex items-center gap-1 rounded-pill border border-success/30 bg-success-soft px-3 py-1 text-metadata font-medium text-success">
              <Lock className="h-3 w-3" /> Locked
            </span>
          ) : (
            <span data-testid="unlock-state" className="rounded-pill border border-warning/30 bg-warning-soft px-3 py-1 text-metadata font-medium text-warning">Unlocked</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isEditing ? (
            <button type="button" onClick={onSaveEdit}
              className="rounded-[0.5rem] bg-primary px-3 py-1 text-metadata font-semibold text-white transition-colors duration-micro hover:bg-primary-hover">
              Save
            </button>
          ) : (
            <button type="button" onClick={onEditStart}
              className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-line bg-surface px-3 py-1 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50">
              <Edit3 className="h-3.5 w-3.5" /> Edit
            </button>
          )}
          <button type="button" onClick={onToggleLock}
            disabled={regenPending}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50">
            {locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
            {locked ? 'Unlock' : 'Lock'}
          </button>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <h2 className="text-section-heading text-text-primary">{question.topic || `Question ${displayLabel}`}</h2>
        {isEditing ? (
          <span className="rounded-pill border border-warning/30 bg-warning-soft px-2.5 py-0.5 text-metadata font-medium text-warning" data-testid="unsaved-changes">Unsaved changes</span>
        ) : null}
        {locked ? (
          <span className="text-metadata text-danger" data-testid="locked-hint">This question is locked and cannot be regenerated.</span>
        ) : null}
      </div>
      <p className="mt-0.5 text-metadata text-text-muted">
        Difficulty: {question.difficulty} · Type: {question.question_type}
        {(question.choice_group || question.choice_group_id) ? ` · Choice: ${question.choice_group || question.choice_group_id}` : ''}
      </p>

      {isEditing ? (
        <textarea value={editText} onChange={(event) => onEditTextChange(event.target.value)}
          aria-label="Question text"
          data-testid="edit-textarea"
          className="mt-3 w-full rounded-[0.5rem] border border-line bg-surface p-3 text-body text-text-primary outline-none transition-colors duration-micro focus:border-primary focus:ring-2 focus:ring-primary/20" rows={3} />
      ) : (
        <p data-testid="question-text" className="mt-3 whitespace-pre-wrap text-body leading-7 text-text-primary">{question.question_text || 'No question text yet.'}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200/60 pt-3">
        <input value={instruction} onChange={(event) => onInstructionChange(event.target.value)}
          placeholder="Optional: what to improve in the rewrite"
          aria-label="Regeneration instructions"
          data-testid="regen-input"
          className="min-w-52 flex-1 rounded-[0.5rem] border border-line bg-surface px-3 py-2 text-body text-text-primary outline-none transition-colors duration-micro focus:border-primary focus:ring-2 focus:ring-primary/20" />
        <button type="button" onClick={onRegenerate} disabled={locked || regenPending}
          className="inline-flex items-center gap-1.5 rounded-[0.5rem] border border-primary/40 bg-transparent px-4 py-2 text-metadata font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60 disabled:opacity-50">
          <RefreshCw className="h-3.5 w-3.5" /> Regenerate
        </button>
      </div>
    </article>
  );
}
