from supabase import Client, create_client

from app.core.settings import settings

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY,
)


def signup(name: str, email: str, password: str):
    response = supabase.auth.sign_up(
        {
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name
                }
            }
        }
    )
    return response


def login(email: str, password: str):
    response = supabase.auth.sign_in_with_password(
        {
            "email": email,
            "password": password
        }
    )
    return response