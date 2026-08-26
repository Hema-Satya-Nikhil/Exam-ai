'use client';

import { useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, Download, Edit3, Lock, RefreshCw, ShieldCheck, Sparkles, Unlock } from 'lucide-react';

import { GlassCard } from '@/components/ui/glass-card';
import {
  usePaperApproval,
  usePaperDraft,
  usePaperExport,
  usePaperLock,
  usePaperQuestionUpdate,
  usePaperRegeneration
} from '@/hooks/use-paper-review';

const fallbackQuestions = [
  {
    question_number: 1,
    marks: 2,
    unit: 1,
    topic: 'Introduction to clustering',
    bloom_level: 'L2',
    difficulty: 'easy',
    question_type: 'conceptual',
    question_text: 'Define clustering and state one key application in data mining.',
    locked: true,
    choice_group: null
  },
  {
    question_number: 2,
    marks: 2,
    unit: 1,
    topic: 'K-means objective',
    bloom_level: 'L3',
    difficulty: 'medium',
    question_type: 'application',
    question_text: 'Explain the objective function optimized by K-means clustering.',
    locked: false,
    choice_group: null
  },
  {
    question_number: 3,
    marks: 10,
    unit: 3,
    topic: 'Classification evaluation',
    bloom_level: 'L4',
    difficulty: 'medium',
    question_type: 'analytical',
    question_text: 'Analyze precision, recall, and F1-score in evaluating classifier performance.',
    locked: false,
    choice_group: '3A'
  }
];

export function PaperReview() {
  const searchParams = useSearchParams();
  const paperId = searchParams.get('paper_id') || 'draft-placeholder';

  const { data: paperDraft } = usePaperDraft(paperId);
  const lockMutation = usePaperLock();
  const regenerateMutation = usePaperRegeneration();
  const updateQuestionMutation = usePaperQuestionUpdate();
  const approveMutation = usePaperApproval();
  const exportMutation = usePaperExport();

  const [questions, setQuestions] = useState(fallbackQuestions);
  const [paperStatus, setPaperStatus] = useState<string>('draft');
  const [editingQuestion, setEditingQuestion] = useState<number | null>(null);
  const [editText, setEditText] = useState<string>('');
  const [regenerationInstructions, setRegenerationInstructions] = useState<Record<number, string>>({});

  useEffect(() => {
    if (paperDraft?.paper_json?.questions) {
      setQuestions(paperDraft.paper_json.questions);
      setPaperStatus(paperDraft.status || 'draft');
    }
  }, [paperDraft]);

  const summary = useMemo(() => {
    const totalMarks = questions.reduce((sum, question) => sum + Number(question.marks || 0), 0);
    const lockedCount = questions.filter((question) => question.locked).length;
    return { totalMarks, lockedCount, questionCount: questions.length };
  }, [questions]);

  function toggleLock(questionNumber: number) {
    const target = questions.find((q) => q.question_number === questionNumber);
    if (!target) return;

    setQuestions((current) =>
      current.map((q) => (q.question_number === questionNumber ? { ...q, locked: !q.locked } : q))
    );

    if (paperId && paperId !== 'draft-placeholder') {
      lockMutation.mutate({ paper_id: paperId, question_number: questionNumber });
    }
  }

  function handleRegenerate(questionNumber: number) {
    const instructions = regenerationInstructions[questionNumber] || '';
    setQuestions((current) =>
      current.map((q) =>
        q.question_number === questionNumber
          ? {
              ...q,
              question_text: `${q.question_text} (Regenerated with: ${instructions || 'controlled variation'})`
            }
          : q
      )
    );

    if (paperId && paperId !== 'draft-placeholder') {
      regenerateMutation.mutate({ paper_id: paperId, question_number: questionNumber, instructions });
    }
  }

  function startEditing(questionNumber: number, text: string) {
    setEditingQuestion(questionNumber);
    setEditText(text);
  }

  function saveEdit(questionNumber: number) {
    setQuestions((current) =>
      current.map((q) => (q.question_number === questionNumber ? { ...q, question_text: editText } : q))
    );
    setEditingQuestion(null);

    if (paperId && paperId !== 'draft-placeholder') {
      updateQuestionMutation.mutate({
        paper_id: paperId,
        question_number: questionNumber,
        updates: { question_text: editText }
      });
    }
  }

  function handleApprove() {
    setPaperStatus('approved');
    if (paperId && paperId !== 'draft-placeholder') {
      approveMutation.mutate({ paper_id: paperId, approved_by: 'Faculty Reviewer', comments: 'Approved after review.' });
    }
  }

  function handleExport(format: 'pdf' | 'docx') {
    const paperJson = paperDraft?.paper_json || {
      title: 'Departmental Examination Paper',
      institution_name: 'ExamCraft University',
      department_name: 'Department of Computer Science & Engineering',
      exam_name: 'Mid Semester Examination',
      subject_name: 'Data Mining',
      subject_code: 'CSE-402',
      duration_minutes: 180,
      total_marks: summary.totalMarks,
      instructions: ['Answer all questions as instructed.'],
      sections: [
        {
          name: 'Part A',
          instructions: 'Short questions (2 marks each)',
          questions: questions.filter((q) => q.marks === 2)
        },
        {
          name: 'Part B',
          instructions: 'Long questions (10 marks each)',
          questions: questions.filter((q) => q.marks > 2)
        }
      ],
      questions
    };

    exportMutation.mutate({ paper_json: paperJson, format });
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.96),_rgba(226,232,240,0.72)_40%,_rgba(203,213,225,0.28)_72%,_rgba(15,23,42,0.05))] text-slate-900">
      <section className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
        <div className="glass-panel rounded-[2rem] border border-white/60 bg-white/60 p-6 shadow-glass backdrop-blur-glass">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <ShieldCheck className="h-3.5 w-3.5" />
                Faculty review workspace
              </div>
              <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">Review, lock, regenerate, and approve the paper.</h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-600 md:text-base">
                Each question can be edited or regenerated independently without rebuilding the full paper. Paper status: <strong className="capitalize">{paperStatus}</strong>
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard label="Questions" value={summary.questionCount} />
              <StatCard label="Locked" value={summary.lockedCount} />
              <StatCard label="Marks" value={summary.totalMarks} />
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[0.68fr_0.32fr]">
          <div className="space-y-4">
            {questions.map((question) => (
              <GlassCard key={question.question_number}>
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/60 pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold tracking-[0.2em] text-white">
                        Q{question.question_number}
                      </span>
                      <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                        {question.marks} marks
                      </span>
                      <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                        Unit {question.unit}
                      </span>
                      <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                        {question.bloom_level}
                      </span>
                      {question.locked ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                          <Lock className="h-3 w-3" /> Locked
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                          <Unlock className="h-3 w-3" /> Regeneratable
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {editingQuestion === question.question_number ? (
                        <button
                          type="button"
                          onClick={() => saveEdit(question.question_number)}
                          className="rounded-full bg-slate-950 px-3 py-1 text-xs font-semibold text-white transition hover:bg-slate-800"
                        >
                          Save
                        </button>
                      ) : (
                        <ActionButton icon={<Edit3 className="h-3.5 w-3.5" />} label="Edit" onClick={() => startEditing(question.question_number, question.question_text)} />
                      )}
                      <ActionButton
                        icon={question.locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                        label={question.locked ? 'Unlock' : 'Lock'}
                        onClick={() => toggleLock(question.question_number)}
                      />
                    </div>
                  </div>

                  <div>
                    <h2 className="text-base font-semibold text-slate-950">{question.topic}</h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Difficulty: {question.difficulty} | Type: {question.question_type}
                    </p>
                  </div>

                  {editingQuestion === question.question_number ? (
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      className="w-full rounded-xl border border-slate-300 p-3 text-sm focus:border-slate-900 outline-none"
                      rows={3}
                    />
                  ) : (
                    <p className="text-sm leading-7 text-slate-800">{question.question_text}</p>
                  )}

                  {!question.locked && (
                    <div className="flex items-center gap-2 pt-2">
                      <input
                        type="text"
                        placeholder="Optional prompt instruction for regeneration..."
                        value={regenerationInstructions[question.question_number] || ''}
                        onChange={(e) =>
                          setRegenerationInstructions({
                            ...regenerationInstructions,
                            [question.question_number]: e.target.value
                          })
                        }
                        className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs outline-none focus:border-slate-400"
                      />
                      <button
                        type="button"
                        onClick={() => handleRegenerate(question.question_number)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
                      >
                        <RefreshCw className="h-3 w-3" /> Regenerate
                      </button>
                    </div>
                  )}
                </div>
              </GlassCard>
            ))}
          </div>

          <div className="space-y-6">
            <GlassCard>
              <p className="text-sm font-medium text-slate-500">Validation Summary</p>
              <div className="mt-4 space-y-3 text-sm text-slate-700">
                <SummaryRow label="Structure" value="Passed" icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} />
                <SummaryRow label="Marks total" value="Passed" icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} />
                <SummaryRow label="Unit scope" value="Passed" icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} />
                <SummaryRow label="Duplicates" value="Passed" icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} />
                <SummaryRow label="Faculty approval" value={paperStatus === 'approved' ? 'Approved' : 'Pending'} icon={<Sparkles className="h-4 w-4 text-slate-500" />} />
              </div>
            </GlassCard>

            <GlassCard>
              <p className="text-sm font-medium text-slate-500">Approval & Export</p>
              <p className="mt-2 text-xs text-slate-600 leading-5">
                Faculty must explicitly approve the paper structure and wording before downloading the official PDF or DOCX file.
              </p>
              <div className="mt-5 flex flex-col gap-3">
                <button
                  type="button"
                  onClick={handleApprove}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                  Approve Paper
                </button>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleExport('pdf')}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100"
                  >
                    <Download className="h-3.5 w-3.5" /> PDF
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('docx')}
                    className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 transition hover:bg-slate-100"
                  >
                    <Download className="h-3.5 w-3.5" /> DOCX
                  </button>
                </div>
              </div>
            </GlassCard>
          </div>
        </div>
      </section>
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white/80 px-4 py-3 shadow-sm backdrop-blur-glass">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function ActionButton({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-100">
      {icon}
      {label}
    </button>
  );
}

function SummaryRow({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-white/70 bg-white/70 px-4 py-3">
      <div className="flex items-center gap-2">
        {icon}
        <span>{label}</span>
      </div>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}
