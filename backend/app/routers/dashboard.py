from fastapi import APIRouter, Depends

from app.dependencies import get_current_user

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/")
def get_dashboard(current_user=Depends(get_current_user)):
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