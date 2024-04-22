from jose import jwt, ExpiredSignatureError, JWTError
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from typing import Optional
from .models import pwd_context

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
SECRET_KEY = os.getenv('KEY', 'your_default_secret_key')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
        return username
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired", headers={"WWW-Authenticate": "Bearer"})
    except JWTError:
        raise credentials_exception
