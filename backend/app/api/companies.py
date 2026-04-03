import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.models.job import Job
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    priority_only: bool = False,
    db: Session = Depends(get_db),
) -> list[CompanyResponse]:
    query = db.query(Company)
    if priority_only:
        query = query.filter(Company.is_priority == True)  # noqa: E712
    companies = query.order_by(Company.name).all()

    scraped_sources = ("greenhouse", "lever", "workday", "ashby", "html_scraper")
    counts = (
        db.query(Job.company_id, func.count(Job.id))
        .filter(Job.company_id.isnot(None), Job.source.in_(scraped_sources))
        .group_by(Job.company_id)
        .all()
    )
    count_by_company_id = {company_id: total for company_id, total in counts}

    return [
        CompanyResponse.model_validate(
            company,
            from_attributes=True,
        ).model_copy(
            update={
                "scraped_job_count": int(count_by_company_id.get(company.id, 0)),
                "scrape_error": company.scrape_last_status == "error",
            }
        )
        for company in companies
    ]


@router.post("", response_model=CompanyResponse, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)) -> Company:
    existing = db.query(Company).filter(Company.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Company already exists")
    company = Company(**payload.model_dump(exclude_none=True))
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db)
) -> Company:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db)) -> Response:
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    db.query(Job).filter(Job.company_id == company_id).update({"company_id": None})

    db.delete(company)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
