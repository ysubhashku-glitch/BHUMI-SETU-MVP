from app.routers.auth import router as auth_router
from app.routers.cases import router as cases_router
from app.routers.parcels import router as parcels_router
from app.routers.documents import router as documents_router
from app.routers.evidence import router as evidence_router
from app.routers.claims import router as claims_router
from app.routers.findings import router as findings_router
from app.routers.ai import router as ai_router
from app.routers.landamin import router as landamin_router
from app.routers.reports import router as reports_router
from app.routers.mcp_router import router as mcp_router
from app.routers.health import router as health_router
from app.routers.judicial import router as judicial_router
from app.routers.valuation import router as valuation_router
from app.routers.spatial_overlay import router as spatial_overlay_router

__all__ = [
    "auth_router",
    "cases_router",
    "parcels_router",
    "documents_router",
    "evidence_router",
    "claims_router",
    "findings_router",
    "ai_router",
    "landamin_router",
    "reports_router",
    "mcp_router",
    "health_router",
    "judicial_router",
    "valuation_router",
    "spatial_overlay_router",
]

