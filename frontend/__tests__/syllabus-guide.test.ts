import {
  addUnit,
  moveTopic,
  normalizeParsedUnits,
  parseUploadResult,
  removeUnit,
  validationIssues
} from '../lib/syllabus-guide';

describe('normalizeParsedUnits', () => {
  it('maps parsed units to the editable shape (title + plain topics)', () => {
    const units = normalizeParsedUnits([
      { unit_number: 1, title: 'Intro to DB', topics: [{ topic_name: 'Relational model' }, { topic_name: 'SQL' }] },
      { unit_number: 2, title: 'Transactions', topics: [] }
    ]);
    expect(units).toEqual([
      { unit_number: 1, title: 'Intro to DB', topics: ['Relational model', 'SQL'] },
      { unit_number: 2, title: 'Transactions', topics: [] }
    ]);
  });

  it('drops malformed entries', () => {
    const units = normalizeParsedUnits([
      null as any,
      { unit_number: 1, title: 'Unit', topics: [{ topic_name: 'A' }] }
    ]);
    expect(units).toHaveLength(1);
    expect(units[0].unit_number).toBe(1);
  });
});

describe('parseUploadResult', () => {
  it('returns parsed status with units when a structure was extracted', () => {
    const out = parseUploadResult({
      parsed: { units: [{ unit_number: 1, title: 'DB', topics: [{ topic_name: 'X' }] }] },
      warnings: [],
      ocr_used: true
    });
    expect(out.status).toBe('parsed');
    expect(out.units).toHaveLength(1);
    expect(out.ocr_used).toBe(true);
  });

        it('returns failed status when no units could be extracted (uncertain, nothing invented)', () => {
    const out = parseUploadResult({
      parsed: { units: [] },
      warnings: ["We couldn't confidently read the syllabus structure."],
      ocr_used: false
    });
    expect(out.status).toBe('failed');
    expect(out.units).toEqual([]);
    expect(out.confidence).toBe('unknown');
  });
});

describe('validationIssues', () => {
  it('rejects duplicate unit numbers', () => {
    const issues = validationIssues([
      { unit_number: 1, title: 'A', topics: ['x'] },
      { unit_number: 1, title: 'B', topics: ['y'] }
    ]);
    expect(issues.some((i) => i.includes('Duplicate'))).toBe(true);
  });

  it('flags units with no topics and empty topics', () => {
    const issues = validationIssues([
      { unit_number: 1, title: 'A', topics: [] },
      { unit_number: 2, title: 'B', topics: ['', 'ok'] }
    ]);
    expect(issues.some((i) => i.includes('no topics'))).toBe(true);
    expect(issues.some((i) => i.includes('empty topic'))).toBe(true);
  });

  it('returns no issues for a valid, corrected structure', () => {
    const issues = validationIssues([
      { unit_number: 1, title: 'A', topics: ['one'] },
      { unit_number: 2, title: 'B', topics: ['two'] }
    ]);
    expect(issues).toEqual([]);
  });
});

describe('editor mutations', () => {
  it('adds a unit with the next unit number', () => {
    const next = addUnit([{ unit_number: 1, title: 'A', topics: ['x'] }]);
    expect(next).toHaveLength(2);
    expect(next[1].unit_number).toBe(2);
  });

  it('removes a unit by index', () => {
    const trimmed = removeUnit(
      [
        { unit_number: 1, title: 'A', topics: [] },
        { unit_number: 2, title: 'B', topics: [] }
      ],
      0
    );
    expect(trimmed).toHaveLength(1);
    expect(trimmed[0].unit_number).toBe(2);
  });

  it('reorders topics within a unit', () => {
    const base = [{ unit_number: 1, title: 'A', topics: ['one', 'two', 'three'] }];
    const moved = moveTopic(base, 0, 0, 1);
    expect(moved[0].topics).toEqual(['two', 'one', 'three']);
  });
});
