'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  FileCheck2,
  LayoutGrid,
  Loader2,
  RefreshCw,
  Sparkles
} from 'lucide-react';

import { useAuth } from '@/contexts/auth-context';
import { confirmSyllabus, cancelGenerationJob, getGenerationJob, queueGenerationJob, resumeGenerationJob, uploadModelPaper, uploadSyllabus, uploadUnitMaterial, validateBlueprint } from '@/lib/api';
import type { GenerationJobSnapshot, ModelPaperAnalysis, UploadModelPaperResult, UploadSyllabusResult, UploadUnitMaterialResult } from '@/lib/api';
import { isTerminal, POLL_INTERVAL_MS } from '@/lib/generation-progress';
import { stableItemKey } from '@/lib/list-keys';
import { BLOOM_OPTIONS, buildBlueprint, DEFAULT_SECTIONS, sectionTotals } from '@/lib/wizard-logic';
import type { BloomLevel, BlueprintQuestion, SectionConfig, SyllabusUnit } from '@/lib/wizard-logic';
import { addUnit, normalizeParsedUnits, removeUnit, validationIssues } from '@/lib/syllabus-guide';
import type { EditableUnit } from '@/lib/syllabus-guide';
import { GenerationProgressCard } from '@/components/wizard/generation-progress';
import { SectionBuilder } from '@/components/wizard/section-builder';
import { Stepper } from '@/components/wizard/stepper';
import type { StepperItem } from '@/components/wizard/stepper';
import { UploadDrop } from '@/components/wizard/upload-drop';
import { Badge } from '@/components/ui/badge';

const STEP_LABELS = [
  'Subject & Exam',
  'Syllabus',
  'Unit Materials',
  'Paper Pattern',
  'Question Structure',
  'Blueprint & Bloom',
  'Generate',
  'Review & Export'
] as const;

type UploadMovement = 'idle' | 'uploading' | 'success' | 'error';

export function PaperWizard() {
  const { user, loading: authLoading } = useAuth();

  // ---------------------------------------------------------------------
  // Wizard state (no demo defaults — everything starts empty)
  // ---------------------------------------------------------------------
  const [step, setStep] = useState(0);
  const [examType, setExamType] = useState('');
  const [subject, setSubject] = useState('');
  const [subjectCode, setSubjectCode] = useState('');
  const [academicYear, setAcademicYear] = useState('');
  const [totalMarks, setTotalMarks] = useState<number>(70);
  const [durationMinutes, setDurationMinutes] = useState<number>(180);
  const [selectedUnits, setSelectedUnits] = useState<number[]>([]);

  const [syllabusStatus, setSyllabusStatus] = useState<UploadMovement>('idle');
  const [syllabusFileName, setSyllabusFileName] = useState<string>('');
  const [syllabusUnits, setSyllabusUnits] = useState<SyllabusUnit[]>([]);
  const [syllabusNotes, setSyllabusNotes] = useState<string[]>([]);
  const [syllabusError, setSyllabusError] = useState<string | null>(null);
  const [syllabusConfirmed, setSyllabusConfirmed] = useState(false);
  // Editable proposed structure — faculty confirm/correct before it becomes
  // the authoritative syllabus (persisted via POST /api/syllabi/confirm).
  const [editableUnits, setEditableUnits] = useState<EditableUnit[] | null>(null);
  const [syllabusIssues, setSyllabusIssues] = useState<string[]>([]);
  const [syllabusConfirming, setSyllabusConfirming] = useState(false);

  const [materials, setMaterials] = useState<Record<number, string>>({});
  const [materialStatus, setMaterialStatus] = useState<Record<number, UploadMovement>>({});
  const [materialErrors, setMaterialErrors] = useState<Record<number, string | null>>({});
  const [materialsSkipped, setMaterialsSkipped] = useState(false);

  const [patternMode, setPatternMode] = useState<'model-paper' | 'manual' | null>(null);
  const [modelPaperStatus, setModelPaperStatus] = useState<UploadMovement>('idle');
  const [modelPaperFileName, setModelPaperFileName] = useState<string>('');
  const [modelPaperError, setModelPaperError] = useState<string | null>(null);
  const [modelPaperAnalysis, setModelPaperAnalysis] = useState<ModelPaperAnalysis | null>(null);
  const [modelPaperConfirmed, setModelPaperConfirmed] = useState(false);

  const [sections, setSections] = useState<SectionConfig[]>(DEFAULT_SECTIONS);

  const [validationResult, setValidationResult] = useState<{ feasibility: string[]; issues: string[]; passed: boolean } | null>(null);
  const [validating, setValidating] = useState(false);

  const [generating, setGenerating] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [generatedPaperId, setGeneratedPaperId] = useState<string | null>(null);
  const [generationJobId, setGenerationJobId] = useState<string | null>(null);
  const [generationStep, setGenerationStep] = useState<string>('');
  const [jobSnapshot, setJobSnapshot] = useState<GenerationJobSnapshot | null>(null);
  const [resumingJob, setResumingJob] = useState(false);

  const { total: configuredTotal, questionCount } = useMemo(() => sectionTotals(sections), [sections]);

  const marksRemaining = totalMarks - configuredTotal;

  // ---------------------------------------------------------------------
  // Step validity guards (UX only — backend remains authoritative)
  // ---------------------------------------------------------------------
  const step0Valid = Boolean(subject.trim()) && Boolean(examType.trim()) && totalMarks > 0 && durationMinutes > 0 && selectedUnits.length > 0;
  const step1Valid = syllabusConfirmed;
  const step2Valid = true; // optional — progress is always possible
  const step3Valid = patternMode !== null && (patternMode === 'manual' || (modelPaperConfirmed && modelPaperAnalysis !== null));
  const step4Valid = marksRemaining === 0 && sections.length > 0 && sections.every((section) => section.questionCount > 0 && section.marksPerQuestion > 0 && section.name.trim().length > 0);
  const step5Valid = step4Valid && sections.every((section) => section.bloomLevels.length > 0);
  const canGenerate = step5Valid;

  const stepItems: StepperItem[] = useMemo(() => {
    const stateFor = (index: number): StepperItem['state'] => {
      if (index === step) return 'current';
      if (index < step) return 'completed';
      if (index === 2) return 'optional';
      return 'upcoming';
    };
    const base = STEP_LABELS.map(
      (label, index) => ({ label, optional: index === 2, state: stateFor(index) } as StepperItem)
    );
    if (step1Valid && step < 1) base[0].state = 'completed';
    return base;
  }, [step, step1Valid]);

  // ---------------------------------------------------------------------
  // Upload handlers
  // ---------------------------------------------------------------------
  async function handleSyllabusFile(file: File) {
    setSyllabusError(null);
    setSyllabusStatus('uploading');
    setSyllabusConfirmed(false);
    setSyllabusIssues([]);
    try {
      const result: UploadSyllabusResult = await uploadSyllabus(file, subject.trim() || 'default');
      const units = normalizeParsedUnits(result.parsed?.units ?? []);
      setSyllabusFileName(result.source_file_name || file.name);
      setSyllabusUnits(units.map((unit) => ({
        unit_number: unit.unit_number,
        title: unit.title || null,
        topics: unit.topics.map((topic) => ({ topic_name: topic }))
      })));
      // Proposed structure is always editable — a scanned page with a low
      // topic yield is corrected here, never silently accepted or fabricated.
      setEditableUnits(units);
      setSyllabusNotes(result.parsed?.notes ?? []);
      setSyllabusStatus('success');
    } catch (error) {
      setSyllabusError(messageOf(error));
      setSyllabusStatus('error');
      setSyllabusUnits([]);
      setEditableUnits(null);
      setSyllabusNotes([]);
    }
  }

  function updateEditableUnit(index: number, patch: Partial<EditableUnit>) {
    setEditableUnits((current) => {
      if (!current) return current;
      return current.map((unit, i) => (i === index ? { ...unit, ...patch } : unit));
    });
  }

  function updateEditableTopics(index: number, raw: string) {
    const topics = raw
      .split('\n')
      .map((line) => line.replace(/^\s*(?:[-•*–—]|\d+[.)]|\([a-z0-9]\))\s*/i, '').trim())
      .filter(Boolean);
    updateEditableUnit(index, { topics });
  }

  async function handleConfirmSyllabus() {
    if (!editableUnits) return;
    const issues = validationIssues(editableUnits);
    if (issues.length) {
      setSyllabusIssues(issues);
      return;
    }
    setSyllabusIssues([]);
    setSyllabusConfirming(true);
    try {
      await confirmSyllabus(
        subject.trim() || 'default',
        syllabusFileName,
        editableUnits.map((unit) => ({
          unit_number: unit.unit_number,
          title: unit.title || null,
          topics: unit.topics
        }))
      );
      // Confirmed structure becomes the authoritative syllabus for the wizard.
      setSyllabusUnits(editableUnits.map((unit) => ({
        unit_number: unit.unit_number,
        title: unit.title || null,
        topics: unit.topics.map((topic) => ({ topic_name: topic }))
      })));
      setSyllabusConfirmed(true);
    } catch (error) {
      setSyllabusIssues([messageOf(error)]);
    } finally {
      setSyllabusConfirming(false);
    }
  }

  function handleUnitMaterialForUnit(unit: number) {
    return (file: File) => doUploadUnitMaterial(unit, file);
  }

  async function doUploadUnitMaterial(unit: number, file: File) {
    setMaterialErrors((current) => ({ ...current, [unit]: null }));
    setMaterialStatus((current) => ({ ...current, [unit]: 'uploading' }));
    try {
      const result: UploadUnitMaterialResult = await uploadUnitMaterial(file, unit);
      setMaterials((current) => ({ ...current, [unit]: result.file_name || file.name }));
      setMaterialStatus((current) => ({ ...current, [unit]: 'success' }));
      setMaterialsSkipped(false);
    } catch (error) {
      setMaterialErrors((current) => ({ ...current, [unit]: messageOf(error) }));
      setMaterialStatus((current) => ({ ...current, [unit]: 'error' }));
    }
  }

  async function handleModelPaperFile(file: File) {
    setModelPaperError(null);
    setModelPaperStatus('uploading');
    setModelPaperConfirmed(false);
    try {
      const result: UploadModelPaperResult = await uploadModelPaper(file);
      setModelPaperFileName(result.source_file_name || file.name);
      setModelPaperAnalysis(result.analysis ?? null);
      applyAnalysisToPattern(result.analysis);
      setModelPaperStatus('success');
    } catch (error) {
      setModelPaperError(messageOf(error));
      setModelPaperStatus('error');
    }
  }

  function applyAnalysisToPattern(analysis: ModelPaperAnalysis | null) {
    if (!analysis) return;
    if (analysis.total_marks && analysis.total_marks > 0) setTotalMarks(analysis.total_marks);
    if (analysis.duration_minutes && analysis.duration_minutes > 0) setDurationMinutes(analysis.duration_minutes);
    if (analysis.exam_title) setExamType(analysis.exam_title);
    if (analysis.subject) setSubject(analysis.subject);
    const detected: SectionConfig[] = analysis.sections
      .filter((section) => section.name.trim())
      .map((section, index) => ({
        id: `model-${index}-${Date.now()}`,
        name: section.name,
        marksPerQuestion: section.marks_per_question && section.marks_per_question > 0 ? section.marks_per_question : index === 0 ? 2 : index === 1 ? 5 : 10,
        questionCount: section.question_count && section.question_count > 0 ? section.question_count : 3,
        difficulty: 'medium' as const,
        questionType: 'analytical',
        internalChoice: false,
        units: [],
        bloomLevels: ['L3', 'L4'] as BloomLevel[]
      }));
    if (detected.length) setSections(detected);
  }

  // ---------------------------------------------------------------------
  // Generation — authenticated, duplicate-submission safe
  // ---------------------------------------------------------------------
  function handleGenerate() {
    if (generating) return; // duplicate-submission prevention
    // Step 2 is REQUIRED: never send a blueprint built from invented topics.
    if (!syllabusConfirmed || syllabusUnits.length === 0) {
      setGenerationError(
        'Confirm your syllabus in Step 2 before generating - the paper structure is built from its units and topics.'
      );
      return;
    }
    setGenerating(true);
    setGenerationError(null);
    setGenerationStep('Preparing your question paper...');
    const { blueprint } = buildBlueprint({
      examType,
      subject,
      subjectCode,
      selectedUnits,
      totalMarks,
      durationMinutes,
      sections,
      sourceMode: patternMode === 'model-paper' ? 'model_paper' : 'manual',
      unitMaterialsPresent: !materialsSkipped && Object.keys(materials).length > 0,
      syllabusUnits
    });

    queueGenerationJob(blueprint)
      .then((job: GenerationJobSnapshot) => {
        // Accepted - the background worker takes over; the poller below tracks
        // checkpoints until completion.
        setGenerationJobId(job.id);
        setJobSnapshot(job);
      })
      .catch((error: unknown) => {
        setGenerationError(messageOf(error));
        setGenerating(false);
      });
  }

  function handleResumeJob() {
    if (!generationJobId || resumingJob) return;
    setResumingJob(true);
    resumeGenerationJob(generationJobId)
      .then((job: GenerationJobSnapshot) => {
        setJobSnapshot(job);
        setGenerationError(null);
      })
      .catch((error: unknown) => setGenerationError(messageOf(error)))
      .finally(() => setResumingJob(false));
  }

  function handleCancelJob() {
    if (!generationJobId || resumingJob) return;
    if (typeof window !== 'undefined' && !window.confirm('Cancel this generation?')) return;
    setResumingJob(true);
    cancelGenerationJob(generationJobId)
      .then((job: GenerationJobSnapshot) => setJobSnapshot(job))
      .catch((error: unknown) => setGenerationError(messageOf(error)))
      .finally(() => setResumingJob(false));
  }

  // Poll the persistent job until it reaches a terminal state.
  useEffect(() => {
    if (!generationJobId || !generating) return;
    let cancelled = false;

    const tick = async () => {
      try {
        const job = await getGenerationJob(generationJobId);
        if (cancelled) return;
        setJobSnapshot(job);
        if (job.status === 'completed' && job.paper_id) {
          setGeneratedPaperId(job.paper_id);
          setGenerationStep('Ready for review');
          setGenerating(false);
          setStep(7);
        } else if (isTerminal(job.status)) {
          setGenerationError(
            job.status === 'cancelled'
              ? 'Generation cancelled. You can start a new generation whenever you are ready.'
              : job.error_message || 'Generation failed.'
          );
          setGenerating(false);
        }
      } catch {
        // Transient network errors are retried on the next tick.
      }
    };

    const interval = setInterval(() => void tick(), POLL_INTERVAL_MS);
    void tick();
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [generationJobId, generating]);

  async function handleValidateBlueprint() {
    setValidating(true);
    setValidationResult(null);
    const { blueprint } = buildBlueprint({
      examType,
      subject,
      subjectCode,
      selectedUnits,
      totalMarks,
      durationMinutes,
      sections,
      sourceMode: (patternMode ?? 'manual') === 'model-paper' ? 'model_paper' : 'manual',
      unitMaterialsPresent: !materialsSkipped && Object.keys(materials).length > 0,
      syllabusUnits
    });
    try {
      const result = await validateBlueprint(blueprint);
      setValidationResult({
        feasibility: result.feasibility_issues ?? [],
        issues: (result.validation?.issues ?? []).map((issue: { message?: string }) => issue.message ?? ''),
        passed: Boolean(result.validation?.passed) && (result.feasibility_issues ?? []).length === 0
      });
    } catch (error) {
      setValidationResult({ feasibility: [], issues: [messageOf(error)], passed: false });
    } finally {
      setValidating(false);
    }
  }

  const stepCanNext: boolean = [
    step0Valid,
    step1Valid,
    true,
    step3Valid,
    step4Valid,
    step5Valid,
    // Step 6 (generate): block until the authoritative blueprint rules check
    // passes — never offer generation while validation is pending or failed.
    Boolean(validationResult?.passed),
    false
  ][step] ?? false;

  function handleNextClick() {
    if (step === 6) {
      handleGenerate();
      return;
    }
    setStep((current) => Math.min(current + 1, STEP_LABELS.length - 1));
  }

  function handleBackClick() {
    setStep((current) => Math.max(current - 1, 0));
  }

  // ---------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------
  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-text-muted" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-md rounded-2xl border border-white/75 bg-white/70 p-8 text-center shadow-glass-soft backdrop-blur-md">
          <h1 className="text-2xl font-semibold text-text-primary">Sign in to create a question paper</h1>
          <p className="mt-3 text-sm leading-6 text-text-secondary">Paper creation requires a faculty account so every generated paper is attributed correctly.</p>
          <Link href="/login" className="mt-6 inline-flex rounded-[0.5rem] bg-primary px-6 py-3 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="pb-8 text-text-primary">
      <section className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-8 sm:px-6 lg:px-10">
        <header className="rounded-2xl border border-white/75 bg-white/55 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
          <p className="text-metadata font-semibold uppercase tracking-[0.14em] text-text-muted">Create your question paper</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-text-primary sm:text-3xl">
            Create Your Question Paper
          </h1>
        </header>

        <MobileStepHeader step={step} total={STEP_LABELS.length} label={STEP_LABELS[step]} optional={Boolean(stepItems[step]?.optional)} />
        <div className="hidden lg:block">
          <Stepper items={stepItems} />
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            {step === 0 ? (
              <section className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <LayoutGrid className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">Subject & Exam</h2>
                </div>
                <p className="mt-1 text-sm text-text-secondary">Set the paper identity. Every value comes from your input — nothing is pre-filled.</p>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <TextInput label="Subject" value={subject} onChange={setSubject} placeholder="e.g. Data Structures" />
                  <TextInput label="Subject code" value={subjectCode} onChange={setSubjectCode} placeholder="e.g. CS301" />
                  <TextInput label="Exam type" value={examType} onChange={setExamType} placeholder="Enter the exam type" />
                  <TextInput label="Academic year" value={academicYear} onChange={setAcademicYear} placeholder="e.g. 2026-27" />
                  <NumberInput label="Total marks" value={totalMarks} onChange={setTotalMarks} min={1} />
                  <NumberInput label="Duration (minutes)" value={durationMinutes} onChange={setDurationMinutes} min={1} />
                </div>

                <div className="mt-6">
                  <p className="text-sm font-medium text-text-secondary">Selected units</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {[1, 2, 3, 4, 5].map((unit) => {
                      const selected = selectedUnits.includes(unit);
                      return (
                        <button
                          key={unit}
                          type="button"
                          onClick={() =>
                            setSelectedUnits((current) => (selected ? current.filter((value) => value !== unit) : [...current, unit]))
                          }
                          className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                            selected ? 'border-primary bg-primary text-white' : 'border-line bg-surface text-text-secondary hover:border-slate-300'
                          }`}
                        >
                          Unit {unit}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-xs text-text-muted">
                    {selectedUnits.length ? `Covering units ${selectedUnits.join(', ')}` : 'No units selected yet.'}
                  </p>
                </div>
                  <div className="mt-6 flex flex-wrap gap-2" data-testid="step1-summary">
                    {totalMarks > 0 ? <Badge tone="primary">{totalMarks} Marks</Badge> : null}
                    {durationMinutes > 0 ? <Badge tone="primary">{durationMinutes} Minutes</Badge> : null}
                    {selectedUnits.length > 0 ? <Badge tone="primary">{selectedUnits.length} Units</Badge> : null}
                    {subject.trim() ? <Badge tone="neutral">{subject}</Badge> : null}
                    {examType.trim() ? <Badge tone="neutral">{examType}</Badge> : null}
                  </div>
              </section>
            ) : null}

            {step === 1 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <FileCheck2 className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">Syllabus</h2>
                  <span className="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-xs font-semibold text-text-secondary">Required</span>
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  Upload the official syllabus (PDF or DOCX). The parsed unit structure is shown for your confirmation.
                </p>

                <div className="mt-6">
                  <UploadDrop
                    accept=".pdf,.docx,.jpg,.jpeg,.png"
                    title="Upload syllabus"
                    hint="PDF, DOCX, JPG, JPEG or PNG — up to 50 MB. Scanned pages and photos are read automatically."
                    status={syllabusStatus}
                    fileName={syllabusFileName}
                    busyLabel="Uploading and parsing syllabus…"
                    error={syllabusError}
                    onFile={handleSyllabusFile}
                    onRemove={() => {
                      setSyllabusFileName('');
                      setSyllabusUnits([]);
                      setEditableUnits(null);
                      setSyllabusNotes([]);
                      setSyllabusIssues([]);
                      setSyllabusStatus('idle');
                      setSyllabusConfirmed(false);
                    }}
                  />
                </div>

                {syllabusStatus === 'success' ? (
                  <div className="mt-6 space-y-4">
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                      Parsed syllabus: <strong>{syllabusFileName || 'uploaded file'}</strong>
                      <span className="ml-2 text-emerald-700">
                        Review the proposed structure below — edit anything the reader mis-captured, then confirm.
                      </span>
                    </div>
                    {editableUnits && editableUnits.length > 0 ? (
                      <ul className="space-y-4" data-testid="syllabus-parsed">
                        {editableUnits.map((unit, index) => (
                          <li key={unit.unit_number} className="rounded-2xl border border-white/80 bg-white/65 px-4 py-4 shadow-low backdrop-blur-sm">
                            <div className="flex items-center gap-3">
                              <span className="rounded-sm bg-primary px-3 py-1 text-metadata font-semibold text-white">
                                Unit {unit.unit_number}
                              </span>
                              <input
                                type="text"
                                value={unit.title ?? ''}
                                onChange={(event) => updateEditableUnit(index, { title: event.target.value })}
                                placeholder="Unit title"
                                data-testid={`unit-title-${unit.unit_number}`}
                                className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-text-primary outline-none focus:border-slate-400"
                              />
                              <button
                                type="button"
                                onClick={() => setEditableUnits((current) => (current ? removeUnit(current, index) : current))}
                                data-testid={`remove-unit-${unit.unit_number}`}
                                className="rounded-full border border-red-200 px-3 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                              >
                                Remove
                              </button>
                            </div>
                            <textarea
                              value={unit.topics.join('\n')}
                              onChange={(event) => updateEditableTopics(index, event.target.value)}
                              rows={Math.max(2, unit.topics.length + 1)}
                              placeholder="One topic per line"
                              data-testid={`unit-topics-${unit.unit_number}`}
                              className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm leading-6 text-text-primary outline-none focus:border-slate-400"
                            />
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800" data-testid="syllabus-empty">
                        No unit structure was detected in this file. Add the units manually below — nothing is invented for you.
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setEditableUnits((current) => addUnit(current ?? []))}
                      data-testid="add-unit"
                      className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-text-secondary hover:bg-slate-50"
                    >
                      + Add unit manually
                    </button>

                    {syllabusIssues.length ? (
                      <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" data-testid="syllabus-issues">
                        {syllabusIssues.map((issue) => (
                          <p key={issue}>{issue}</p>
                        ))}
                      </div>
                    ) : null}

                    {syllabusNotes.length ? (
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                        {syllabusNotes.map((note, noteIdx) => (
                          <p key={stableItemKey(note, noteIdx, "unassigned-note")}>{note}</p>
                        ))}
                      </div>
                    ) : null}

                    <button
                      type="button"
                      onClick={() => void handleConfirmSyllabus()}
                      disabled={syllabusConfirming}
                      className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-5 py-2.5 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100 disabled:opacity-60"
                      data-testid="confirm-syllabus"
                    >
                      {syllabusConfirming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      {syllabusConfirmed ? 'Syllabus confirmed' : 'Confirm syllabus & continue'}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}

            {step === 2 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <LayoutGrid className="h-5 w-5 text-text-muted" />
                    <h2 className="text-lg font-semibold">Add Unit Materials</h2>
                    <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-800">Optional</span>
                  </div>
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  Add reference material to improve topic coverage. You can continue without materials.
                </p>

                {materialsSkipped ? (
                  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    Continuing without materials — the syllabus content will be used as the source for the paper.
                    <button type="button" onClick={() => setMaterialsSkipped(false)} className="ml-2 font-semibold underline">
                      Add materials instead
                    </button>
                  </div>
                ) : null}

                <div className="mt-6 space-y-6">
                  {selectedUnits.length === 0 ? (
                    <p className="text-sm text-text-muted">Select units in Subject &amp; Exam first to attach materials per unit.</p>
                  ) : (
                    selectedUnits.map((unit) => (
                      <div key={unit} className="rounded-3xl border border-slate-200 bg-white/80 p-4">
                        <p className="text-sm font-semibold text-text-primary">Unit {unit}</p>
                        <p className="mt-1 text-xs text-text-muted">
                          {materials[unit] ? `Attached: ${materials[unit]}` : 'No material attached yet.'}
                        </p>
                        <div className="mt-3">
                          <UploadDrop
                            accept=".pdf,.docx,.txt"
                            title={`Add material for Unit ${unit}`}
                            hint="PDF, DOCX, or TXT"
                            status={materialStatus[unit] ?? 'idle'}
                            busyLabel={`Extracting Unit ${unit} material…`}
                            error={materialErrors[unit]}
                            onFile={handleUnitMaterialForUnit(unit)}
                            onRemove={
                              materials[unit]
                                ? () => {
                                    setMaterials((current) => {
                                      const next = { ...current };
                                      delete next[unit];
                                      return next;
                                    });
                                    setMaterialStatus((current) => ({ ...current, [unit]: 'idle' }));
                                  }
                                : undefined
                            }
                          />
                        </div>
                      </div>
                    ))
                  )}
                </div>

                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => setMaterialsSkipped(true)}
                    className="inline-flex items-center gap-2 rounded-[0.5rem] border border-primary/40 bg-transparent px-5 py-2.5 text-small font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60"
                    data-testid="continue-without-materials"
                  >
                    Continue Without Materials
                  </button>
                </div>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">Paper Pattern</h2>
                </div>
                <p className="mt-1 text-sm text-text-secondary">Choose how the paper structure is defined.</p>

                <div className="mt-6 grid gap-3 md:grid-cols-2">
                  <ModeCard
                    title="Model Paper Pattern"
                    description="Upload an official model paper so the section and mark pattern is extracted for you to confirm."
                    active={patternMode === 'model-paper'}
                    onSelect={() => setPatternMode('model-paper')}
                  />
                  <ModeCard
                    title="Manual Paper Setup"
                    description="Define the sections, marks, and question counts yourself in the Question Structure step."
                    active={patternMode === 'manual'}
                    onSelect={() => setPatternMode('manual')}
                  />
                </div>

                {patternMode === 'model-paper' ? (
                  <div className="mt-6 space-y-5">
                    <UploadDrop
                      accept=".pdf,.docx"
                      title="Upload model paper"
                      hint="PDF or DOCX"
                      status={modelPaperStatus}
                      fileName={modelPaperFileName}
                      busyLabel="Analyzing model paper pattern…"
                      error={modelPaperError}
                      onFile={handleModelPaperFile}
                      onRemove={() => {
                        setModelPaperFileName('');
                        setModelPaperAnalysis(null);
                        setModelPaperStatus('idle');
                        setModelPaperConfirmed(false);
                      }}
                    />
                  </div>
                ) : null}

                {patternMode === 'model-paper' && modelPaperAnalysis ? (
                  <div className="mt-6 space-y-4" data-testid="model-paper-analysis">
                    <div className="rounded-2xl border border-white/80 bg-white/65 px-4 py-4 shadow-low backdrop-blur-sm">
                      <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Extracted pattern</p>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        <AnalysisRow label="Exam title" value={modelPaperAnalysis.exam_title || 'Not detected'} />
                        <AnalysisRow label="Total marks" value={modelPaperAnalysis.total_marks ? `${modelPaperAnalysis.total_marks}` : 'Not detected'} />
                        <AnalysisRow label="Duration" value={modelPaperAnalysis.duration_minutes ? `${modelPaperAnalysis.duration_minutes} min` : 'Not detected'} />
                        <AnalysisRow label="Confidence" value={modelPaperAnalysis.confidence || 'unknown'} />
                      </div>
                    </div>
                    {modelPaperAnalysis.sections.length ? (
                      <div className="rounded-2xl border border-white/80 bg-white/65 px-4 py-4 shadow-low backdrop-blur-sm">
                        <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Sections detected</p>
                        <ul className="mt-2 divide-y divide-slate-100">
                          {modelPaperAnalysis.sections.map((section, index) => (
                            <li key={`${section.name}-${index}`} className="flex items-center justify-between gap-3 py-2 text-sm">
                              <span className="font-medium text-text-primary">{section.name}</span>
                              <span className="text-right text-xs text-text-muted">
                                {section.question_count ? `${section.question_count} questions` : 'count unknown'} ·{' '}
                                {section.marks_per_question ? `${section.marks_per_question} marks` : 'marks unknown'} · {section.confidence}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <p className="text-sm text-text-secondary">
                      Review the extracted pattern, then confirm. Anything marked <em>inferred</em> or <em>unknown</em> can be corrected in the Question Structure step.
                    </p>
                    <button
                      type="button"
                      onClick={() => setModelPaperConfirmed(true)}
                      className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-5 py-2.5 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100"
                      data-testid="confirm-model-paper"
                    >
                      <CheckCircle2 className="h-4 w-4" /> Confirm model pattern
                    </button>
                  </div>
                ) : null}

                {patternMode === 'manual' ? (
                  <div className="mt-6 rounded-3xl border border-slate-200 bg-white/90 p-6" data-testid="manual-config">
                    <p className="text-sm font-semibold text-text-primary">Manual Paper Setup</p>
                    <p className="mt-2 text-sm leading-6 text-text-secondary">
                      You will define the sections, marks per question, question counts, units, and evaluation levels in the next two steps.
                    </p>
                    <p className="mt-1 text-sm text-text-muted">No model paper is required for this mode.</p>
                  </div>
                ) : null}
              </div>
            ) : null}

            {step === 4 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <LayoutGrid className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">Question Structure</h2>
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  Build the paper sections. Question count × marks per question must add up to your target total.
                </p>
                <div className="mt-6">
                  <SectionBuilder
                    sections={sections}
                    selectedUnits={selectedUnits}
                    targetMarks={totalMarks}
                    onChange={setSections}
                    showBloom={false}
                  />
                </div>
              </div>
            ) : null}

            {step === 5 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">Blueprint &amp; Bloom</h2>
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  Assign evaluation levels to each section, review the distribution, and run the structure check before generation.
                </p>

                <div className="mt-6">
                  <SectionBuilder
                    sections={sections}
                    selectedUnits={selectedUnits}
                    targetMarks={totalMarks}
                    onChange={setSections}
                    showBloom
                  />
                </div>

                <div className="mt-6 rounded-3xl border border-slate-200 bg-white/90 p-5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-text-muted">Paper distribution</p>
                  <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <DistributionStat label="Questions" value={`${questionCount}`} />
                    <DistributionStat label="Section total" value={`${configuredTotal} marks`} />
                    <DistributionStat label="Target total" value={`${totalMarks} marks`} />
                    <DistributionStat label="Unallocated" value={`${marksRemaining} marks`} tone={marksRemaining === 0 ? 'ok' : 'warn'} />
                  </dl>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={handleValidateBlueprint}
                    disabled={validating || !step4Valid}
                    className="inline-flex items-center gap-2 rounded-[0.5rem] border border-primary/40 bg-transparent px-5 py-2.5 text-small font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60 disabled:opacity-50"
                    data-testid="check-blueprint"
                  >
                    {validating ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
                    {validating ? 'Checking…' : 'Check Paper Rules'}
                  </button>

                  {validationResult ? (
                    <>
                    <span className="inline-flex items-center" data-testid="validation-status">
                      <Badge tone={validationResult.passed ? 'success' : 'danger'}>{validationResult.passed ? 'Valid' : 'Needs attention'}</Badge>
                    </span>
                    <div
                      className={`flex-1 min-w-64 rounded-2xl border px-4 py-3 text-sm ${
                        validationResult.passed
                          ? 'border-success/25 bg-success-soft'
                          : 'border-danger/25 bg-danger-soft'
                      }`}
                      data-testid="validation-result"
                    >
                      <p className="font-semibold">{validationResult.passed ? 'Paper rules passed' : 'Paper rules need attention'}</p>
                      {[...validationResult.feasibility, ...validationResult.issues].map((message, index) => (
                        <p key={`${message}-${index}`} className="mt-1 text-xs">
                          • {message}
                        </p>
                      ))}
                    </div>
                  </>
                  ) : null}
                </div>
              </div>
            ) : null}

{step === 6 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-text-muted" />
                  <h2 className="text-lg font-semibold">
                    {validationResult?.passed
                      ? 'Ready to Generate Your Question Paper'
                      : 'Question distribution needs attention.'}
                  </h2>
                </div>
                <p className="mt-1 text-sm text-text-secondary">
                  {validationResult?.passed
                    ? 'Review the summary, then generate. The paper opens in the review workspace, where it must be approved before export.'
                    : 'Resolve the issues listed under Paper rules before generating. Adjust the question distribution so each question uses a different topic from its unit while unused topics remain.'}
                </p>

                <div className="mt-6 rounded-2xl border border-white/75 bg-white/55 p-5 shadow-low backdrop-blur-sm">
                  <dl className="grid grid-cols-2 gap-3 text-small sm:grid-cols-3">
                    <DistributionStat label="Subject" value={subject || 'Not selected'} />
                    <DistributionStat label="Exam" value={examType || 'Not selected'} />
                    <DistributionStat label="Units" value={selectedUnits.length ? selectedUnits.join(', ') : 'Not selected'} />
                    <DistributionStat label="Marks" value={`${configuredTotal} / ${totalMarks}`} tone={marksRemaining === 0 ? 'ok' : 'warn'} />
                    <DistributionStat label="Sections" value={`${sections.length}`} />
                    <DistributionStat label="Source" value={patternMode === 'model-paper' ? 'Model paper pattern' : patternMode === 'manual' ? 'Manual setup' : 'Not selected'} />
                  </dl>
                </div>

                {generating && jobSnapshot ? (
                  <GenerationProgressCard
                    job={jobSnapshot}
                    onResume={handleResumeJob}
                    resuming={resumingJob}
                    onRetry={handleGenerate}
                  />
                ) : null}
                {generating && !jobSnapshot ? (
                  <div
                    className="mt-6 flex items-center gap-3 rounded-2xl border border-white/75 bg-white/60 px-4 py-4 text-small text-text-secondary shadow-low backdrop-blur-sm"
                    role="status"
                  >
                    <Loader2 className="h-5 w-5 animate-spin text-primary" data-testid="generation-spinner" />
                    <span>{generationStep || 'Preparing your question paper...'}</span>
                  </div>
                ) : null}

                {generationError ? (
                  <div
                    className="mt-6 rounded-lg border border-danger/25 bg-danger-soft px-4 py-3 text-small text-danger"
                    data-testid="generation-error"
                    role="alert"
                  >
                    <p className="font-semibold">Generation couldn’t be completed.</p>
                    <p className="mt-1 text-metadata">{generationError}</p>
                    <button
                      type="button"
                      onClick={handleGenerate}
                      className="mt-3 inline-flex items-center gap-2 rounded-[0.5rem] border border-danger/40 bg-surface px-4 py-1.5 text-metadata font-semibold text-danger transition-colors duration-micro hover:bg-surface-elevated"
                    >
                      <RefreshCw className="h-3.5 w-3.5" /> Try again
                    </button>
                  </div>
                ) : null}

                {generating && jobSnapshot && (jobSnapshot.status === 'queued' || jobSnapshot.status === 'running') ? (
                  <button
                    type="button"
                    onClick={handleCancelJob}
                    disabled={resumingJob}
                    className="mt-4 inline-flex items-center gap-2 rounded-[0.5rem] border border-line bg-surface px-4 py-2 text-metadata font-medium text-text-secondary transition-colors duration-micro hover:bg-slate-50 disabled:opacity-60"
                    data-testid="generation-cancel"
                  >
                    Cancel Generation
                  </button>
                ) : null}

                <div className="mt-6">
                  <button
                    type="button"
                    onClick={handleGenerate}
                    disabled={!canGenerate || generating}
                    className="inline-flex items-center gap-2 rounded-[0.5rem] bg-primary px-6 py-3 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover disabled:opacity-50"
                    data-testid="generate-paper"
                  >
                    <Sparkles className="h-4 w-4" />
                    {generating ? 'Generating…' : 'Generate Question Paper'}
                  </button>
                  {!canGenerate ? (
                    <p className="mt-2 text-xs text-text-muted">Complete the previous steps and balance the paper total before generating.</p>
                  ) : null}
                </div>
              </div>
            ) : null}
            {step === 7 ? (
              <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-md sm:p-8">
                {generatedPaperId ? (
                  <div className="space-y-4" data-testid="generation-complete">
                    <div className="flex items-center gap-2 text-success">
                      <CheckCircle2 className="h-6 w-6" aria-hidden="true" />
                      <h2 className="text-lg font-semibold">Your question paper is ready</h2>
                    </div>
                    <p className="text-small text-text-secondary">
                      Your questions have been generated and validated. Open the review workspace
                      to edit, regenerate, lock, and export it.
                    </p>
                    <div className="flex flex-wrap gap-2" data-testid="generation-complete-summary">
                      <Badge tone="success">✓ Question paper ready</Badge>
                      <Badge tone="neutral">{questionCount} questions</Badge>
                      <Badge tone="neutral">{configuredTotal} marks</Badge>
                      <Badge tone="neutral">{durationMinutes} minutes</Badge>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <Link
                        href={`/review?paper_id=${generatedPaperId}`}
                        className="inline-flex items-center gap-2 rounded-[0.5rem] bg-primary px-5 py-3 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover"
                      >
                        Review Question Paper <ArrowRight className="h-4 w-4" aria-hidden="true" />
                      </Link>
                      <Link
                        href="/dashboard"
                        className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-text-secondary transition hover:bg-slate-100"
                      >
                        Back to dashboard
                      </Link>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3" data-testid="generation-empty">
                    <h2 className="text-lg font-semibold text-text-primary">Ready to Review</h2>
                    <p className="text-sm text-text-secondary">Generate the paper first, then return here to open the review workspace.</p>
                    <button
                      type="button"
                      onClick={() => setStep(6)}
                      className="inline-flex items-center gap-2 rounded-[0.5rem] border border-primary/40 bg-transparent px-5 py-2.5 text-small font-semibold text-primary transition-colors duration-micro hover:bg-primary-soft/60"
                    >
                      <ArrowLeft className="h-4 w-4" /> Back to Generate
                    </button>
                  </div>
                )}
              </div>
            ) : null}
          </div>

          <aside className="space-y-6" data-testid="wizard-summary">
            <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-glass sm:p-8">
              <h3 className="text-sm font-medium text-text-muted">Paper summary</h3>
              <dl className="mt-4 space-y-3 text-sm">
                <SummaryRow label="Subject" value={subject || 'Not selected'} />
                <SummaryRow label="Exam" value={examType || 'Not selected'} />
                <SummaryRow label="Units" value={selectedUnits.length ? selectedUnits.join(', ') : 'Not selected'} />
                <SummaryRow label="Marks" value={totalMarks ? `${totalMarks}` : 'Not selected'} />
                <SummaryRow label="Duration" value={durationMinutes ? `${durationMinutes} min` : 'Not selected'} />
                <SummaryRow label="Paper total" value={`${configuredTotal} marks`} />
                <SummaryRow label="Pattern" value={patternMode === 'model-paper' ? 'Model paper' : patternMode === 'manual' ? 'Manual' : 'Not selected'} />
                <SummaryRow
                  label="Materials"
                  value={materialsSkipped ? 'Skipped' : Object.keys(materials).length ? `${Object.keys(materials).length} uploaded` : 'None yet'}
                />
              </dl>
            </div>

            <div className="rounded-2xl border border-white/75 bg-white/70 p-6 shadow-glass-soft backdrop-blur-glass sm:p-8">
              <h3 className="text-sm font-medium text-text-muted">Quality checks</h3>
              <div className="mt-4 space-y-3 text-sm">
                <CheckRow label="Syllabus confirmed" ok={syllabusConfirmed} />
                <CheckRow label="Marks structure balanced" ok={step4Valid} />
                <CheckRow label="Evaluation levels set" ok={step5Valid} />
                <CheckRow label="Rules check passed" ok={Boolean(validationResult?.passed)} />
              </div>
            </div>
          </aside>
        </div>

        <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/75 bg-white/85 px-5 py-4 shadow-high backdrop-blur-md">
          <button
            type="button"
            onClick={handleBackClick}
            disabled={step === 0}
            className="inline-flex items-center gap-2 rounded-[0.5rem] border border-line bg-surface px-4 py-2 text-small font-semibold text-text-secondary transition-colors duration-micro hover:bg-slate-50 disabled:opacity-40"
          >
            <ArrowLeft className="h-4 w-4" /> Back
          </button>
          <div className="text-sm text-text-muted">
            Step {step + 1} of {STEP_LABELS.length}
            {!stepCanNext && step !== 7 ? (
              <span className="ml-2 text-xs text-text-muted">Complete the required fields to continue</span>
            ) : null}
          </div>
          {step < 7 ? (
            <button
              type="button"
              onClick={handleNextClick}
              disabled={!stepCanNext || (step === 6 && generating)}
              className="inline-flex items-center gap-2 rounded-[0.5rem] bg-primary px-5 py-2 text-small font-semibold text-white transition-colors duration-micro hover:bg-primary-hover disabled:opacity-40"
              data-testid="wizard-next"
            >
              {step === 6 ? 'Generate Question Paper' : 'Next'}
              <ArrowRight className="h-4 w-4" />
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function TextInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (value: string) => void; placeholder?: string }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-text-primary outline-none transition placeholder:text-text-muted focus:border-slate-400"
      />
    </label>
  );
}

function NumberInput({ label, value, onChange, min }: { label: string; value: number; onChange: (value: number) => void; min?: number }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wider text-text-muted">{label}</span>
      <input
        type="number"
        min={min}
        value={Number.isFinite(value) ? value : ''}
        onChange={(event) => {
          const parsed = parseInt(event.target.value, 10);
          onChange(Number.isFinite(parsed) ? Math.max(min ?? 0, parsed) : 0);
        }}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-text-primary outline-none transition focus:border-slate-400"
      />
    </label>
  );
}

function ModeCard({ title, description, active, onSelect }: { title: string; description: string; active: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`rounded-3xl border px-4 py-4 text-left transition ${
        active ? 'border-primary bg-primary-soft/60 text-text-primary shadow-low' : 'border-line bg-surface text-text-secondary hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <p className="font-semibold">{title}</p>
      <p className={`mt-1.5 text-sm leading-5 ${active ? 'text-slate-300' : 'text-text-muted'}`}>{description}</p>
    </button>
  );
}

function AnalysisRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-xl border border-slate-100 bg-white px-3 py-2 text-sm">
      <span className="text-xs font-medium uppercase tracking-wider text-text-muted">{label}</span>
      <span className="font-semibold text-text-primary">{value}</span>
    </div>
  );
}

function DistributionStat({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'warn' }) {
  const toneClass = tone === 'ok' ? 'text-emerald-700' : tone === 'warn' ? 'text-amber-700' : 'text-text-primary';
  return (
    <div>
      <dt className="text-xs uppercase tracking-wider text-text-muted">{label}</dt>
      <dd className={`mt-0.5 text-sm font-semibold ${toneClass}`}>{value}</dd>
    </div>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/60 pb-2 text-sm last:border-b-0 last:pb-0">
      <dt className="text-text-muted">{label}</dt>
      <dd className="font-medium text-text-primary">{value}</dd>
    </div>
  );
}

function CheckRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-text-secondary">{label}</span>
      {ok ? (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5" /> Passed
        </span>
      ) : (
        <span className="text-xs font-semibold text-text-muted">Pending</span>
      )}
    </div>
  );
}

function messageOf(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'string') return error;
  return 'Something went wrong. Please try again.';
}
function MobileStepHeader({ step, total, label, optional }: { step: number; total: number; label: string; optional: boolean }) {
  const percent = Math.round(((step + 1) / total) * 100);
  return (
    <div
      className="rounded-2xl border border-white/75 bg-white/60 p-4 shadow-glass-soft backdrop-blur-md lg:hidden"
      aria-label={'Step ' + (step + 1) + ' of ' + total + ': ' + label}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-metadata font-medium text-text-muted">
          Step {step + 1} of {total}
        </p>
        {optional ? <Badge tone="warning">Optional</Badge> : null}
      </div>
      <p className="mt-1 text-small font-semibold text-text-primary" aria-current="step">{label}</p>
      <div
        className="mt-3 h-1.5 w-full overflow-hidden rounded-pill bg-slate-200"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Wizard progress"
      >
        <div className="h-full rounded-pill bg-primary transition-all duration-panel ease-standard" style={{ width: percent + '%' }} />
      </div>
    </div>
  );
}
