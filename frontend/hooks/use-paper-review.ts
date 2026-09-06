'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  approvePaper,
  downloadPaper,
  getPaperDraft,
  lockPaperQuestion,
  regeneratePaperQuestion,
  unlockPaperQuestion,
  updatePaperQuestion
} from '@/lib/api';
import type { CompositeQuestionIdentity } from '@/lib/composite-review';

export function usePaperDraft(paperId: string) {
  return useQuery({
    queryKey: ['paper-draft', paperId],
    queryFn: () => getPaperDraft(paperId),
    enabled: Boolean(paperId) && paperId !== 'draft-placeholder'
  });
}

export function usePaperQuestionUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { paper_id: string; question: CompositeQuestionIdentity; updates: Record<string, unknown> }) =>
      updatePaperQuestion(payload.paper_id, payload.question, payload.updates),
    // Reflect the authoritative server draft immediately (the cached query
    // result would otherwise keep overriding the mutation's returned draft).
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-draft'] })
  });
}

export function usePaperLock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { paper_id: string; question: CompositeQuestionIdentity }) =>
      lockPaperQuestion(payload.paper_id, payload.question),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-draft'] })
  });
}

export function usePaperUnlock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { paper_id: string; question: CompositeQuestionIdentity }) =>
      unlockPaperQuestion(payload.paper_id, payload.question),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-draft'] })
  });
}

export function usePaperRegeneration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { paper_id: string; question: CompositeQuestionIdentity; instructions?: string }) =>
      regeneratePaperQuestion(payload.paper_id, payload.question, payload.instructions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-draft'] })
  });
}

export function usePaperApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { paper_id: string; approved_by: string; comments?: string }) =>
      approvePaper(payload.paper_id, payload.approved_by, payload.comments),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['paper-draft'] })
  });
}

export function usePaperExport() {
  return useMutation({
    mutationFn: (payload: { paper_id: string; format: 'pdf' | 'docx' }) =>
      downloadPaper(payload.paper_id, payload.format)
  });
}
