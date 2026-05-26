# -*- coding: utf-8 -*-
"""Routes package – aggregates routers from existing API modules.
We re-export the existing routers to keep backwards compatibility while
providing a clean import path for the new structure.
"""

from backend.agent.api.webhook import router as webhook_router
from backend.agent.api.dashboard import router as dashboard_router
from backend.agent.api.test_chat import router as test_router
from backend.agent.api.auth import router as auth_router
from backend.agent.api.schedule import router as schedule_router
