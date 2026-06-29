from fastapi import APIRouter

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/")
def get_dashboard():
    return {
        "page": "Dashboard",
        "status": "success",
        "message": "Dashboard endpoint is working."
    }