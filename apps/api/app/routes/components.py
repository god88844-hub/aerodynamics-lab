"""Component evidence database routes (editor pickers)."""

from fastapi import APIRouter

from app.services import component_service

router = APIRouter(prefix="/components", tags=["components"])


@router.get("")
def components() -> dict:
    return component_service.list_components()
