# Database

The schema is designed for versioning, auditability, and deterministic validation. Major entities include users, roles, subjects, syllabi, syllabus versions, unit materials, paper templates, paper template versions, paper sections, question blueprints, generation jobs, generated questions, generated papers, paper versions, validation results, approvals, audit logs, system settings, and LLM configs.

Every major workflow step writes a new version or audit event instead of overwriting prior evidence.
