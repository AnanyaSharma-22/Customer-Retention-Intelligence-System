from fastapi import APIRouter, HTTPException

from app.schemas.auth import LoginRequest, SignUpRequest
from app.services.auth_service import login, signup
from fastapi import Depends
from app.dependencies import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/signup")
def register(request: SignUpRequest):
    try:
        response = signup(
            request.name,
            request.email,
            request.password,
        )

        return {
            "message": "User registered successfully",
            "user": response.user,
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post("/login")
def signin(request: LoginRequest):
    try:
        response = login(
            request.email,
            request.password,
        )

        return {
            "message": "Login successful",
            "session": response.session,
            "user": response.user,
        }

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        )
@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.user_metadata.get("name"),
    }