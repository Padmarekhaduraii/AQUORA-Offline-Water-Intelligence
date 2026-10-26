from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import SystemAlert
from backend.schemas import AlertResponse
from backend.services.alert_service import alert_service

router = APIRouter(prefix="/api/v1/alerts", tags=["System Alerts & Warnings"])

@router.get("", response_model=List[AlertResponse])
def get_active_alerts(db: Session = Depends(get_db)):
    """
    Returns active system alerts: Sensor Disconnections, Stale Data, Critical Battery, Surge Warnings.
    """
    return alert_service.scan_and_update_alerts(db)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Acknowledge an alert to silence recurring audio/visual dashboard warnings.
    """
    alert = db.query(SystemAlert).filter(SystemAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    alert.is_acknowledged = True
    db.commit()
    db.refresh(alert)
    return alert
