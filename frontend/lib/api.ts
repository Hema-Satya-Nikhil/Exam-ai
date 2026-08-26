const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const defaultHeaders: Record<string, string> = isFormData ? {} : { 'Content-Type': 'application/json' };

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...defaultHeaders,
      ...(init?.headers as Record<string, string> ?? {})
    },
    cache: 'no-store'
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function uploadSyllabus(file: File, subjectId: string) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('subject_id', subjectId);
  return apiFetch<any>('/api/syllabi/upload', { method: 'POST', body: formData });
}

export async function uploadUnitMaterial(file: File, unitNumber: number, syllabusId = 'default') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('unit_number', String(unitNumber));
  formData.append('syllabus_id', syllabusId);
  return apiFetch<any>('/api/unit-materials/upload', { method: 'POST', body: formData });
}

export async function uploadModelPaper(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch<any>('/api/model-papers/upload', { method: 'POST', body: formData });
}

export async function validateBlueprint(blueprint: any) {
  return apiFetch<any>('/api/blueprints/validate', { method: 'POST', body: JSON.stringify(blueprint) });
}

export async function createGenerationJob(blueprint: any) {
  return apiFetch<any>('/api/generation/papers/generate', { method: 'POST', body: JSON.stringify({ blueprint }) });
}

export async function getGenerationJob(jobId: string) {
  return apiFetch<any>(`/api/generation/jobs/${jobId}`);
}

export async function getPaperDraft(paperId: string) {
  return apiFetch<any>(`/api/papers/drafts/${paperId}`);
}

export async function updatePaperQuestion(paperId: string, questionNumber: number, updates: any) {
  return apiFetch<any>(`/api/papers/drafts/${paperId}/question`, {
    method: 'PATCH',
    body: JSON.stringify({ question_number: questionNumber, ...updates })
  });
}

export async function lockPaperQuestion(paperId: string, questionNumber: number) {
  return apiFetch<any>(`/api/papers/drafts/${paperId}/lock`, {
    method: 'POST',
    body: JSON.stringify({ question_number: questionNumber })
  });
}

export async function regeneratePaperQuestion(paperId: string, questionNumber: number, instructions?: string) {
  return apiFetch<any>(`/api/papers/drafts/${paperId}/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ question_number: questionNumber, instructions })
  });
}

export async function approvePaper(paperId: string, approvedBy: string, comments?: string) {
  return apiFetch<any>(`/api/papers/drafts/${paperId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy, comments })
  });
}

export async function exportPaper(paperJson: any, format: 'pdf' | 'docx') {
  return apiFetch<any>('/api/papers/export', {
    method: 'POST',
    body: JSON.stringify({ paper_json: paperJson, format })
  });
}
