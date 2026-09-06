import {
  buildBlueprint,
  createSection,
  DEFAULT_SECTIONS,
  sectionTotal,
  sectionTotals
} from '../lib/wizard-logic';
import type { SectionConfig, SyllabusUnit } from '../lib/wizard-logic';

describe('sectionTotals', () => {
  it('computes the total for a 2/5/10 mark paper (6×2 + 4×5 + 3×10 = 62)', () => {
    const sections: SectionConfig[] = [
      { ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 6 },
      { ...createSection(), name: 'Section B', marksPerQuestion: 5, questionCount: 4 },
      { ...createSection(), name: 'Section C', marksPerQuestion: 10, questionCount: 3 }
    ];
    const result = sectionTotals(sections);
    expect(result.total).toBe(62);
    expect(result.questionCount).toBe(13);
    expect(Object.values(result.bySection).sort((a: number, b: number) => a - b)).toEqual([12, 20, 30]);
  });

  it('reports the per-section total as questionCount * marksPerQuestion', () => {
    const section = createSection({ marksPerQuestion: 5, questionCount: 4 });
    expect(sectionTotal(section)).toBe(20);
  });

  it('reports a mark mismatch that must block generation', () => {
    const sections: SectionConfig[] = [
      { ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 6 }
    ];
    // target 70 → 58 allocated → 12 unallocated
    expect(sectionTotals(sections).total).toBe(12);
  });
});

describe('DEFAULT_SECTIONS', () => {
  it('keeps the 2/5/10 mark structure with no demo academic data', () => {
    expect(DEFAULT_SECTIONS).toHaveLength(3);
    expect(DEFAULT_SECTIONS.map((section) => section.marksPerQuestion)).toEqual([2, 5, 10]);
    const names = DEFAULT_SECTIONS.map((section) => section.name);
    expect(names).not.toContain('Data Mining');
    expect(names).not.toContain('Clustering');
  });
});

describe('buildBlueprint', () => {
  const selectedUnits = [1, 2, 3];
  const syllabusUnits: SyllabusUnit[] = [
    { unit_number: 1, title: 'Unit 1 — FDBS', topics: [{ topic_name: 'Fundamentals of Databases' }] },
    { unit_number: 2, title: 'Unit 2 — Indexing', topics: [{ topic_name: 'Indexing Structures' }] }
  ];

  function blueprintFor(sections: SectionConfig[], overrides: Partial<Record<string, unknown>> = {}) {
    return buildBlueprint({
      examType: 'Mid Semester 1',
      subject: 'Databases',
      subjectCode: 'DB-301',
      selectedUnits,
      totalMarks: 62,
      durationMinutes: 180,
      sections,
      sourceMode: 'manual',
      unitMaterialsPresent: true,
      syllabusUnits,
      ...overrides
    });
  }

  it('creates contiguous question numbers starting at 1', () => {
    const { questions } = blueprintFor(DEFAULT_SECTIONS);
    expect(questions.map((question) => question.question_number)).toEqual(
      Array.from({ length: questions.length }, (_, index) => index + 1)
    );
  });

  it('matches section question_count and marks_per_question', () => {
    const { sections, questions } = blueprintFor(DEFAULT_SECTIONS);
    for (const section of sections) {
      const sectionQuestions = questions.filter((question) => question.section === section.name);
      expect(sectionQuestions).toHaveLength(Number(section.question_count));
      expect(sectionQuestions.every((question) => question.marks === section.marks_per_question)).toBe(true);
    }
  });

  it('keeps question units inside the selected scope', () => {
    const { questions } = blueprintFor(DEFAULT_SECTIONS);
    expect(questions.every((question) => selectedUnits.includes(question.unit))).toBe(true);
  });

  it('assigns Bloom levels only from the section allowance', () => {
    const { questions } = blueprintFor(DEFAULT_SECTIONS);
    const sectionB = questions.filter((question) => question.section === 'Section B');
    expect(sectionB.every((question) => ['L3', 'L4'].includes(question.bloom_level))).toBe(true);
  });

  it('uses real syllabus topics instead of fabricated demo data', () => {
    const { questions } = blueprintFor(DEFAULT_SECTIONS);
    const topics = questions.map((question) => question.topic);
    expect(topics).toContain('Fundamentals of Databases');
    expect(topics).toContain('Indexing Structures');
    expect(topics.some((topic) => topic.toLowerCase().includes('clustering'))).toBe(false);
    expect(topics.some((topic) => topic.toLowerCase().includes('data mining'))).toBe(false);
  });

  it('sets source_mode and unit_materials_present from the input', () => {
    const withMaterials = blueprintFor(DEFAULT_SECTIONS, { sourceMode: 'manual', unitMaterialsPresent: true });
    expect(withMaterials.blueprint.source_mode).toBe('manual');
    expect(withMaterials.blueprint.unit_materials_present).toBe(true);

    const model = blueprintFor(DEFAULT_SECTIONS, { sourceMode: 'model_paper', unitMaterialsPresent: false });
    expect(model.blueprint.source_mode).toBe('model_paper');
    expect(model.blueprint.unit_materials_present).toBe(false);
  });

  it('adds a choice group value when a section uses internal choice', () => {
    const sections = [
      { ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 2, internalChoice: true }
    ];
    const { questions } = blueprintFor(sections);
    expect(questions).toHaveLength(2);
    expect(questions.every((question) => Boolean(question.choice_group))).toBe(true);
    // internal choice pairs are grouped two at a time
    expect(questions[0].choice_group).toBe(questions[1].choice_group);
  });
});

describe('buildBlueprint topic allocation (Operating Systems MID 1)', () => {
  // Realistic OS syllabus where the extractor returned comma-joined topics —
  // the shape that previously made the pool look tiny and caused
  // exact_duplicate_topic validation failures.
  const osSyllabus: SyllabusUnit[] = [
    {
      unit_number: 1,
      title: 'Unit 1 — Operating Systems Overview',
      topics: [{ topic_name: 'Operating system structure, Operating system operations, Process management fundamentals' }]
    },
    {
      unit_number: 2,
      title: 'Unit 2 — Process Management',
      topics: [
        { topic_name: 'Process scheduling, Operations on processes, Inter-process communication' },
        { topic_name: 'CPU scheduling criteria' }
      ]
    }
  ];

  const compositeSections: SectionConfig[] = [
    { ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 10, units: [1, 2], bloomLevels: ['L2', 'L3'], difficulty: 'easy' },
    { ...createSection(), name: 'Section B', marksPerQuestion: 5, questionCount: 6, units: [1, 2], bloomLevels: ['L3', 'L4'], difficulty: 'medium' }
  ];

  function osBlueprint(sections: SectionConfig[]) {
    return buildBlueprint({
      examType: 'MID 1',
      subject: 'OPERATING SYSTEMS',
      selectedUnits: [1, 2],
      totalMarks: sections.reduce((sum, s) => sum + s.questionCount * s.marksPerQuestion, 0),
      durationMinutes: 110,
      sections,
      sourceMode: 'manual',
      unitMaterialsPresent: true,
      syllabusUnits: osSyllabus
    });
  }

  it('splits comma-joined extracted topics into the real topic pool', () => {
    const { questions } = osBlueprint([{ ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 8, units: [2] }]);
    const unit2Topics = questions.filter((q) => q.unit === 2).map((q) => q.topic);
    expect(new Set(unit2Topics).size).toBeGreaterThan(1);
    // the original joined blob must no longer be handed out as one "topic"
    expect(unit2Topics).not.toContain('Process scheduling, Operations on processes, Inter-process communication');
    expect(unit2Topics).toContain('Process scheduling');
    expect(unit2Topics).toContain('Inter-process communication');
  });

  it('assigns distinct topics while unused eligible topics remain', () => {
    const { questions } = osBlueprint(compositeSections);
    const byUnit = new Map<number, string[]>();
    for (const q of questions) {
      byUnit.set(q.unit, [...(byUnit.get(q.unit) ?? []), q.topic]);
    }
    for (const [unit, topics] of byUnit) {
      const available = unit === 1 ? 3 : 4; // pool sizes after splitting
      const assigned = topics.length;
      const distinct = new Set(topics).size;
      // every topic distinct until the pool wraps
      expect(distinct).toBe(Math.min(assigned, available));
    }
  });

  it('reuses a topic only after the unit pool is exhausted', () => {
    // 5 questions from unit 1 whose pool is 3 topics → 3 distinct + 2 reused
    const { questions } = osBlueprint([{ ...createSection(), name: 'Section A', marksPerQuestion: 2, questionCount: 5, units: [1] }]);
    const topics = questions.map((q) => q.topic);
    expect(new Set(topics).size).toBe(3);
    expect(topics[0]).toBe(topics[3]); // wraps in syllabus order after exhaustion
    expect(topics[1]).toBe(topics[4]);
  });

  it('round-robins across multiple units and keeps unit/marks/bloom intact', () => {
    const { questions } = osBlueprint(compositeSections);
    const units = questions.map((q) => q.unit);
    expect(new Set(units)).toEqual(new Set([1, 2]));
    const sectionA = questions.filter((q) => q.section === 'Section A');
    expect(sectionA.every((q) => q.marks === 2)).toBe(true);
    expect(sectionA.every((q) => ['L2', 'L3'].includes(q.bloom_level))).toBe(true);
    const sectionB = questions.filter((q) => q.section === 'Section B');
    expect(sectionB.every((q) => q.marks === 5)).toBe(true);
    expect(sectionB.every((q) => ['L3', 'L4'].includes(q.bloom_level))).toBe(true);
    expect(questions.every((q) => ['easy', 'medium'].includes(q.difficulty))).toBe(true);
  });

  it('does not fabricate topics outside the syllabus', () => {
    const { questions } = osBlueprint(compositeSections);
    const allowed = new Set([
      'Operating system structure', 'Operating system operations', 'Process management fundamentals',
      'Process scheduling', 'Operations on processes', 'Inter-process communication', 'CPU scheduling criteria'
    ]);
    for (const q of questions) {
      expect(allowed.has(q.topic)).toBe(true);
    }
  });
});