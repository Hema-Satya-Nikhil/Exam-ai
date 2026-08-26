'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeft, ArrowRight, CheckCircle2, CopyPlus, FileText, Layers3, Loader2, Sparkles, Trash2, Upload } from 'lucide-react';
import { usePaperGeneration } from '@/hooks/use-generation';
import { uploadModelPaper, uploadSyllabus, uploadUnitMaterial } from '@/lib/api';

const questionRowSchema = z.object({
  questionNumber: z.coerce.number().int().min(1),
  section: z.string().min(1),
  marks: z.coerce.number().int().min(1),
  unit: z.coerce.number().int().min(1),
  topic: z.string().min(1),
  bloomLevel: z.enum(['L2', 'L3', 'L4', 'L5', 'L6']),
  difficulty: z.enum(['easy', 'medium', 'hard']),
  questionType: z.string().min(1),
  internalChoice: z.string().optional().default('')
});

const wizardSchema = z.object({
  mode: z.enum(['model-paper', 'manual']),
  subject: z.string().min(1),
  subjectCode: z.string().min(1),
  examType: z.string().min(1),
  academicYear: z.string().min(1),
  totalMarks: z.coerce.number().int().min(1),
  durationMinutes: z.coerce.number().int().min(1),
  selectedUnits: z.string().min(1),
  modelPaperName: z.string().optional(),
  syllabusFile: z.string().optional(),
  unitMaterialSummary: z.string().optional(),
  sections: z.string().min(1),
  bloomStrategy: z.string().min(1),
  twoMarkCount: z.coerce.number().int().min(0),
  questions: z.array(questionRowSchema).min(1)
});

type WizardValues = z.infer<typeof wizardSchema>;

const defaultQuestions = [
  {
    questionNumber: 1,
    section: 'Part A',
    marks: 2,
    unit: 1,
    topic: 'Introduction to clustering',
    bloomLevel: 'L2' as const,
    difficulty: 'easy' as const,
    questionType: 'conceptual',
    internalChoice: ''
  },
  {
    questionNumber: 2,
    section: 'Part A',
    marks: 2,
    unit: 1,
    topic: 'K-means objective',
    bloomLevel: 'L3' as const,
    difficulty: 'medium' as const,
    questionType: 'application',
    internalChoice: ''
  }
];

const stepLabels = [
  'Subject & Exam',
  'Syllabus',
  'Unit Materials',
  'Model Paper / Manual',
  'Blueprint',
  'Bloom & 2-Mark',
  'Generate',
  'Review'
];

const sectionPresets = {
  'model-paper': 'Part A - 2 marks, Part B - 5 marks, Part C - 10 marks',
  manual: 'Custom sections and internal choice rules defined by faculty'
};

export function PaperWizard() {
  const [step, setStep] = useState(0);
  const [generatedPaperId, setGeneratedPaperId] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const generatePaper = usePaperGeneration();

  const form = useForm<WizardValues>({
    resolver: zodResolver(wizardSchema),
    defaultValues: {
      mode: 'model-paper',
      subject: 'Data Mining',
      subjectCode: 'CSE-402',
      examType: 'Mid 2',
      academicYear: '2026-27',
      totalMarks: 70,
      durationMinutes: 180,
      selectedUnits: '3,4,5',
      modelPaperName: 'Mid 2 Model Paper',
      syllabusFile: 'uploaded-syllabus.pdf',
      unitMaterialSummary: 'Unit 3 Notes.pdf, Unit 4 Notes.docx, Unit 5 Notes.pdf',
      sections: 'Part A, Part B, Part C',
      bloomStrategy: 'L2 20%, L3 20%, L4 30%, L5 20%, L6 10%',
      twoMarkCount: 10,
      questions: defaultQuestions
    }
  });

  const { fields, append, remove, insert } = useFieldArray({ control: form.control, name: 'questions' });
  const mode = form.watch('mode');
  const questions = form.watch('questions');

  function handleGeneratePaper() {
    setGenerationError(null);
    const values = form.getValues();
    const parsedUnits = values.selectedUnits
      .split(',')
      .map((item) => parseInt(item.trim(), 10))
      .filter((num) => !isNaN(num));

    const payload = {
      blueprint: {
        exam_type: values.examType,
        subject: values.subject,
        selected_units: parsedUnits.length ? parsedUnits : [1, 2],
        total_marks: values.totalMarks,
        duration_minutes: values.durationMinutes,
        sections: [
          {
            name: 'Part A',
            section_type: 'short_answer',
            question_count: values.questions.filter((q) => q.section === 'Part A').length || 1,
            marks_per_question: 2,
            instructions: 'Answer all 2-mark questions.'
          },
          {
            name: 'Part B',
            section_type: 'descriptive',
            question_count: values.questions.filter((q) => q.section === 'Part B').length || 1,
            marks_per_question: 10,
            instructions: 'Answer all descriptive questions.'
          }
        ],
        questions: values.questions.map((q) => ({
          question_number: q.questionNumber,
          section: q.section,
          marks: q.marks,
          unit: q.unit,
          topic: q.topic,
          bloom_level: q.bloomLevel,
          difficulty: q.difficulty,
          question_type: q.questionType,
          choice_group: q.internalChoice || null
        })),
        source_mode: values.mode
      }
    };

    generatePaper.mutate(payload, {
      onSuccess: (data: any) => {
        const id = data.paper_id || data.job?.id || 'draft-placeholder';
        setGeneratedPaperId(id);
        setStep(7);
      },
      onError: (err: any) => {
        setGenerationError(err.message || 'Paper generation failed. Please check blueprint rules.');
      }
    });
  }

  const summary = useMemo(() => {
    const totalQuestionMarks = questions.reduce((sum, item) => sum + Number(item.marks || 0), 0);
    const unitList = form.watch('selectedUnits').split(',').map((value) => value.trim()).filter(Boolean);

    return {
      totalQuestionMarks,
      unitCount: unitList.length,
      questionCount: questions.length
    };
  }, [form, questions]);

  function nextStep() {
    setStep((current) => Math.min(current + 1, stepLabels.length - 1));
  }

  function previousStep() {
    setStep((current) => Math.max(current - 1, 0));
  }

  const selectedModeCopy = mode === 'model-paper' ? 'Model paper path' : 'Manual configuration path';

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.95),_rgba(226,232,240,0.75)_40%,_rgba(203,213,225,0.28)_72%,_rgba(15,23,42,0.05))] text-slate-900">
      <section className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-8 lg:px-10">
        <div className="glass-panel rounded-[2rem] border border-white/60 bg-white/55 p-6 shadow-glass backdrop-blur-glass">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/65 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                <Sparkles className="h-3.5 w-3.5" />
                Paper creation workspace
              </div>
              <h1 className="text-3xl font-semibold tracking-tight md:text-5xl">Create a governed exam paper blueprint.</h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-600 md:text-base">
                Faculty control the sections, units, Bloom distribution, and 2-mark structure. The backend will validate the rules before generation and export.
              </p>
            </div>
            <div className="rounded-3xl border border-slate-200/60 bg-slate-950 px-5 py-4 text-white shadow-lg">
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Current path</p>
              <p className="mt-1 text-lg font-semibold">{selectedModeCopy}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-4 lg:grid-cols-8">
            {stepLabels.map((label, index) => {
              const active = index === step;
              const completed = index < step;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setStep(index)}
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    active
                      ? 'border-slate-900/15 bg-slate-950 text-white shadow-lg'
                      : completed
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                        : 'border-white/70 bg-white/55 text-slate-600 hover:bg-white/75'
                  }`}
                >
                  <div className="text-xs font-medium uppercase tracking-[0.18em] opacity-70">Step {index + 1}</div>
                  <div className="mt-1 text-sm font-semibold leading-5">{label}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-6">
            <div className="glass-panel rounded-[2rem] border border-white/60 bg-white/60 p-6 shadow-glass backdrop-blur-glass">
              {step === 0 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <Layers3 className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Subject & exam definition</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Subject" value={form.watch('subject')} onChange={(value) => form.setValue('subject', value)} />
                    <Field label="Subject code" value={form.watch('subjectCode')} onChange={(value) => form.setValue('subjectCode', value)} />
                    <Field label="Exam type" value={form.watch('examType')} onChange={(value) => form.setValue('examType', value)} />
                    <Field label="Academic year" value={form.watch('academicYear')} onChange={(value) => form.setValue('academicYear', value)} />
                    <Field label="Total marks" type="number" value={String(form.watch('totalMarks'))} onChange={(value) => form.setValue('totalMarks', Number(value))} />
                    <Field label="Duration (minutes)" type="number" value={String(form.watch('durationMinutes'))} onChange={(value) => form.setValue('durationMinutes', Number(value))} />
                  </div>
                  <ModeSwitcher value={mode} onChange={(value) => form.setValue('mode', value)} />
                  <Field label="Selected units" hint="Comma-separated units selected for this exam" value={form.watch('selectedUnits')} onChange={(value) => form.setValue('selectedUnits', value)} />
                </div>
              )}

              {step === 1 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <FileText className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Syllabus ingestion</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field label="Uploaded syllabus file" value={form.watch('syllabusFile') ?? ''} onChange={(value) => form.setValue('syllabusFile', value)} />
                    <Field label="Syllabus preview status" value="Parsed and awaiting faculty confirmation" onChange={() => undefined} readOnly />
                  </div>
                  <InfoCard title="Extracted structure" body="Unit 1: foundational concepts, Unit 2: clustering methods, Unit 3: classification, Unit 4: pattern mining, Unit 5: evaluation." />
                  <InfoCard title="Faculty action" body="Review detected units and topics before any generation step starts. Nothing is silently assumed." />
                </div>
              )}

              {step === 2 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <CopyPlus className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Unit materials</h2>
                  </div>
                  <Field label="Attached unit materials" value={form.watch('unitMaterialSummary') ?? ''} onChange={(value) => form.setValue('unitMaterialSummary', value)} />
                  <div className="grid gap-4 md:grid-cols-3">
                    <InfoCard title="Primary source" body="Use unit materials first when available." />
                    <InfoCard title="Boundary source" body="Syllabus still validates coverage and scope." />
                    <InfoCard title="Fallback" body="If a unit has no material, syllabus content is used instead." />
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <FileText className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Model paper or manual rules</h2>
                  </div>
                  {mode === 'model-paper' ? (
                    <>
                      <Field label="Model paper file" value={form.watch('modelPaperName') ?? ''} onChange={(value) => form.setValue('modelPaperName', value)} />
                      <InfoCard title="Blueprint extraction" body="Section order, marks, numbering, and choices are extracted as a candidate blueprint for faculty confirmation." />
                    </>
                  ) : (
                    <>
                      <Field label="Section structure" value={form.watch('sections')} onChange={(value) => form.setValue('sections', value)} />
                      <InfoCard title="Manual path" body="Faculty defines the complete paper structure without relying on a model paper." />
                    </>
                  )}
                </div>
              )}

              {step === 4 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <Layers3 className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Blueprint review</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <Metric label="Marks total" value={`${summary.totalQuestionMarks}`} />
                    <Metric label="Questions" value={`${summary.questionCount}`} />
                    <Metric label="Units selected" value={`${summary.unitCount}`} />
                    <Metric label="Mode" value={mode === 'model-paper' ? 'Model paper' : 'Manual'} />
                  </div>
                  <InfoCard title="Blueprint preview" body={sectionPresets[mode]} />
                  <InfoCard title="Validation note" body="The backend will reject impossible totals, unit mismatches, or ambiguous question counts before generation starts." />
                </div>
              )}

              {step === 5 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <Sparkles className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Bloom taxonomy and 2-mark configuration</h2>
                  </div>
                  <Field label="Bloom strategy" value={form.watch('bloomStrategy')} onChange={(value) => form.setValue('bloomStrategy', value)} />
                  <Field label="2-mark question count" type="number" value={String(form.watch('twoMarkCount'))} onChange={(value) => form.setValue('twoMarkCount', Number(value))} />
                  <div className="overflow-hidden rounded-[1.75rem] border border-white/70 bg-white/60">
                    <div className="border-b border-slate-200/70 px-5 py-4 text-sm font-semibold text-slate-900">2-Mark Question Configuration</div>
                    <div className="max-h-[360px] overflow-auto">
                      <table className="min-w-full divide-y divide-slate-200/70 text-sm">
                        <thead className="bg-white/80 text-left text-xs uppercase tracking-[0.16em] text-slate-500">
                          <tr>
                            <th className="px-5 py-3">#</th>
                            <th className="px-5 py-3">Unit</th>
                            <th className="px-5 py-3">Topic</th>
                            <th className="px-5 py-3">Bloom</th>
                            <th className="px-5 py-3">Style</th>
                            <th className="px-5 py-3 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-200/70 bg-white/40">
                          {fields.map((field, index) => (
                            <tr key={field.id}>
                              <td className="px-5 py-3 font-medium text-slate-700">
                                <input
                                  className="w-16 rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none ring-0 focus:border-slate-400"
                                  type="number"
                                  value={questions[index]?.questionNumber}
                                  onChange={(event) => form.setValue(`questions.${index}.questionNumber`, Number(event.target.value))}
                                />
                              </td>
                              <td className="px-5 py-3">
                                <input
                                  className="w-24 rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-slate-400"
                                  value={questions[index]?.unit}
                                  onChange={(event) => form.setValue(`questions.${index}.unit`, Number(event.target.value))}
                                />
                              </td>
                              <td className="px-5 py-3">
                                <input
                                  className="w-full min-w-48 rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-slate-400"
                                  value={questions[index]?.topic}
                                  onChange={(event) => form.setValue(`questions.${index}.topic`, event.target.value)}
                                />
                              </td>
                              <td className="px-5 py-3">
                                <select
                                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-slate-400"
                                  value={questions[index]?.bloomLevel}
                                  onChange={(event) => form.setValue(`questions.${index}.bloomLevel`, event.target.value as WizardValues['questions'][number]['bloomLevel'])}
                                >
                                  {['L2', 'L3', 'L4', 'L5', 'L6'].map((level) => (
                                    <option key={level} value={level}>
                                      {level}
                                    </option>
                                  ))}
                                </select>
                              </td>
                              <td className="px-5 py-3">
                                <input
                                  className="w-28 rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none focus:border-slate-400"
                                  value={questions[index]?.questionType}
                                  onChange={(event) => form.setValue(`questions.${index}.questionType`, event.target.value)}
                                />
                              </td>
                              <td className="px-5 py-3 text-right">
                                <div className="inline-flex gap-2">
                                  <button type="button" onClick={() => insert(index + 1, { ...questions[index], questionNumber: questions[index].questionNumber + 1 })} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-slate-600 transition hover:bg-slate-100" aria-label="Duplicate row">
                                    <CopyPlus className="h-4 w-4" />
                                  </button>
                                  <button type="button" onClick={() => remove(index)} className="rounded-full border border-rose-200 bg-rose-50 px-3 py-2 text-rose-600 transition hover:bg-rose-100" aria-label="Delete row">
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex items-center justify-between border-t border-slate-200/70 px-5 py-4">
                      <p className="text-sm text-slate-600">Rows can be duplicated, reordered, or deleted before generation.</p>
                      <button
                        type="button"
                        className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                        onClick={() => append({ ...questions[questions.length - 1], questionNumber: questions.length + 1 })}
                      >
                        Add row
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {step === 6 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <Sparkles className="h-5 w-5 text-slate-600" />
                    <h2 className="text-xl font-semibold">Generation staging</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <InfoCard title="Deterministic Blueprint Control" body="The backend validates total marks, unit coverage, and Bloom taxonomy rules before invoking LLM generation." />
                    <InfoCard title="Validation Engine Active" body="All generated questions will be checked for unit boundary adherence and model paper duplicate protection." />
                  </div>

                  {generationError && (
                    <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-700">
                      <strong>Generation Error:</strong> {generationError}
                    </div>
                  )}

                  <div className="rounded-[1.75rem] border border-white/70 bg-white/70 p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-slate-950">Ready to Generate Question Paper</h3>
                    <p className="mt-1 text-sm text-slate-600">
                      Click below to submit the validated blueprint. Questions will be generated and persisted in PostgreSQL.
                    </p>
                    <button
                      type="button"
                      disabled={generatePaper.isPending}
                      onClick={handleGeneratePaper}
                      className="mt-5 inline-flex items-center gap-2 rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
                    >
                      {generatePaper.isPending ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Generating Questions...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" />
                          Generate Question Paper
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}

              {step === 7 && (
                <div className="space-y-6">
                  <div className="flex items-center gap-3 text-slate-900">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    <h2 className="text-xl font-semibold">Review and export</h2>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    <InfoCard title="Structure" body="✓ Blueprint validation passed" />
                    <InfoCard title="Quality" body="✓ Duplicate and scope checks complete" />
                    <InfoCard title="Approval" body="Faculty must explicitly approve before PDF/DOCX export." />
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <Link
                      href={generatedPaperId ? `/review?paper_id=${generatedPaperId}` : '/review'}
                      className="inline-flex rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                    >
                      Open review workspace
                    </Link>
                    <Link href="/dashboard" className="inline-flex rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100">
                      Back to dashboard
                    </Link>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between rounded-[1.75rem] border border-white/60 bg-white/55 px-5 py-4 shadow-glass backdrop-blur-glass">
              <button type="button" onClick={previousStep} disabled={step === 0} className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 disabled:opacity-50">
                <ArrowLeft className="h-4 w-4" />
                Back
              </button>
              <div className="text-sm text-slate-500">Step {step + 1} of {stepLabels.length}</div>
              <button type="button" onClick={nextStep} disabled={step === stepLabels.length - 1} className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50">
                Next
                <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="space-y-6">
            <div className="glass-panel rounded-[2rem] border border-white/60 bg-white/60 p-6 shadow-glass backdrop-blur-glass">
              <p className="text-sm font-medium text-slate-500">Blueprint summary</p>
              <div className="mt-4 space-y-3 text-sm text-slate-700">
                <SummaryRow label="Subject" value={form.watch('subject')} />
                <SummaryRow label="Exam" value={form.watch('examType')} />
                <SummaryRow label="Units" value={form.watch('selectedUnits')} />
                <SummaryRow label="Marks" value={`${form.watch('totalMarks')}`} />
                <SummaryRow label="Duration" value={`${form.watch('durationMinutes')} min`} />
                <SummaryRow label="Bloom" value={form.watch('bloomStrategy')} />
              </div>
            </div>

            <div className="glass-panel rounded-[2rem] border border-white/60 bg-slate-950 p-6 text-white shadow-glass backdrop-blur-glass">
              <p className="text-sm font-medium text-slate-400">Workflow integrity</p>
              <div className="mt-4 space-y-3 text-sm text-slate-200">
                <p>• Model paper never becomes the factual subject source.</p>
                <p>• Faculty review sits between extraction and generation.</p>
                <p>• Validation blocks invalid papers before export.</p>
                <p>• Locked questions cannot be changed by regeneration.</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
  hint,
  readOnly = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  hint?: string;
  readOnly?: boolean;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <input
        readOnly={readOnly}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-2xl border border-slate-200/80 bg-white/75 px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:bg-white"
      />
      {hint ? <span className="text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}

function ModeSwitcher({ value, onChange }: { value: 'model-paper' | 'manual'; onChange: (value: 'model-paper' | 'manual') => void }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <button
        type="button"
        onClick={() => onChange('model-paper')}
        className={`rounded-[1.5rem] border px-4 py-4 text-left transition ${value === 'model-paper' ? 'border-slate-950 bg-slate-950 text-white shadow-lg' : 'border-slate-200 bg-white/70 text-slate-700 hover:bg-white'}`}
      >
        <div className="text-xs uppercase tracking-[0.18em] text-current/70">Mode A</div>
        <div className="mt-1 font-semibold">Model paper available</div>
        <div className="mt-2 text-sm opacity-80">Analyze structure, then confirm or correct the extracted blueprint.</div>
      </button>
      <button
        type="button"
        onClick={() => onChange('manual')}
        className={`rounded-[1.5rem] border px-4 py-4 text-left transition ${value === 'manual' ? 'border-slate-950 bg-slate-950 text-white shadow-lg' : 'border-slate-200 bg-white/70 text-slate-700 hover:bg-white'}`}
      >
        <div className="text-xs uppercase tracking-[0.18em] text-current/70">Mode B</div>
        <div className="mt-1 font-semibold">No model paper</div>
        <div className="mt-2 text-sm opacity-80">Faculty define the entire paper blueprint manually in the wizard.</div>
      </button>
    </div>
  );
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/70 bg-white/70 p-4">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.5rem] border border-white/70 bg-white/70 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/60 pb-2 last:border-b-0 last:pb-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}
