from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas import SyncStatusResponse
from backend.services.sync_service import sync_service

router = APIRouter(prefix="/api/v1/sync", tags=["Offline-First Cloud Synchronization"])

@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(db: Session = Depends(get_db)):
    """
    Returns the number of pending local records queued for cloud sync and last attempt timestamp.
    """
    return sync_service.get_sync_status(db)


@router.post("/trigger")
async def trigger_cloud_synchronization(db: Session = Depends(get_db)):
    """
    Manually triggers synchronization of queued sensor readings with the central upstream cloud.
    Guarantees no data loss if cloud remains unreachable.
    """
    count, message = await sync_service.synchronize_pending(db)
    return {
        "synced_count": count,
        "message": message,
        "is_connected": count > 0
    }
