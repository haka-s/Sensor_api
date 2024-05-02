import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
import os
from dotenv import load_dotenv
from fastapi_users.db import SQLAlchemyUserDatabase
from .models import User, get_user_db
from logging.config import dictConfig
import logging
from . import schemas
dictConfig(schemas.LogConfig().model_dump())
logger = logging.getLogger("SensorApi")
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
SECRET_KEY = os.getenv('KEY', 'Insecure_key')
if SECRET_KEY == 'Insecure_key':
    logger.warn('''no esta cargada la variable SECRET_KEY estas es necesaria para el correcto funcionamiento del sistema de autenticación
                podes generarla con el siguiente comando python -c 'import secrets; print(secrets.token_urlsafe(26))
                luego debe ser ingresada en el archivo .env
                '''
                
                )

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"el usuario {user.id} fue registrado.")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"el usuario {user.id} olvido su contraseña, Reset token: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"verificación para el usuario {user.id}. Verification token: {token}")


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)