'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  approvePaper,
  downloadPaper,
  getPaperDraft,
  lockPaperQuestion,
  regeneratePaperQuestion,
  unlockPaperQuestion,
  updatePaperQuestion
} from '@/lib/api';

export function usePaperDraft(paperId: string) {
  return useQuery({
    queryKey: ['paper-draft', paperId],
    queryFn: () => getPaperDraft(paperId),
    enabled: Boolean(paperId) && paperId !== 'draft-placeholder'
  });
}

export function usePaperQuestionUpdate() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number; updates: Record<string, unknown> }) =>
      updatePaperQuestion(payload.paper_id, payload.question_number, payload.updates)
  });
}

export function usePaperLock() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number }) =>
      lockPaperQuestion(payload.paper_id, payload.question_number)
  });
}

export function usePaperUnlock() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number }) =>
      unlockPaperQuestion(payload.paper_id, payload.question_number)
  });
}

export function usePaperRegeneration() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number; instructions?: string }) =>
      regeneratePaperQuestion(payload.paper_id, payload.question_number, payload.instructions)
  });
}

export function usePaperApproval() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; approved_by: string; comments?: string }) =>
      approvePaper(payload.paper_id, payload.approved_by, payload.comments)
  });
}

export function usePaperExport() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; format: 'pdf' | 'docx' }) =>
      downloadPaper(payload.paper_id, payload.format)
  });
}
