// Pure logic helpers for the syllabus ingestion + faculty-confirmation flow.
// Kept dependency-free so they are trivially unit-testable.

export interface EditableUnit {
  unit_number: number;
  title: string;
  topics: string[];
}

export interface ParseOutcome {
  status: 'pending' | 'parsed' | 'manual' | 'failed';
  units: EditableUnit[];
  warnings: string[];
  ocr_used: boolean;
  confidence: string;
}

// Backend unit payloads vary slightly (optional title, optional confidence);
// accept the superset and normalise to the strict editable shape.
export type ParsedUnitInput = {
  unit_number: number;
  title?: string | null;
  confidence?: string;
  topics: Array<{ topic_name: string } | string>;
};

export function normalizeParsedUnits(units: ParsedUnitInput[]): EditableUnit[] {
  return (units ?? [])
    .filter((u) => u && typeof u.unit_number === 'number')
    .map((u) => ({
      unit_number: u.unit_number,
      title: u.title ?? '',
      topics: (u.topics ?? []).map((t) => (typeof t === 'string' ? t : t?.topic_name ?? '')).filter(Boolean)
    }));
}

// Map a syllabus-upload response into the editor's editable structure.
export function parseUploadResult(payload: {
  parsed: { units: Array<{ unit_number: number; title: string | null; topics: Array<{ topic_name: string }> }> };
  warnings: string[];
  ocr_used: boolean;
}): ParseOutcome {
  const units = normalizeParsedUnits(payload.parsed?.units ?? []);
  const warnings = payload.warnings ?? [];
  if (units.length === 0) {
    return {
      status: 'failed',
      units: [],
      warnings,
      ocr_used: !!payload.ocr_used,
      confidence: 'unknown'
    };
  }
  // If OCR was used and there are warnings, treat as low-confidence-but-editable.
  return {
    status: 'parsed',
    units,
    warnings,
    ocr_used: !!payload.ocr_used,
    confidence: 'inferred'
  };
}

// Validators for the confirmation editor before it can be submitted.
export function validationIssues(units: EditableUnit[]): string[] {
  const issues: string[] = [];
  if (units.length === 0) {
    issues.push('Add at least one unit before confirming.');
  }
  const numbers = units.map((u) => u.unit_number);
  if (new Set(numbers).size !== numbers.length) {
    issues.push('Duplicate unit numbers are not allowed.');
  }
  for (const u of units) {
    if (u.topics.length === 0) {
      issues.push(`Unit ${u.unit_number} has no topics.`);
    }
    if (u.topics.some((t) => !t.trim())) {
      issues.push(`Unit ${u.unit_number} contains an empty topic.`);
    }
  }
  return issues;
}

export function addUnit(units: EditableUnit[]): EditableUnit[] {
  const nextNumber = units.length ? Math.max(...units.map((u) => u.unit_number)) + 1 : 1;
  return [...units, { unit_number: nextNumber, title: `Unit ${nextNumber}`, topics: [] }];
}

export function removeUnit(units: EditableUnit[], index: number): EditableUnit[] {
  return units.filter((_, i) => i !== index);
}

export function moveTopic(units: EditableUnit[], unitIndex: number, from: number, dir: 1 | -1): EditableUnit[] {
  const topics = [...units[unitIndex].topics];
  const to = from + dir;
  if (to < 0 || to >= topics.length) return units;
  [topics[from], topics[to]] = [topics[to], topics[from]];
  return units.map((u, i) => (i === unitIndex ? { ...u, topics } : u));
}
