// Pure, testable logic for the paper-creation wizard.
// No React, no network — safe to unit test in isolation.

export type BloomLevel = 'L2' | 'L3' | 'L4' | 'L5' | 'L6';
export type Difficulty = 'easy' | 'medium' | 'hard';

export interface SectionConfig {
  id: string;
  name: string;
  marksPerQuestion: number;
  questionCount: number;
  difficulty: Difficulty;
  questionType: string;
  internalChoice: boolean;
  units: number[]; // unit numbers this section draws from; empty = all selected units
  bloomLevels: BloomLevel[]; // allowed Bloom levels assigned to this section
}

export interface SyllabusUnit {
  unit_number: number;
  title?: string | null;
  topics: Array<{ topic_name: string }>;
}

export interface BlueprintQuestion {
  question_number: number;
  section: string;
  marks: number;
  unit: number;
  topic: string;
  bloom_level: BloomLevel;
  difficulty: string;
  question_type: string;
  choice_group: string | null;
}

export interface SectionTotalResult {
  bySection: Record<string, number>;
  total: number;
  questionCount: number;
}

export function sectionTotal(section: SectionConfig): number {
  return section.questionCount * section.marksPerQuestion;
}

export function sectionTotals(sections: SectionConfig[]): SectionTotalResult {
  const bySection: Record<string, number> = {};
  let total = 0;
  let questionCount = 0;
  for (const section of sections) {
    const value = sectionTotal(section);
    bySection[section.id] = value;
    total += value;
    questionCount += section.questionCount;
  }
  return { bySection, total, questionCount };
}

function unitTopicList(units: SyllabusUnit[], unit: number): string[] {
  const found = units.find((item) => item.unit_number === unit);
  if (found) {
    if (found.topics.length) {
      // Extracted/pasted topics are often comma- or semicolon-joined into a
      // single entry (e.g. "Scheduling, IPC, Threads"). Splitting them gives
      // the allocator the real topic pool so distinct topics are assigned
      // while unused eligible topics remain, and reuse only happens after the
      // pool is genuinely exhausted.
      return found.topics.flatMap((topic) =>
        topic.topic_name
          .split(/[;,•\n]+/)
          .map((part) => part.trim())
          .filter(Boolean)
      );
    }
    if (found.title) return [found.title];
  }
  return [`Unit ${unit}`];
}

function choiceGroupLabel(sectionName: string, index: number): string {
  const pair = Math.floor(index / 2);
  const slug = sectionName.toLowerCase().replace(/\s+/g, '_') || 'section';
  return `${slug}_op${pair + 1}`;
}

function sectionType(marksPerQuestion: number): string {
  return marksPerQuestion >= 5 ? 'descriptive' : 'short_answer';
}

export function buildBlueprint(args: {
  examType: string;
  subject: string;
  subjectCode?: string;
  selectedUnits: number[];
  totalMarks: number;
  durationMinutes: number;
  sections: SectionConfig[];
  sourceMode: 'model_paper' | 'manual';
  unitMaterialsPresent: boolean;
  syllabusUnits: SyllabusUnit[];
}): { sections: Array<Record<string, unknown>>; questions: BlueprintQuestion[]; blueprint: Record<string, unknown> } {
  const sections = args.sections.map((section) => {
    const choice = section.internalChoice
      ? 'Answer any one from each paired option.'
      : `Answer all ${section.questionCount} questions.`;
    return {
      name: section.name,
      section_type: sectionType(section.marksPerQuestion),
      question_count: section.questionCount,
      marks_per_question: section.marksPerQuestion,
      instructions: `${section.name} — ${section.marksPerQuestion} marks each. ${choice}`
    };
  });

  const questions: BlueprintQuestion[] = [];
  let number = 1;
  // Per-unit topic cursors shared across ALL sections: a unit's topic pool is
  // walked continuously so reuse happens only after the pool is exhausted.
  const cursors = new Map<number, number>();
  for (const section of args.sections) {
    const pool = section.units.length ? section.units : args.selectedUnits;
    const units = pool.length ? pool : [1];
    const blooms = section.bloomLevels.length
      ? section.bloomLevels
      : section.marksPerQuestion <= 2
        ? (['L2', 'L3'] as BloomLevel[])
        : (['L3', 'L4', 'L5'] as BloomLevel[]);

    for (let i = 0; i < section.questionCount; i++) {
      const unit = units[i % units.length];
      const bloom = blooms[i % blooms.length];
      // Per-unit cursor shared ACROSS sections (declared outside the section
      // loop): each unit's topic list is walked forward continuously so
      // questions stay on distinct topics for as long as the syllabus allows
      // and only wrap once a unit's list is genuinely exhausted.
      const topicCursor = cursors.get(unit) ?? 0;
      cursors.set(unit, topicCursor + 1);
      const topicList = unitTopicList(args.syllabusUnits, unit);
      questions.push({
        question_number: number,
        section: section.name,
        marks: section.marksPerQuestion,
        unit,
        topic: topicList[topicCursor % topicList.length],
        bloom_level: bloom,
        difficulty: section.difficulty,
        question_type: section.questionType,
        choice_group: section.internalChoice ? choiceGroupLabel(section.name, i) : null
      });
      number++;
    }
  }

  const blueprint: Record<string, unknown> = {
    exam_type: args.examType,
    subject: args.subject,
    selected_units: args.selectedUnits,
    total_marks: args.totalMarks,
    duration_minutes: args.durationMinutes,
    sections,
    questions,
    source_mode: args.sourceMode,
    unit_materials_present: args.unitMaterialsPresent
  };

  return { sections, questions, blueprint };
}

export function createSection(overrides: Partial<SectionConfig> = {}): SectionConfig {
  const id =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `sec-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
  return {
    id,
    name: 'Section A',
    marksPerQuestion: 2,
    questionCount: 6,
    difficulty: 'easy',
    questionType: 'conceptual',
    internalChoice: false,
    units: [],
    bloomLevels: ['L2', 'L3'],
    ...overrides
  };
}

export const DEFAULT_SECTIONS: SectionConfig[] = [
  createSection({ name: 'Section A', marksPerQuestion: 2, questionCount: 6, difficulty: 'easy', questionType: 'conceptual', bloomLevels: ['L2', 'L3'] }),
  createSection({ name: 'Section B', marksPerQuestion: 5, questionCount: 4, difficulty: 'medium', questionType: 'application', bloomLevels: ['L3', 'L4'] }),
  createSection({ name: 'Section C', marksPerQuestion: 10, questionCount: 3, difficulty: 'hard', questionType: 'analytical', bloomLevels: ['L4', 'L5', 'L6'] })
];

export const BLOOM_OPTIONS: Array<{ value: BloomLevel; label: string }> = [
  { value: 'L2', label: 'L2 · Understand' },
  { value: 'L3', label: 'L3 · Apply' },
  { value: 'L4', label: 'L4 · Analyze' },
  { value: 'L5', label: 'L5 · Evaluate' },
  { value: 'L6', label: 'L6 · Create' }
];

export const QUESTION_TYPES = ['conceptual', 'application', 'analytical', 'numerical', 'case_based', 'comparative'];

export const DIFFICULTY_OPTIONS: Array<{ value: Difficulty; label: string }> = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' }
];

