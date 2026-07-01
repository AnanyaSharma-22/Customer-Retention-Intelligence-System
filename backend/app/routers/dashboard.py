from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.dataset import Dataset
from app.dependencies import get_current_user, get_db
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import get_dashboard_summary

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/")
def get_dashboard(
    current_user=Depends(get_current_user),
):
    return {
        "page": "Dashboard",
        "status": "success",
        "message": "Dashboard endpoint is working.",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.user_metadata.get("name"),
        },
    }


@router.get(
    "/summary/{dataset_id}",
    response_model=DashboardSummary,
)
def dashboard_summary(
    dataset_id: str,
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

    return get_dashboard_summary(
        db=db,
        dataset_id=dataset_id,
    )