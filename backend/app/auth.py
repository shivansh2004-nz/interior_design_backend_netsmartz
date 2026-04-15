# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel, EmailStr
# from .mongodb import (
#     get_user_by_email,
#     create_user,
#     verify_otp_in_db,
#     store_otp,
# )
# from .security import hash_password, verify_password, create_jwt
# from .settings import settings
# from .mailer import send_otp_email, generate_otp
# from authlib.integrations.starlette_client import OAuth
# from starlette.requests import Request
# from fastapi.responses import RedirectResponse
# import time

# router = APIRouter(prefix="/auth", tags=["auth"])


# class AuthIn(BaseModel):
#     email: EmailStr
#     password: str


# class VerifyOTPIn(BaseModel):
#     email: EmailStr
#     password: str
#     otp: str


# oauth = OAuth()
# if settings.GOOGLE_CLIENT_ID:
#     oauth.register(
#         name="google",
#         client_id=settings.GOOGLE_CLIENT_ID,
#         client_secret=settings.GOOGLE_CLIENT_SECRET,
#         server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
#         client_kwargs={"scope": "openid email profile"},
#     )


# @router.post("/request-signup")
# async def request_signup(data: AuthIn):
#     if await get_user_by_email(data.email):
#         raise HTTPException(status_code=409, detail="Email already registered")

#     otp = generate_otp()
#     await store_otp(data.email, otp)

#     sent = await send_otp_email(data.email, otp)
#     if not sent:
#         raise HTTPException(status_code=500, detail="Failed to send verification email")

#     return {"message": "Verification code sent to email"}


# @router.post("/signup")
# async def signup(data: VerifyOTPIn):
#     valid = await verify_otp_in_db(data.email, data.otp)
#     if not valid:
#         raise HTTPException(status_code=400, detail="Invalid or expired verification code")

#     user_id = await create_user(
#         {
#             "email": data.email,
#             "password_hash": hash_password(data.password),
#             "created_at": time.time(),
#         }
#     )

#     return {"message": "User registered successfully", "id": str(user_id)}


# @router.post("/signin")
# async def signin(data: AuthIn):
#     u = await get_user_by_email(data.email)
#     if not u or not verify_password(data.password, u.get("password_hash", "")):
#         raise HTTPException(status_code=401, detail="Invalid credentials")

#     token = create_jwt(
#         {"sub": str(u["_id"]), "email": u["email"]},
#         settings.APP_SECRET,
#         settings.JWT_EXPIRE_MIN,
#     )
#     return {"access_token": token}


# @router.get("/me")
# async def get_me(email: str):
#     u = await get_user_by_email(email)
#     if not u:
#         raise HTTPException(status_code=404, detail="User not found")

#     return {
#         "email": u["email"],
#         "credits": u.get("credits", 0),
#         "created_at": u.get("created_at"),
#     }


# @router.get("/login/google")
# async def login_google(request: Request):
#     if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
#         raise HTTPException(status_code=501, detail="Google Login not configured")

#     return await oauth.google.authorize_redirect(
#         request,
#         settings.GOOGLE_REDIRECT_URI,
#     )


# @router.get("/google/callback")
# async def google_callback(request: Request):
#     try:
#         token = await oauth.google.authorize_access_token(request)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Google authorization failed: {str(e)}")

#     user_info = token.get("userinfo")
#     if not user_info:
#         raise HTTPException(status_code=400, detail="Failed to get user info from Google")

#     email = user_info["email"]
#     u = await get_user_by_email(email)

#     if not u:
#         await create_user(
#             {
#                 "email": email,
#                 "google_id": user_info["sub"],
#                 "name": user_info.get("name"),
#                 "created_at": time.time(),
#             }
#         )
#         u = await get_user_by_email(email)

#     jwt_token = create_jwt(
#         {"sub": str(u["_id"]), "email": u["email"]},
#         settings.APP_SECRET,
#         settings.JWT_EXPIRE_MIN,
#     )

#     return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth?token={jwt_token}")

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from .mongodb import (
    get_user_by_email,
    create_user,
    verify_otp_in_db,
    store_otp,
)
from .security import hash_password, verify_password, create_jwt
from .settings import settings
from .mailer import send_otp_email, generate_otp
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from fastapi.responses import RedirectResponse
import time

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthIn(BaseModel):
    email: EmailStr
    password: str


class VerifyOTPIn(BaseModel):
    email: EmailStr
    password: str
    otp: str


oauth = OAuth()
if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


@router.post("/request-signup")
async def request_signup(data: AuthIn):
    if await get_user_by_email(data.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    otp = generate_otp()
    await store_otp(data.email, otp)

    sent = await send_otp_email(data.email, otp)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return {"message": "Verification code sent to email"}


@router.post("/signup")
async def signup(data: VerifyOTPIn):
    valid = await verify_otp_in_db(data.email, data.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    user_id = await create_user(
        {
            "email": data.email,
            "password_hash": hash_password(data.password),
            "created_at": time.time(),
        }
    )

    return {"message": "User registered successfully", "id": str(user_id)}


@router.post("/signin")
async def signin(data: AuthIn):
    u = await get_user_by_email(data.email)
    if not u or not verify_password(data.password, u.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(
        {"sub": str(u["_id"]), "email": u["email"]},
        settings.APP_SECRET,
        settings.JWT_EXPIRE_MIN,
    )
    return {"access_token": token}


@router.get("/me")
async def get_me(email: str):
    u = await get_user_by_email(email)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "email": u["email"],
        "credits": u.get("credits", 0),
        "created_at": u.get("created_at"),
    }


@router.get("/login/google")
async def login_google(request: Request):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Google Login not configured")

    return await oauth.google.authorize_redirect(
        request,
        settings.GOOGLE_REDIRECT_URI,
    )


@router.get("/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google authorization failed: {str(e)}")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info from Google")

    email = user_info["email"]
    u = await get_user_by_email(email)

    if not u:
        await create_user(
            {
                "email": email,
                "google_id": user_info["sub"],
                "name": user_info.get("name"),
                "created_at": time.time(),
            }
        )
        u = await get_user_by_email(email)

    jwt_token = create_jwt(
        {"sub": str(u["_id"]), "email": u["email"]},
        settings.APP_SECRET,
        settings.JWT_EXPIRE_MIN,
    )

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/auth?token={jwt_token}")