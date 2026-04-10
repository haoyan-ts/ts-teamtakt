from fastapi import APIRouter

from .absences import router as absences_router
from .auth import router as auth_router
from .categories import router as categories_router
from .daily_records import router as daily_records_router
from .daily_records import unlock_router
from .export import router as export_router
from .growth import router as growth_router
from .health import router as health_router
from .holidays import router as holidays_router
from .metrics import router as metrics_router
from .notifications import router as notifications_router
from .projects import router as projects_router
from .quarterly_reports import router as quarterly_reports_router
from .sharing_grants import router as sharing_grants_router
from .social import router as social_router
from .team_settings import router as team_settings_router
from .teams import router as teams_router
from .users import router as users_router
from .weekly_emails import router as weekly_emails_router
from .weekly_reports import router as weekly_reports_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(teams_router)
router.include_router(users_router)
router.include_router(categories_router)
router.include_router(projects_router)
router.include_router(daily_records_router)
router.include_router(unlock_router)
router.include_router(absences_router)
router.include_router(team_settings_router)
router.include_router(metrics_router)
router.include_router(growth_router)
router.include_router(weekly_reports_router)
router.include_router(weekly_emails_router)
router.include_router(notifications_router)
router.include_router(holidays_router)
router.include_router(sharing_grants_router)
router.include_router(export_router)
router.include_router(social_router)
router.include_router(quarterly_reports_router)
