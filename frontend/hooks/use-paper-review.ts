'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import {
  approvePaper,
  exportPaper,
  getPaperDraft,
  lockPaperQuestion,
  regeneratePaperQuestion,
  updatePaperQuestion
} from '@/lib/api';

export function usePaperDraft(paperId: string) {
  return useQuery({
    queryKey: ['paper-draft', paperId],
    queryFn: () => getPaperDraft(paperId),
    enabled: Boolean(paperId)
  });
}

export function usePaperQuestionUpdate() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number; updates: any }) =>
      updatePaperQuestion(payload.paper_id, payload.question_number, payload.updates)
  });
}

export function usePaperLock() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; question_number: number }) =>
      lockPaperQuestion(payload.paper_id, payload.question_number)
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
    mutationFn: (payload: { paper_json: any; format: 'pdf' | 'docx' }) =>
      exportPaper(payload.paper_json, payload.format)
  });
}
