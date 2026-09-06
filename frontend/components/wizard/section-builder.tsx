'use client';

import { CopyPlus, Plus, Trash2 } from 'lucide-react';

import { BLOOM_OPTIONS, DIFFICULTY_OPTIONS, QUESTION_TYPES, sectionTotal, sectionTotals } from '@/lib/wizard-logic';
import type { SectionConfig } from '@/lib/wizard-logic';

interface SectionBuilderProps {
  sections: SectionConfig[];
  selectedUnits: number[];
  targetMarks: number;
  onChange: (sections: SectionConfig[]) => void;
  showBloom?: boolean;
}

export function SectionBuilder({ sections, selectedUnits, targetMarks, onChange, showBloom = true }: SectionBuilderProps) {
  const totals = sectionTotals(sections);
  const difference = targetMarks - totals.total;
  const balanced = difference === 0;

  function updateSection(id: string, patch: Partial<SectionConfig>) {
    onChange(sections.map((section) => (section.id === id ? { ...section, ...patch } : section)));
  }

  function removeSection(id: string) {
    if (sections.length <= 1) return;
    onChange(sections.filter((section) => section.id !== id));
  }

  function addSection() {
    const index = sections.length + 1;
    onChange([
      ...sections,
      {
        id: `section-${Date.now()}-${index}`,
        name: `Section ${String.fromCharCode(64 + index)}`,
        marksPerQuestion: sections.length <= 1 ? 5 : 10,
        questionCount: 3,
        difficulty: 'medium',
        questionType: 'analytical',
        internalChoice: false,
        units: [],
        bloomLevels: ['L3', 'L4']
      }
    ]);
  }

  function copySection(id: string) {
    const source = sections.find((section) => section.id === id);
    if (!source) return;
    onChange([
      ...sections,
      {
        ...source,
        id: `section-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: `${source.name} (copy)`
      }
    ]);
  }

  return (
    <div className="space-y-5" data-testid="section-builder">
      <div className="grid gap-3 sm:grid-cols-3">
        <TotalMetric label="Paper total" value={`${totals.total} marks`} tone={balanced ? 'ok' : 'warn'} />
        <TotalMetric label="Target total" value={`${targetMarks} marks`} tone="plain" />
        <TotalMetric label="Questions" value={`${totals.questionCount}`} tone="plain" />
      </div>

      {!balanced ? (
        <div
          className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          data-testid="mark-difference"
        >
          {difference > 0
            ? `${difference} mark${difference === 1 ? '' : 's'} remaining to reach ${targetMarks}. Adjust question counts and marks below.`
            : `The paper is ${Math.abs(difference)} mark${Math.abs(difference) === 1 ? '' : 's'} over the ${targetMarks} target. Reduce counts or marks.`}
        </div>
      ) : (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" data-testid="mark-balanced">
          Paper structure adds up to {totals.total} marks — matches the target of {targetMarks}.
        </div>
      )}

      {sections.map((section, index) => (
        <section
          key={section.id}
          className="rounded-3xl border border-white/70 bg-white/75 p-5 shadow-sm"
          data-testid={`section-card-${index}`}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="min-w-40 flex-1 space-y-1.5">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500">Section name</span>
              <input
                value={section.name}
                onChange={(event) => updateSection(section.id, { name: event.target.value })}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none focus:border-slate-400"
              />
            </label>
            <div className="flex items-center gap-2">
              <button type="button" onClick={() => copySection(section.id)} title="Duplicate section" className="rounded-full border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-100">
                <CopyPlus className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => removeSection(section.id)}
                disabled={sections.length <= 1}
                title="Remove section"
                className="rounded-full border border-slate-200 bg-white p-2 text-slate-600 hover:bg-red-50 disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <NumberField label="Questions" value={section.questionCount} min={0} max={50} onChange={(value) => updateSection(section.id, { questionCount: value })} />
            <NumberField label="Marks per question" value={section.marksPerQuestion} min={1} max={50} onChange={(value) => updateSection(section.id, { marksPerQuestion: value })} />
            <div className="space-y-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Difficulty</span>
              <select
                value={section.difficulty}
                onChange={(event) => updateSection(section.id, { difficulty: event.target.value as SectionConfig['difficulty'] })}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
              >
                {DIFFICULTY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Type</span>
              <select
                value={section.questionType}
                onChange={(event) => updateSection(section.id, { questionType: event.target.value })}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
              >
                {QUESTION_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {labelOfQuestionType(type)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Section total</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950">
              {section.questionCount} × {section.marksPerQuestion} = {format(sectionTotal(section))} marks
            </p>
          </div>

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Units covered</span>
              <div className="mt-2 flex flex-wrap gap-2">
                {selectedUnits.length === 0 ? (
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-500">No units selected yet</span>
                ) : (
                  selectedUnits.map((unit) => {
                    const isOn = section.units.length === 0 || section.units.includes(unit);
                    return (
                      <button
                        key={unit}
                        type="button"
                        onClick={() =>
                          updateSection(section.id, {
                            units: isOn ? section.units.filter((u) => u !== unit) : section.units.length === 0 ? [unit] : [...section.units, unit]
                          })
                        }
                        className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                          isOn ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                        }`}
                      >
                        Unit {unit}
                      </button>
                    );
                  })
                )}
              </div>
              {section.units.length > 0 ? (
                <button type="button" onClick={() => updateSection(section.id, { units: [] })} className="mt-2 text-xs font-medium text-slate-500 hover:text-slate-800">
                  Clear — cover all units
                </button>
              ) : (
                <p className="mt-2 text-xs text-slate-500">All selected units are covered by this section.</p>
              )}
            </div>

            <div>
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Internal choice</span>
              <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={section.internalChoice}
                  onChange={(event) => updateSection(section.id, { internalChoice: event.target.checked })}
                  className="h-4 w-4 rounded border-slate-300"
                />
                Answer any one from each pair (an &quot;or&quot; question)
              </label>
            </div>
          </div>
{showBloom ? (
            <div className="mt-4">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">Allowed evaluation levels</span>
              <div className="mt-2 flex flex-wrap gap-2" data-testid={`bloom-${index}`}>
                {BLOOM_OPTIONS.map((option) => {
                  const selected = section.bloomLevels.includes(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => {
                        const next = selected
                          ? section.bloomLevels.filter((level) => level !== option.value)
                          : [...section.bloomLevels, option.value];
                        updateSection(section.id, { bloomLevels: next });
                      }}
                      className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                        selected ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                      }`}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </section>
      ))}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={addSection}
          className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
          data-testid="add-section"
        >
          <Plus className="h-4 w-4" /> Add Section
        </button>
      </div>
    </div>
  );
}

function TotalMetric({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'warn' | 'plain' }) {
  const toneClass =
    tone === 'ok'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
      : tone === 'warn'
        ? 'border-amber-200 bg-amber-50 text-amber-800'
        : 'border-slate-200 bg-white/70 text-slate-800';
  return (
    <div className={`rounded-3xl border px-4 py-3 ${toneClass}`}>
      <p className="text-xs uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function NumberField({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="space-y-1.5">
      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={Number.isFinite(value) ? value : ''}
        onChange={(event) => {
          const parsed = parseInt(event.target.value, 10);
          onChange(Number.isFinite(parsed) ? Math.max(min, Math.min(max, parsed)) : 0);
        }}
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400"
      />
    </label>
  );
}

function format(value: number): string {
  return value.toLocaleString('en-IN');
}

function labelOfQuestionType(type: string): string {
  return type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}