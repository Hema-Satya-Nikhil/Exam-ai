'use client';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

export function usePaperGeneration() {
  return useMutation({
    mutationFn: async (payload: unknown) => apiFetch('/api/generation/papers/generate', { method: 'POST', body: JSON.stringify(payload) })
  });
}
