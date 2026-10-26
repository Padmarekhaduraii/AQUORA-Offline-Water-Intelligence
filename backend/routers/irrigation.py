from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import IrrigationSchedule
from backend.schemas import IrrigationScheduleResponse
from backend.services.irrigation_engine import irrigation_engine

router = APIRouter(prefix="/api/v1/irrigation", tags=["Offline Irrigation Scheduling"])

@router.get("/schedules", response_model=List[IrrigationScheduleResponse])
def get_irrigation_schedules(db: Session = Depends(get_db)):
    """
    Returns offline-generated irrigation schedules correlated with canal arrival windows.
    Runs completely without cloud access.
    """
    return irrigation_engine.generate_schedules_for_zones(db)


@router.post("/recalculate", response_model=List[IrrigationScheduleResponse])
def recalculate_schedules(db: Session = Depends(get_db)):
    """
    Forces immediate re-evaluation of crop irrigation requirements against latest sensor telemetry.
    """
    return irrigation_engine.generate_schedules_for_zones(db)
