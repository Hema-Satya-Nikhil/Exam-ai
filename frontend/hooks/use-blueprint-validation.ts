'use client';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';

export function useBlueprintValidation() {
  return useMutation({
    mutationFn: async (blueprint: unknown) => apiFetch('/api/blueprints/validate', { method: 'POST', body: JSON.stringify(blueprint) })
  });
}
