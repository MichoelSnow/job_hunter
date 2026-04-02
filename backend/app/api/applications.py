import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.application import Application, ApplicationStatusHistory
from app.models.job import Job
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    StatusHistoryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationResponse])
def list_applications(db: Session = Depends(get_db)) -> list[Application]:
    return db.query(Application).order_by(Application.updated_at.desc()).all()


@router.post("", response_model=ApplicationResponse, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> Application:
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = db.query(Application).filter(Application.job_id == payload.job_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Application for this job already exists")

    application = Application(**payload.model_dump(exclude_none=True))
    db.add(application)
    db.commit()
    db.refresh(application)
    logger.info("Created application for job_id=%s", payload.job_id)
    return application


@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int, db: Session = Depends(get_db)) -> Application:
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.put("/{app_id}", response_model=ApplicationResponse)
def update_application(
    app_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)
) -> Application:
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    old_status = application.status
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(application, field, value)

    if "status" in update_data and update_data["status"] != old_status:
        history = ApplicationStatusHistory(
            application_id=app_id,
            old_status=old_status,
            new_status=update_data["status"],
        )
        db.add(history)

    db.commit()
    db.refresh(application)
    return application


@router.delete("/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)) -> None:
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(application)
    db.commit()


@router.get("/{app_id}/history", response_model=list[StatusHistoryResponse])
def get_status_history(
    app_id: int, db: Session = Depends(get_db)
) -> list[ApplicationStatusHistory]:
    application = db.get(Application, app_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application.status_history
