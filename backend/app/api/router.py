from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_roles
from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.blueprints import router as blueprints_router
from app.api.routes.generation import router as generation_router
from app.api.routes.exam_generation import router as exam_generation_router
from app.api.routes.health import router as health_router
from app.api.routes.model_papers import router as model_papers_router
from app.api.routes.papers import router as papers_router
from app.api.routes.syllabi import router as syllabi_router
from app.api.routes.unit_materials import router as unit_materials_router
from app.api.routes.productivity import router as productivity_router
from app.core.config import settings

api_router = APIRouter()

# Public endpoints — no auth required
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# TEST-ONLY support routes (OTP outbox for browser E2E). Conditionally mounted
# so they cannot even be reached — let alone documented — outside APP_ENV=TEST.
if settings.app_env.upper() == "TEST":
    from app.api.routes.test_support import router as test_support_router

    api_router.include_router(test_support_router, prefix="/auth/test", tags=["test-support"])

# Protected endpoints — require FACULTY or ADMIN role
_staff_dep = [Depends(require_roles("faculty", "admin"))]

# Admin-only endpoints — REQUIRE the ADMIN role; backend RBAC is authoritative.
_admin_dep = [Depends(require_roles("admin"))]
api_router.include_router(admin_router, prefix="/admin", tags=["admin"], dependencies=_admin_dep)

api_router.include_router(syllabi_router,       prefix="/syllabi",        tags=["syllabi"],        dependencies=_staff_dep)
api_router.include_router(unit_materials_router, prefix="/unit-materials", tags=["unit-materials"], dependencies=_staff_dep)
api_router.include_router(model_papers_router,  prefix="/model-papers",  tags=["model-papers"],   dependencies=_staff_dep)
api_router.include_router(blueprints_router,    prefix="/blueprints",    tags=["blueprints"],     dependencies=_staff_dep)
api_router.include_router(papers_router,        prefix="/papers",        tags=["papers"],         dependencies=_staff_dep)
api_router.include_router(generation_router,    prefix="/generation",    tags=["generation"],     dependencies=_staff_dep)
api_router.include_router(exam_generation_router, prefix="/exam-generation", tags=["exam-generation"], dependencies=_staff_dep)
api_router.include_router(productivity_router, prefix="/productivity", tags=["productivity"], dependencies=_staff_dep)
