from fastapi import APIRouter
from app.api.routes import auth, companies, search, emails, users

router = APIRouter()

# Authentication routes
router.include_router(auth.router, prefix="/auth", tags=["auth"])

# User routes
router.include_router(users.router, prefix="/users", tags=["users"])

# Company routes
router.include_router(companies.router, prefix="/companies", tags=["companies"])

# Search routes
router.include_router(search.router, prefix="/search", tags=["search"])

# Email routes
router.include_router(emails.router, prefix="/emails", tags=["emails"])