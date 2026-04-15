from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    # Truncate to 72 characters (bcrypt limit) to prevent ValueError
    return pwd_ctx.hash(pw[:72])

def verify_password(pw: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(pw[:72], hashed)
    except:
        return False

def create_jwt(payload: dict, secret: str, expire_min: int) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expire_min)
    to_encode = {**payload, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(to_encode, secret, algorithm="HS256")

def verify_jwt(token: str, secret: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except:
        return None