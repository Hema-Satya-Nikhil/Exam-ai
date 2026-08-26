"""Shared test configuration for the backend test suite.

Applies compatibility patches that all test modules need before they import
the app models:

1.  ``SQLiteTypeCompiler.visit_JSONB`` — SQLite cannot natively render the
    PostgreSQL ``JSONB`` type, which breaks ``Base.metadata.create_all()``.
    We teach the SQLite compiler to fall back to plain ``JSON`` so that the
    in-memory SQLite test database can host every table.

2.  ``bcrypt.__about__`` — ``passlib`` (used by ``app.core.security``) reads
    ``bcrypt.__about__.__version__``; ``bcrypt`` 4.x removed the module, so we
    inject a dummy to silence the noisy warning.
"""

from __future__ import annotations

import os

# Mark the process as the test environment BEFORE app modules are imported so
# startup hooks (e.g. generation-job resume) skip production side effects.
os.environ.setdefault("APP_ENV", "TEST")

import bcrypt as _bcrypt  # noqa: E402
from sqlalchemy import JSON
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

# --- 1. SQLite compiler: teach it to render JSONB as JSON --------------------

if not hasattr(SQLiteTypeCompiler, "visit_JSONB"):

    def _visit_JSONB(self, type_, **kw):  # noqa: ARG001
        return self.process(JSON(), **kw)

    SQLiteTypeCompiler.visit_JSONB = _visit_JSONB

# --- 2. bcrypt / passlib compatibility shim ---------------------------------

if not hasattr(_bcrypt, "__about__"):
    _bcrypt.__about__ = type("_about", (object,), {"__version__": "4.0.0"})()
