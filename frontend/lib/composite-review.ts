/**
 * Composite examination Review helpers (Phase 4).
 *
 * Pure functions that turn a paper draft's `paper_json` into the view model the
 * Review UI renders. The legacy flat `sections`/`questions` shape remains fully
 * supported; composite papers additionally expose `parts.part_a` and
 * `parts.part_b.groups`.
 */

export type AnyRecord = Record<string, any>;
export interface CompositeQuestionIdentity {
  exam_part?: 'short_answer' | 'main';
  question_number?: number;
  group_number?: number | null;
  part_label?: string | null;
}

export interface PartAHeader {
  name: string;
  questionCount: number;
  marksPerQuestion: number;
  totalMarks: number;
  durationMinutes: number | null;
}

export interface OrCluster<T> {
  /** null when the group is compulsory (no choice relationship). */
  choiceGroupId: string | null;
  groups: T[];
}

export function isCompositePaper(paperJson: AnyRecord | undefined | null): boolean {
  const parts = paperJson?.parts;
  return Boolean(parts && (parts.part_a || parts.part_b));
}

export function getPartA(paperJson: AnyRecord | undefined | null): AnyRecord {
  return paperJson?.parts?.part_a ?? {};
}

export function getPartB(paperJson: AnyRecord | undefined | null): AnyRecord {
  return paperJson?.parts?.part_b ?? {};
}

/** Ordered Part A questions (falls back to the legacy flat list). */
export function getPartAQuestions(paperJson: AnyRecord | undefined | null): AnyRecord[] {
  const questions = getPartA(paperJson).questions;
  return Array.isArray(questions) ? questions : [];
}

export function getPartAHeader(
  paperJson: AnyRecord | undefined | null,
): PartAHeader {
  const partA = getPartA(paperJson);
  const questions = getPartAQuestions(paperJson);
  const marksEach = Number(partA.questions?.[0]?.marks) ||
    Number(questions[0]?.marks) || 0;
  return {
    name: String(partA.name || 'PART A - SHORT ANSWER'),
    questionCount: questions.length,
    marksPerQuestion: marksEach,
    totalMarks: Number(partA.total_marks) || questions.length * marksEach,
    durationMinutes: partA.duration_minutes ?? null,
  };
}

/** Ordered Part B question groups. */
export function getPartBGroups(paperJson: AnyRecord | undefined | null): AnyRecord[] {
  const groups = getPartB(paperJson).groups;
  return Array.isArray(groups) ? groups : [];
}

/**
 * Cluster Part B groups by their persisted choice-group membership.
 *
 * Alternatives are grouped ONLY by the explicit `choice_group_id` that was
 * persisted during generation - never inferred from numbering. Groups without
 * membership are returned as standalone clusters.
 */
export function clusterGroupsByChoice(
  groups: AnyRecord[],
): OrCluster<AnyRecord>[] {
  const clusters: OrCluster<AnyRecord>[] = [];
  const indexByChoice = new Map<string, OrCluster<AnyRecord>>();

  for (const group of groups) {
    const choiceGroupId: string | null = group.choice_group ?? null;
    if (choiceGroupId && indexByChoice.has(choiceGroupId)) {
      indexByChoice.get(choiceGroupId)!.groups.push(group);
      continue;
    }
    const cluster: OrCluster<AnyRecord> = { choiceGroupId, groups: [group] };
    clusters.push(cluster);
    if (choiceGroupId) indexByChoice.set(choiceGroupId, cluster);
  }
  return clusters;
}

/**
 * True when the parts inside ONE group are themselves alternatives
 * (part-level OR, e.g. 2(a) <=> 2(b)).
 */
export function hasPartLevelChoice(group: AnyRecord): boolean {
  const members = group.parts
    ?.map((part: AnyRecord) => part.choice_member_id)
    .filter(Boolean) ?? [];
  return members.length >= 2;
}

/** Stable key identifying one generated alternative/part for React lists. */
export function partKey(groupNumber: number, part: AnyRecord): string {
  return `${groupNumber}${part.part_label ?? ''}`;
}

export function questionIdentity(question: AnyRecord): CompositeQuestionIdentity {
  return {
    exam_part: question.exam_part,
    question_number: typeof question.question_number === 'number' ? question.question_number : Number(question.question_number),
    group_number: question.group_number == null ? null : Number(question.group_number),
    part_label: question.part_label ?? null,
  };
}

export function questionActionKey(question: CompositeQuestionIdentity): string {
  if (question.exam_part === 'short_answer' && question.question_number != null) {
    return `short_answer:q${question.question_number}`;
  }
  if (question.exam_part === 'main' && question.group_number != null && question.part_label) {
    return `main:g${question.group_number}:${String(question.part_label).toLowerCase()}`;
  }
  return `legacy:q${question.question_number ?? 'unknown'}`;
}

/** Display label for an alternative, e.g. "2(a)". */
export function partDisplayLabel(groupNumber: number, part: AnyRecord): string {
  const label = part.part_label ? `(${part.part_label})` : '';
  return `${group_number_label(groupNumber)}${label}`;
}

function group_number_label(groupNumber: number): string {
  return String(groupNumber);
}

/** Total marks printed across every alternative of a cluster. */
export function clusterPrintedMarks(cluster: OrCluster<AnyRecord>): number {
  return cluster.groups.reduce(
    (sum, group) => sum + (group.parts ?? []).reduce(
      (s: number, p: AnyRecord) => s + Number(p.marks || 0), 0),
    0,
  );
}

// ---------------------------------------------------------------------------
// Persisted validation record (paper_json.validation)
// ---------------------------------------------------------------------------
//
// Two persisted shapes flow through the same source of truth:
//   * composite: { passed, errors[], warnings[], issues[] } — `errors` is the
//     explicit blocking set; `warnings` never block.
//   * legacy flat: { passed, issues[] } (ValidationSummary dump).
// The helpers below expose only the user-facing result - never backend
// implementation details such as service names, NVIDIA, DB, or stack traces.

const VALIDATION_MESSAGE = (value: AnyRecord | undefined | null): string =>
  String(value?.message ?? '') || 'Validation issue';

/** True when a paper is composite (has parts.part_a / parts.part_b). */
export function getValidationRecord(paperJson: AnyRecord | undefined | null): AnyRecord {
  return paperJson?.validation ?? {};
}

/** Blocking (error) issues from the persisted validation record. */
export function getBlockingValidationIssues(
  paperJson: AnyRecord | undefined | null,
): string[] {
  const record = getValidationRecord(paperJson);
  // Composite shape: `errors` is the explicit blocking set.
  if (Array.isArray(record.errors)) {
    const blockers = (record.errors ?? [])
      .filter((e: AnyRecord) => e && e.severity !== 'warning')
      .map(VALIDATION_MESSAGE);
    if (blockers.length > 0) return blockers;
    // Empty errors but explicit failed state still blocks.
    if (record.passed === false) return ['Paper validation has not passed yet.'];
    return [];
  }
  // Legacy flat shape: filter error severity from the combined issues list.
  if (Array.isArray(record.issues)) {
    return (record.issues ?? [])
      .filter((issue: AnyRecord) => issue?.severity === 'error')
      .map(VALIDATION_MESSAGE);
  }
  // No issues persisted: fall back to the recorded pass/fail flag.
  return record.passed === false ? ['Paper validation has not passed yet.'] : [];
}

/** Non-blocking warnings from the persisted validation record (shown separately). */
export function getValidationWarnings(
  paperJson: AnyRecord | undefined | null,
): string[] {
  const record = getValidationRecord(paperJson);
  if (Array.isArray(record.warnings)) {
    return (record.warnings ?? [])
      .filter((w: AnyRecord) => w)
      .map(VALIDATION_MESSAGE);
  }
  if (Array.isArray(record.issues)) {
    return (record.issues ?? [])
      .filter((issue: AnyRecord) => issue?.severity === 'warning')
      .map(VALIDATION_MESSAGE);
  }
  return [];
}

/** True when the persisted validation record carries no blocking errors. */
export function isValidationClean(paperJson: AnyRecord | undefined | null): boolean {
  return getBlockingValidationIssues(paperJson).length === 0;
}
