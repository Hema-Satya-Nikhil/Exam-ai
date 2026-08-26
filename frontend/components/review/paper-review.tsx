'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';
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

import { GlassCard } from '@/components/ui/glass-card';
import { useAuth } from '@/contexts/auth-context';
import {
  usePaperApproval,
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
  const approveMutation = usePaperApproval();
  const exportMutation = usePaperExport();

  const [editingQuestion, setEditingQuestion] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [regenerationInstructions, setRegenerationInstructions] = useState<Record<number, string>>({});
  const [approvalComment, setApprovalComment] = useState('');
  const [feedback, setFeedback] = useState<{ tone: 'ok' | 'error'; message: string } | null>(null);
  const [referenceDraft, setReferenceDraft] = useState<any>(null);

  const draft = paperDraft ?? referenceDraft;
  const status: string = draft?.status ?? 'draft';
  const paperJson = draft?.paper_json ?? {};
  const questions: Array<Record<string, any>> = paperJson.questions ?? [];

  function flash(tone: 'ok' | 'error', message: string) {
    setFeedback({ tone, message });
  }

  function toggleLock(questionNumber: number) {
    if (!paperId) return;
    if (lockMutation.isPending || unlockMutation.isPending) return;
    const target = questions.find((question) => Number(question.question_number) === questionNumber);
    if (!target) return;

    const mutate = target.locked ? unlockMutation : lockMutation;
    mutate.mutate(
      { paper_id: paperId, question_number: questionNumber },
      {
        onSuccess: (draft: any) => setReferenceDraft(draft),
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function saveEdit(questionNumber: number) {
    if (!paperId) return;
    updateQuestionMutation.mutate(
      { paper_id: paperId, question_number: questionNumber, updates: { question_text: editText } as never },
      {
        onSuccess: (draft: any) => {
          setReferenceDraft(draft);
          setEditingQuestion(null);
          flash('ok', 'Question text updated.');
        },
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function handleRegenerate(questionNumber: number) {
    if (!paperId) return;
    const instructions = regenerationInstructions[questionNumber] ?? '';
    regenerateMutation.mutate(
      { paper_id: paperId, question_number: questionNumber, instructions },
      {
        onSuccess: (draft: any) => {
          setReferenceDraft(draft);
          flash('ok', `Question ${questionNumber} regenerated.`);
        },
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function handleApprove() {
    if (!paperId || !user) {
      flash('error', 'Sign in with a faculty account to approve papers.');
      return;
    }
    approveMutation.mutate(
      { paper_id: paperId, approved_by: user.user_id, comments: approvalComment || undefined },
      {
        onSuccess: () => {
          flash('ok', 'Paper approved. PDF and DOCX export are now available.');
          if (referenceDraft) setReferenceDraft({ ...referenceDraft, status: 'approved', paper_json: { ...referenceDraft.paper_json, status: 'approved' } });
        },
        onError: (error: unknown) => flash('error', messageOf(error))
      }
    );
  }

  function handleExport(format: 'pdf' | 'docx') {
    if (!paperId) return;
    if (status !== 'approved') {
      flash('error', 'Approve the paper before downloading the final file.');
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

  const totalMarks = questions.reduce((sum, question) => sum + Number(question.marks || 0), 0);
  const lockedCount = questions.filter((question) => Boolean(question.locked)).length;

  if (authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.9),_rgba(226,232,240,0.6)_34%,_rgba(203,213,225,0.25)_70%,_rgba(15,23,42,0.04))]">
        <Loader2 className="h-8 w-8 animate-spin text-slate-500" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.92),_rgba(226,232,240,0.68)_36%,_rgba(203,213,225,0.26)_70%,_rgba(15,23,42,0.04))] text-slate-900">
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-500">Review Question Paper</p>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-950">{draft?.title || 'Question paper'}</h1>
          </div>
          <Link href="/dashboard" className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
            <ArrowLeft className="h-4 w-4" /> Dashboard
          </Link>
        </div>

        {!paperId ? (
          <div className="mt-8 rounded-[2rem] border border-dashed border-slate-300 bg-white/60 p-10 text-center">
            <h2 className="text-lg font-semibold text-slate-900">No paper selected</h2>
            <p className="mt-2 text-sm text-slate-600">Generate a paper first, then open it here for review.</p>
            <Link href="/create" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Create a paper
            </Link>
          </div>
        ) : isLoading ? (
          <div className="mt-8 flex items-center justify-center gap-3 rounded-[2rem] border border-white/60 bg-white/60 p-10 text-slate-600">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading paper…
          </div>
        ) : isError || !draft ? (
          <div className="mt-8 rounded-[2rem] border border-red-200 bg-red-50 p-10 text-center">
            <h2 className="text-lg font-semibold text-red-800">Paper not found</h2>
            <p className="mt-2 text-sm text-red-700">We could not load this paper. It may have been created in a different session.</p>
            <Link href="/create" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Create a new paper
            </Link>
          </div>
        ) : !user ? (
          <div className="mt-8 rounded-[2rem] border border-amber-200 bg-amber-50 p-10 text-center">
            <h2 className="text-lg font-semibold text-amber-900">Sign in to review papers</h2>
            <p className="mt-2 text-sm text-amber-800">Approval and export require a faculty or administrator account.</p>
            <Link href="/login" className="mt-5 inline-flex rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              Sign in
            </Link>
          </div>
        ) : (
          <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-4">
                <StatCard label="Status" value={statusLabel(status)} />
                <StatCard label="Total marks" value={`${totalMarks}`} />
                <StatCard label="Questions" value={String(questions.length)} />
                <StatCard label="Locked" value={String(lockedCount)} />
              </div>

              {feedback ? (
                <div
                  className={`rounded-2xl border px-4 py-3 text-sm ${
                    feedback.tone === 'ok' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-red-200 bg-red-50 text-red-800'
                  }`}
                >
                  {feedback.message}
                </div>
              ) : null}

              {questions.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-slate-300 bg-white/60 p-10 text-center">
                  <p className="text-sm text-slate-600">This paper has no questions yet.</p>
                </div>
              ) : (
                questions.map((question) => (
                  <article key={String(question.question_number)} className="rounded-3xl border border-white/70 bg-white/75 p-5 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/60 pb-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold tracking-[0.2em] text-white">
                          Q{question.question_number}
                        </span>
                        <Pill>
                          {question.marks} marks · Unit {question.unit} · {question.bloom_level}
                        </Pill>
                        {question.locked ? (
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                            <Lock className="h-3 w-3" /> Locked
                          </span>
                        ) : (
                          <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">Unlocked</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {editingQuestion === Number(question.question_number) ? (
                          <button
                            type="button"
                            onClick={() => saveEdit(Number(question.question_number))}
                            className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold text-white transition hover:bg-slate-800"
                          >
                            Save
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => {
                              setEditingQuestion(Number(question.question_number));
                              setEditText(String(question.question_text ?? ''));
                            }}
                            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                          >
                            <Edit3 className="h-3.5 w-3.5" /> Edit
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => toggleLock(Number(question.question_number))}
                          disabled={lockMutation.isPending || unlockMutation.isPending}
                          className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                        >
                          {question.locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                          {question.locked ? 'Unlock' : 'Lock'}
                        </button>
                      </div>
                    </div>

                    <h2 className="mt-3 text-base font-semibold text-slate-950">{question.topic || `Question ${question.question_number}`}</h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Difficulty: {question.difficulty} · Type: {question.question_type}
                      {question.choice_group ? ` · Choice: ${question.choice_group}` : ''}
                    </p>

                    {editingQuestion === Number(question.question_number) ? (
                      <textarea
                        value={editText}
                        onChange={(event) => setEditText(event.target.value)}
                        className="mt-3 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-slate-900"
                        rows={3}
                      />
                    ) : (
                      <p className="mt-3 text-sm leading-7 text-slate-800">{question.question_text || 'No question text yet.'}</p>
                    )}

                    <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-200/60 pt-3">
                      <input
                        value={regenerationInstructions[Number(question.question_number)] ?? ''}
                        onChange={(event) =>
                          setRegenerationInstructions((current) => ({
                            ...current,
                            [Number(question.question_number)]: event.target.value
                          }))
                        }
                        placeholder="Optional: what to improve in the rewrite"
                        className="min-w-52 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                      />
                      <button
                        type="button"
                        onClick={() => handleRegenerate(Number(question.question_number))}
                        disabled={Boolean(question.locked) || regenerateMutation.isPending}
                        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                      >
                        <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                      </button>
                    </div>
                  </article>
                ))
              )}
            </div>

            <aside className="space-y-5">
              <GlassCard>
                <p className="text-sm font-medium text-slate-500">Approval</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  Approving this paper records the reviewer and enables the final PDF and DOCX downloads.
                </p>
                {status === 'approved' ? (
                  <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
                    <CheckCircle2 className="h-4 w-4" /> Approved
                  </div>
                ) : (
                  <div className="mt-4 space-y-3">
                    <textarea
                      value={approvalComment}
                      onChange={(event) => setApprovalComment(event.target.value)}
                      placeholder="Optional review comment"
                      rows={2}
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-slate-400"
                    />
                    <button
                      type="button"
                      onClick={handleApprove}
                      disabled={approveMutation.isPending}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
                    >
                      {approveMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      Approve Paper
                    </button>
                  </div>
                )}
              </GlassCard>

              <GlassCard>
                <p className="text-sm font-medium text-slate-500">Export</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">
                  {status === 'approved'
                    ? 'Download the approved version as PDF or DOCX. You can export the same version as many times as needed.'
                    : 'Approve the paper first — downloads are locked until approval.'}
                </p>
                <div className="mt-4 flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleExport('pdf')}
                    disabled={status !== 'approved' || exportMutation.isPending}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 disabled:opacity-50"
                  >
                    <Download className="h-3.5 w-3.5" /> PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('docx')}
                    disabled={status !== 'approved' || exportMutation.isPending}
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
              </GlassCard>
            </aside>
          </div>
        )}
      </section>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white/80 px-4 py-3 shadow-sm">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">{children}</span>;
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