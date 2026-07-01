from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dataset import Dataset
from app.dependencies import get_current_user, get_db
from app.schemas.customer import (
    CustomerDetails,
    CustomerListItem,
)
from app.services.customer_service import (
    get_customer_details,
    get_customers,
)

router = APIRouter(
    prefix="/customers",
    tags=["Customers"],
)


@router.get(
    "",
    response_model=list[CustomerListItem],
)
def customers(
    dataset_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    customer_id: Optional[str] = None,
    risk: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.user_id == current_user.id,
        )
        .first()
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    return get_customers(
        db=db,
        dataset_id=dataset_id,
        customer_id=customer_id,
        risk=risk,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{dataset_id}/{customer_id}",
    response_model=CustomerDetails,
)
def customer_details(
    dataset_id: str,
    customer_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):

    dataset = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.user_id == current_user.id,
        )
        .first()
    )

    if not dataset:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found.",
        )

    customer = get_customer_details(
        db=db,
        dataset_id=dataset_id,
        customer_id=customer_id,
    )

    if not customer:
        raise HTTPException(
            status_code=404,
            detail="Customer not found.",
        )

    return customer