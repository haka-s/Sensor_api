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
import random
import string
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
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
conf_correo = ConnectionConfig(
    MAIL_USERNAME = str(os.getenv("MAIL_USERNAME")),
    MAIL_PASSWORD = str(os.getenv("MAIL_PASSWORD")),
    MAIL_FROM = str("sistemas@bauduccosa.com.ar"),
    MAIL_PORT = 25,
    MAIL_SERVER = str(os.getenv("MAIL_SERVER")),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

fastmail = FastMail(conf_correo)
def generate_verification_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET_KEY
    verification_token_secret = SECRET_KEY

    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"El usuario {user.id} fue registrado.")
        verification_code = generate_verification_code()
        
        # Actualizar el usuario con el código de verificación
        await self.user_db.update(user, {"verification_code": verification_code})

        # Enviar correo de verificación
        message = MessageSchema(
            subject="Verifica tu correo electrónico",
            recipients=[user.email],
            body=f"Tu código de verificación es: {verification_code}",
            subtype="html"
        )
        print(verification_code)
        await fastmail.send_message(message)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"El usuario {user.id} olvidó su contraseña. Token de restablecimiento: {token}")

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"Verificación solicitada para el usuario {user.id}. Token de verificación: {token}")

    async def verify_user(self, user: User, code: str):
        if user.verification_code == code:
            await self.user_db.update(user, {"is_verified": True, "verification_code": None})
            return True
        return False

    # Keep the existing verify_email method as well
    async def verify_email(self, user: User, code: str):
        return await self.verify_user(user, code)
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