import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './auth';

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function redirectToLogin(): void {
  if (typeof window === 'undefined') return;
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const response = await fetch(`${apiBaseUrl}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: 'no-store'
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { access_token: string; refresh_token: string };
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

function buildHeaders(init?: RequestInit): Record<string, string> {
  const isFormData = init?.body instanceof FormData;
  const token = getAccessToken();
  return {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((init?.headers as Record<string, string>) ?? {})
  };
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: buildHeaders(init),
    cache: 'no-store'
  });

  if (response.status === 401 && getRefreshToken()) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetch<T>(path, init);
    }
    clearTokens();
    redirectToLogin();
    throw new ApiError('Session expired. Please sign in again.', 401);
  }

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const text = await response.text();
      if (text) message = text;
    } catch {
      // ignore parse errors on the error body
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}


// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  user_id: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
}

export async function loginRequest(email: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password })
  });
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>('/api/auth/me');
}

export interface RegisterResponse {
  user_id: string;
  email: string;
  status: string;
}

export interface RegisterOptions {
  email: string;
  full_name: string;
  password: string;
}

export async function registerFaculty({ email, full_name, password }: RegisterOptions): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, full_name, password, role: 'faculty' })
  });
}

export async function logoutRequest(refreshToken: string): Promise<void> {
  await apiFetch<void>('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken })
  });
}

// ---------------------------------------------------------------------------
// Syllabus / unit materials / model paper
// ---------------------------------------------------------------------------

export interface UploadSyllabusResult {
  subject_id: string;
  source_file_name: string;
  warnings: string[];
  parsed: {
    source_file_name: string;
    confidence: string;
    notes: string[];
    units: Array<{
      unit_number: number;
      title?: string | null;
      confidence: string;
      topics: Array<{ topic_name: string }>;
    }>;
  };
  page_references: string[];
}

export async function uploadSyllabus(file: File, subjectId: string): Promise<UploadSyllabusResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('subject_id', subjectId);
  return apiFetch<UploadSyllabusResult>('/api/syllabi/upload', { method: 'POST', body: formData });
}

export interface UploadUnitMaterialResult {
  syllabus_id: string;
  unit_number: number;
  file_name: string;
  extracted_text: string;
  warnings: string[];
  page_references: string[];
}

export async function uploadUnitMaterial(file: File, unitNumber: number, syllabusId = 'default'): Promise<UploadUnitMaterialResult> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('unit_number', String(unitNumber));
  formData.append('syllabus_id', syllabusId);
  return apiFetch<UploadUnitMaterialResult>('/api/unit-materials/upload', { method: 'POST', body: formData });
}

export interface ModelPaperAnalysis {
  exam_title?: string | null;
  subject?: string | null;
  total_marks?: number | null;
  duration_minutes?: number | null;
  sections: Array<{
    name: string;
    question_count?: number | null;
    marks_per_question?: number | null;
    numbering_style?: string | null;
    confidence: string;
  }>;
  findings: Array<{ field: string; value: string; confidence: string }>;
  confidence: string;
  bloom_hints: string[];
}

export interface UploadModelPaperResult {
  source_file_name: string;
  warnings: string[];
  page_references: string[];
  analysis: ModelPaperAnalysis;
}

export async function uploadModelPaper(file: File): Promise<UploadModelPaperResult> {
  const formData = new FormData();
  formData.append('file', file);
  return apiFetch<UploadModelPaperResult>('/api/model-papers/upload', { method: 'POST', body: formData });
}

// ---------------------------------------------------------------------------
// Blueprint + generation
// ---------------------------------------------------------------------------

export async function validateBlueprint(blueprint: unknown): Promise<{
  feasibility_issues: string[];
  validation: { passed: boolean; issues: Array<{ code: string; message: string }> };
}> {
  return apiFetch('/api/blueprints/validate', { method: 'POST', body: JSON.stringify(blueprint) });
}

export interface GenerationJobSnapshot {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  current_step: string | null;
  progress_percent: number;
  retry_count: number;
  error_message: string | null;
  paper_id: string | null;
  created_by: string | null;
  total_questions: number | null;
  completed_questions: number;
  current_question: number | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string | null;
}

/** Queue an async generation job; resolves as soon as the job is accepted. */
export async function queueGenerationJob(blueprint: unknown): Promise<GenerationJobSnapshot> {
  return apiFetch<GenerationJobSnapshot>('/api/generation/jobs', {
    method: 'POST',
    body: JSON.stringify({ blueprint })
  });
}

export async function getGenerationJob(jobId: string): Promise<GenerationJobSnapshot> {
  return apiFetch<GenerationJobSnapshot>(`/api/generation/jobs/${jobId}`);
}

export async function resumeGenerationJob(jobId: string): Promise<GenerationJobSnapshot> {
  return apiFetch<GenerationJobSnapshot>(`/api/generation/jobs/${jobId}/resume`, { method: 'POST' });
}
export async function getPaperDraft(paperId: string): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}`);
}

export async function updatePaperQuestion(paperId: string, questionNumber: number, updates: unknown): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/question`, {
    method: 'PATCH',
    body: JSON.stringify({ question_number: questionNumber, ...(updates as object) })
  });
}

export async function lockPaperQuestion(paperId: string, questionNumber: number): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/lock`, {
    method: 'POST',
    body: JSON.stringify({ question_number: questionNumber })
  });
}

export async function unlockPaperQuestion(paperId: string, questionNumber: number): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/unlock`, {
    method: 'POST',
    body: JSON.stringify({ question_number: questionNumber })
  });
}

export async function regeneratePaperQuestion(paperId: string, questionNumber: number, instructions?: string): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ question_number: questionNumber, instructions })
  });
}

export async function approvePaper(paperId: string, approvedBy: string, comments?: string): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy, comments })
  });
}

// ---------------------------------------------------------------------------
// Export — downloads real bytes and triggers a browser download
// ---------------------------------------------------------------------------

const EXPORT_MIME: Record<'pdf' | 'docx', string> = {
  pdf: 'application/pdf',
  docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
};

export async function downloadPaper(paperId: string, format: 'pdf' | 'docx'): Promise<void> {
  const url = `${apiBaseUrl}/api/papers/export/download?paper_id=${encodeURIComponent(paperId)}&format=${format}`;

  const response = await fetch(url, {
    method: 'GET',
    headers: buildHeaders({}),
    cache: 'no-store'
  });

  if (response.status === 401 && getRefreshToken()) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return downloadPaper(paperId, format);
    }
  }

  if (!response.ok) {
    let message = `Export failed with status ${response.status}`;
    try {
      const text = await response.text();
      if (text) message = text;
    } catch {
      // ignore
    }
    throw new ApiError(message, response.status);
  }

  const blob = await response.blob();
  if (blob.size === 0) {
    throw new ApiError('The export file is empty. Please try again.', 500);
  }

  const filename = `question-paper-${paperId}.${format}`;
  const mime = EXPORT_MIME[format];
  const downloadUrl = URL.createObjectURL(new Blob([blob], { type: mime }));
  const anchor = document.createElement('a');
  anchor.href = downloadUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(downloadUrl);
}

// ---------------------------------------------------------------------------
// Syllabus ingestion — image/PDF upload + faculty confirmation
// ---------------------------------------------------------------------------

export interface SyllabusUnitParsed {
  unit_number: number;
  title: string | null;
  topics: Array<{ topic_name: string }>;
}

export interface SyllabusParseResponse {
  subject_id: string;
  source_file_name: string;
  warnings: string[];
  parsed: { units: SyllabusUnitParsed[]; confidence: string };
  ocr_used: boolean;
}

export async function uploadSyllabusFile(
  file: File,
  subjectId: string
): Promise<SyllabusParseResponse> {
  const form = new FormData();
  form.append('subject_id', subjectId);
  form.append('file', file);
  const init: RequestInit = { method: 'POST', body: form };
  return apiFetch<SyllabusParseResponse>('/api/syllabi/upload', init);
}

export interface SyllabusConfirmUnitPayload {
  unit_number: number;
  title?: string | null;
  topics: string[];
}

export async function confirmSyllabus(
  subjectId: string,
  sourceFileName: string,
  units: SyllabusConfirmUnitPayload[]
): Promise<{ syllabus_version_id: string }> {
  return apiFetch<{ syllabus_version_id: string }>('/api/syllabi/confirm', {
    method: 'POST',
    body: JSON.stringify({ subject_id: subjectId, source_file_name: sourceFileName, units })
  });
}

// ---------------------------------------------------------------------------
// Admin — user management + audit logs (admin-only backend routes)
// ---------------------------------------------------------------------------

export interface AdminUserSummary {
  user_id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: string[];
  created_at: string | null;
}

export async function listAdminUsers(): Promise<{ users: AdminUserSummary[] }> {
  return apiFetch<{ users: AdminUserSummary[] }>('/api/admin/users');
}

export async function listPendingFaculty(): Promise<{ users: AdminUserSummary[] }> {
  return apiFetch<{ users: AdminUserSummary[] }>('/api/admin/users/pending');
}

export async function approveFaculty(userId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/admin/users/${userId}/approve`, { method: 'POST' });
}

export async function rejectFaculty(userId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/admin/users/${userId}/reject`, { method: 'POST' });
}

export async function disableUser(userId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/admin/users/${userId}/disable`, { method: 'POST' });
}

export async function listAuditLogs(): Promise<{ audit_logs: unknown[] }> {
  return apiFetch<{ audit_logs: unknown[] }>('/api/admin/audit-logs');
}
