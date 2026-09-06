import { extractFilenameFromContentDisposition } from '@/lib/api';

describe('extractFilenameFromContentDisposition (export filename regression)', () => {
  it('parses a plain attachment filename', () => {
    expect(
      extractFilenameFromContentDisposition(
        'attachment; filename="DataMining_Exam_ai.docx"'
      )
    ).toBe('DataMining_Exam_ai.docx');
  });

  it('parses an unquoted filename', () => {
    expect(
      extractFilenameFromContentDisposition('attachment; filename=OperatingSystem_Exam_ai.pdf')
    ).toBe('OperatingSystem_Exam_ai.pdf');
  });

  it('parses the RFC 5987 extended notation', () => {
    expect(
      extractFilenameFromContentDisposition(
        'attachment; filename*=UTF-8\'\'Data%20Warehousing_Exam_ai.pdf'
      )
    ).toBe('Data Warehousing_Exam_ai.pdf');
  });

  it('returns null when no filename is present', () => {
    expect(extractFilenameFromContentDisposition('inline')).toBeNull();
    expect(extractFilenameFromContentDisposition(null)).toBeNull();
  });

  it('extracts a subject filename (no UUID) from the real server header shape', () => {
    const serverHeader = 'attachment; filename="OperatingSystem_Exam_ai.pdf"';
    const name = extractFilenameFromContentDisposition(serverHeader);
    expect(name).toBe('OperatingSystem_Exam_ai.pdf');
    expect(name).not.toContain('question-paper');
  });
});
