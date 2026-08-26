'use client';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

export function useSyllabusUpload() {
  return useMutation({
    mutationFn: async (payload: { subject_id: string; file_name: string; extracted_text: string }) =>
      apiFetch('/api/syllabi/parse', { method: 'POST', body: JSON.stringify(payload) })
  });
}
