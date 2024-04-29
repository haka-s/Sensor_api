from jose import jwt
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from typing import Optional
from logging.config import dictConfig
import logging
from .schemas import LogConfig


dictConfig(LogConfig().model_dump())
logger = logging.getLogger("SensorApi")

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
SECRET_KEY = os.getenv('KEY', 'Insecure_key')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

if SECRET_KEY == 'Insecure_key':
    logger.warn('Estas corriendo una instancia insegura ya que no esta cargada la variable de entorno key, la cual proporciona el cifrado de los tokens jwt')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta if expires_delta else timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


