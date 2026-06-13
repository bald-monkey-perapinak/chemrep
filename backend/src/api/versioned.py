from fastapi import APIRouter


def versioned_router(router: APIRouter, prefix: str = "/api/v1") -> APIRouter:
    """Wrap router with /api/v1 prefix."""
    versioned = APIRouter(prefix=prefix)
    versioned.include_router(router)
    return versioned
