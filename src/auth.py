from fastapi import HTTPException
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


