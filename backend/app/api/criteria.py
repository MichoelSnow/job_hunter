import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.criteria import UserCriteria
from app.schemas.criteria import UserCriteriaCreate, UserCriteriaResponse, UserCriteriaUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/criteria", tags=["criteria"])


@router.get("", response_model=list[UserCriteriaResponse])
def list_criteria(db: Session = Depends(get_db)) -> list[UserCriteria]:
    return db.query(UserCriteria).order_by(UserCriteria.is_hard_requirement.desc()).all()


@router.post("", response_model=UserCriteriaResponse, status_code=201)
def create_criterion(payload: UserCriteriaCreate, db: Session = Depends(get_db)) -> UserCriteria:
    criterion = UserCriteria(**payload.model_dump())
    db.add(criterion)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.put("/{criterion_id}", response_model=UserCriteriaResponse)
def update_criterion(
    criterion_id: int, payload: UserCriteriaUpdate, db: Session = Depends(get_db)
) -> UserCriteria:
    criterion = db.get(UserCriteria, criterion_id)
    if not criterion:
        raise HTTPException(status_code=404, detail="Criterion not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(criterion, field, value)
    db.commit()
    db.refresh(criterion)
    return criterion


@router.delete("/{criterion_id}", status_code=204)
def delete_criterion(criterion_id: int, db: Session = Depends(get_db)) -> None:
    criterion = db.get(UserCriteria, criterion_id)
    if not criterion:
        raise HTTPException(status_code=404, detail="Criterion not found")
    db.delete(criterion)
    db.commit()
