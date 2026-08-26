# Generation Flow

1. Faculty defines or imports a blueprint.
2. Backend validates structure, scope, and marks.
3. Backend selects the relevant source material for each question.
4. NVIDIA generates structured JSON for each question or section.
5. Deterministic validators check the result.
6. Failed items are regenerated with the failure reason.
7. Approved papers are exported from the same validated JSON.
