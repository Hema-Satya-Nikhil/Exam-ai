'use client';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

export function useModelPaperAnalysis() {
  return useMutation({
    mutationFn: async (payload: { file_name: string; extracted_text: string }) =>
      apiFetch('/api/model-papers/analyze', { method: 'POST', body: JSON.stringify(payload) })
  });
}
