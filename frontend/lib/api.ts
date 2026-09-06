import { clearTokens, getAccessToken, getRefreshToken, setTokens } from './auth';
import type { CompositeQuestionIdentity } from './composite-review';

const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
if (process.env.NODE_ENV === 'production' && !configuredApiBaseUrl) {
  throw new Error('NEXT_PUBLIC_API_BASE_URL must be configured for production builds.');
}
const apiBaseUrl = configuredApiBaseUrl ?? 'http://localhost:8000';

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

let refreshPromise: Promise<boolean> | null = null;

async function performTokenRefresh(): Promise<boolean> {
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

function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = performTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
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

// ---------------------------------------------------------------------------
// Recent papers (dashboard) — persisted PostgreSQL state only
// ---------------------------------------------------------------------------

/** Summary shape returned by GET /api/papers/recent. */
export interface RecentPaper {
  id: string;
  title: string;
  subject: string | null;
  exam_type: string | null;
  total_marks: number | null;
  duration_minutes: number | null;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

/** Fetch the authenticated user's recent papers (admin sees all, per RBAC). */
export async function fetchRecentPapers(): Promise<RecentPaper[]> {
  return apiFetch<RecentPaper[]>('/api/papers/recent');
}

export interface ProductivityJob {
  id: string;
  status: string;
  current_step: string | null;
  progress_percent: number;
  retry_count: number;
  error_message: string | null;
  paper_id: string | null;
  total_questions: number | null;
  created_at: string | null;
  finished_at: string | null;
}

export interface PaperTemplate {
  id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  version: number | null;
  template_json: Record<string, unknown>;
}

export async function listProductivityJobs(status?: string): Promise<{ jobs: ProductivityJob[] }> {
  return apiFetch(`/api/productivity/jobs${status ? `?status=${encodeURIComponent(status)}` : ''}`);
}

export async function retryProductivityJob(jobId: string): Promise<{ job_id: string; status: string }> {
  return apiFetch(`/api/productivity/jobs/${jobId}/retry`, { method: 'POST' });
}

export async function listPaperTemplates(): Promise<{ templates: PaperTemplate[] }> {
  return apiFetch('/api/productivity/templates');
}

export async function createPaperTemplate(payload: { name: string; description?: string; template_json: Record<string, unknown> }): Promise<PaperTemplate> {
  return apiFetch('/api/productivity/templates', { method: 'POST', body: JSON.stringify(payload) });
}

export async function deletePaperTemplate(templateId: string): Promise<void> {
  return apiFetch(`/api/productivity/templates/${templateId}`, { method: 'DELETE' });
}

export async function listPaperVersions(paperId: string): Promise<{ versions: Array<{ id: string; version_number: number; paper_json: Record<string, unknown> }> }> {
  return apiFetch(`/api/productivity/papers/${paperId}/versions`);
}

export async function restorePaperVersion(paperId: string, versionId: string): Promise<{ version_id: string }> {
  return apiFetch(`/api/productivity/papers/${paperId}/versions/${versionId}/restore`, { method: 'POST' });
}

export async function clonePaper(paperId: string, title?: string): Promise<{ source_paper_id: string; paper_id: string; title: string; paper_json: Record<string, unknown> }> {
  return apiFetch(`/api/productivity/papers/${paperId}/clone`, { method: 'POST', body: JSON.stringify({ title }) });
}

export async function listPaperDownloads(paperId: string): Promise<{ downloads: Array<{ version_id: string; version_number: number; pdf_available: boolean; docx_available: boolean }> }> {
  return apiFetch(`/api/productivity/papers/${paperId}/downloads`);
}

export async function preparePaperExport(paperId: string, format: 'pdf' | 'docx'): Promise<{ file_path: string; format: string }> {
  return apiFetch('/api/papers/export', { method: 'POST', body: JSON.stringify({ paper_id: paperId, format }) });
}

export function paperDownloadUrl(paperId: string, format: 'pdf' | 'docx'): string {
  return `${apiBaseUrl}/api/papers/export/download?paper_id=${encodeURIComponent(paperId)}&format=${format}`;
}

export interface UsageSummary {
  generation_counts: Record<string, number>;
  audit_activity: Array<{ action: string; entity_type: string; created_at: string | null }>;
}

export async function fetchUsageSummary(): Promise<UsageSummary> {
  return apiFetch('/api/productivity/usage');
}

async function apiFetchWithRetry<T>(
  path: string,
  init: RequestInit | undefined,
  allowRefresh: boolean
): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: buildHeaders(init),
    cache: 'no-store'
  });

  if (response.status === 401 && allowRefresh && getRefreshToken()) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiFetchWithRetry<T>(path, init, false);
    }
    clearTokens();
    redirectToLogin();
    throw new ApiError('Session expired. Please sign in again.', 401);
  }

  if (response.status === 401 && !allowRefresh) {
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

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetchWithRetry<T>(path, init, true);
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
  /** Present when the registration included an admin-access request. */
  admin_request_status?: string | null;
}

export interface RegisterOptions {
  email: string;
  full_name: string;
  password: string;
  /** When true, the new account also gets a PENDING admin-access request. */
  requestAdmin?: boolean;
}

export async function registerFaculty({ email, full_name, password, requestAdmin }: RegisterOptions): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, full_name, password, request_admin: requestAdmin ?? false })
  });
}

export async function logoutRequest(refreshToken: string): Promise<void> {
  await apiFetch<void>('/api/auth/logout', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken })
  });
}

// ---------------------------------------------------------------------------
// Password reset (forgot-password OTP flow) — unauthenticated
// ---------------------------------------------------------------------------

/** Generic, enumeration-safe response from POST /api/auth/forgot-password. */
export interface ForgotPasswordResponse {
  message: string;
}

/** Short-lived, single-use password-reset authorization (NOT a login JWT). */
export interface VerifyResetOtpResponse {
  reset_token: string;
}

export interface ResetPasswordResponse {
  message: string;
}

export async function forgotPasswordRequest(email: string): Promise<ForgotPasswordResponse> {
  return apiFetch<ForgotPasswordResponse>('/api/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email })
  });
}

export async function verifyResetOtp(email: string, otp: string): Promise<VerifyResetOtpResponse> {
  return apiFetch<VerifyResetOtpResponse>('/api/auth/verify-reset-otp', {
    method: 'POST',
    body: JSON.stringify({ email, otp })
  });
}

export async function resetPassword(resetToken: string, newPassword: string): Promise<ResetPasswordResponse> {
  return apiFetch<ResetPasswordResponse>('/api/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ reset_token: resetToken, new_password: newPassword })
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
  /** Real per-part progress when the generation API provides it (composite). */
  part_a?: GenerationPartProgress | null;
  part_b?: GenerationPartProgress | null;
}

/** Per-part progress as exposed by the generation API (optional, additive). */
export interface GenerationPartProgress {
  total_questions: number;
  completed_questions: number;
  status: string;
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

/** Cancel an active generation job using the existing cancellation endpoint. */
export async function cancelGenerationJob(jobId: string): Promise<GenerationJobSnapshot> {
  return apiFetch<GenerationJobSnapshot>(`/api/generation/jobs/${jobId}/cancel`, { method: 'POST' });
}
export async function getPaperDraft(paperId: string): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}`);
}

export async function updatePaperQuestion(
  paperId: string,
  question: CompositeQuestionIdentity,
  updates: unknown,
): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/question`, {
    method: 'PATCH',
    body: JSON.stringify({ ...question, ...(updates as object) })
  });
}

export async function lockPaperQuestion(
  paperId: string,
  question: CompositeQuestionIdentity,
): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/lock`, {
    method: 'POST',
    body: JSON.stringify(question)
  });
}

export async function unlockPaperQuestion(
  paperId: string,
  question: CompositeQuestionIdentity,
): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/unlock`, {
    method: 'POST',
    body: JSON.stringify(question)
  });
}

export async function regeneratePaperQuestion(
  paperId: string,
  question: CompositeQuestionIdentity,
  instructions?: string,
): Promise<any> {
  return apiFetch(`/api/papers/drafts/${paperId}/regenerate`, {
    method: 'POST',
    body: JSON.stringify({ ...question, instructions })
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

/**
 * Parse the filename from a Content-Disposition header.
 *
 * Honors both the plain (`filename=foo.pdf`) and RFC 5987
 * (`filename*=UTF-8''foo.pdf`) forms. Returns null when no filename is
 * present so callers can fall back to a generated name.
 */
export function extractFilenameFromContentDisposition(header: string | null): string | null {
  if (!header) return null;
  // RFC 5987 extended notation: filename*=UTF-8''Foo%20Bar.pdf
  const extended = header.match(/filename\*\s*=\s*[^']*'[^']*'([^;]+)/i);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim().replace(/^"|"$/g, ''));
    } catch {
      // fall through to plain parsing
    }
  }
  const plain = header.match(/filename\s*=\s*"?([^";\r\n]+)"?/i);
  return plain ? plain[1].trim() : null;
}

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

    // Prefer the server-derived subject filename (Content-Disposition). The
  // server filename is the user-facing `<Subject>_Exam_ai.<ext>` name.
  const serverFilename = extractFilenameFromContentDisposition(
    response.headers.get('Content-Disposition')
  );
  const filename = serverFilename || `question-paper-${paperId}.${format}`;
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
  /** Protected Main Admin flag (backend-authoritative). */
  is_primary_admin?: boolean;
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

// ---------------------------------------------------------------------------
// Admin access requests (multi-admin onboarding)
// ---------------------------------------------------------------------------

export interface AdminAccessRequest {
  request_id: string;
  requester_id: string;
  requester_name?: string | null;
  requester_email?: string | null;
  requester_is_active?: boolean | null;
  requested_role: string;
  status: string;
  requested_at: string | null;
  reviewed_at?: string | null;
  reviewer?: string | null;
  review_reason?: string | null;
}

export async function getAdminRequests(): Promise<{ requests: AdminAccessRequest[] }> {
  return apiFetch<{ requests: AdminAccessRequest[] }>('/api/admin/admin-requests');
}

export async function approveAdminRequest(requestId: string): Promise<AdminAccessRequest> {
  return apiFetch<AdminAccessRequest>(`/api/admin/admin-requests/${requestId}/approve`, {
    method: 'POST'
  });
}

export async function rejectAdminRequest(
  requestId: string,
  reason?: string
): Promise<AdminAccessRequest> {
  return apiFetch<AdminAccessRequest>(`/api/admin/admin-requests/${requestId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason: reason ?? null })
  });
}

export async function removeAdminRole(userId: string): Promise<{ message: string; user_id: string }> {
  return apiFetch<{ message: string; user_id: string }>(`/api/admin/users/${userId}/remove-admin`, {
    method: 'POST'
  });
}
