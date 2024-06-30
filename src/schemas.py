import re
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
import uuid
from fastapi_users import schemas

class UserRead(schemas.BaseUser[uuid.UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass

class TipoSensorBase(BaseModel):
    tipo: str
    unidad: str

class TipoSensorCreate(TipoSensorBase):
    pass

class TipoSensorRead(TipoSensorBase):
    id: int

    class Config:
        from_attributes = True
class VerifyEmailSchema(BaseModel):
    email: str
    code: str
class TipoSensorList(BaseModel):
    tipos: List[TipoSensorRead]

class SensorBase(BaseModel):
    nombre: str
    tipo_sensor_id: int
    maquina_id: int
    estado: Optional[bool] = None
    valor: Optional[float] = None

class SensorListaRead(BaseModel):
    nombre: str
    tipo: str

class MaquinaListaRead(BaseModel):
    id: int
    nombre: str
    sensores: List[SensorListaRead]

    class Config:
        from_attributes = True

class SensorCreate(SensorBase):
    pass

class SensorRead(SensorBase):
    id: int
    fecha_hora: datetime

    class Config:
        from_attributes = True

class MaquinaBase(BaseModel):
    nombre: str

class MaquinaCreate(MaquinaBase):
    sensores: List[SensorCreate] = []

class MaquinaRead(MaquinaBase):
    id: int
    sensores: List[SensorRead] = []

    class Config:
        from_attributes = True

class EventoCriticoBase(BaseModel):
    sensor_id: int
    value: float
    description: str

class EventoCriticoCreate(EventoCriticoBase):
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class EventoCriticoRead(EventoCriticoBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class NotificacionBase(BaseModel):
    event_id: int
    sent_to: EmailStr
    status: str

class NotificacionCreate(NotificacionBase):
    sent_timestamp: datetime = Field(default_factory=datetime.utcnow)

class NotificacionRead(NotificacionBase):
    id: int
    sent_timestamp: datetime

    class Config:
        from_attributes = True

class SensorHistoryQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class AnalisisTendencia(BaseModel):
    sensor: str
    tendencia: str
    pendiente: float
    r_cuadrado: float
    datos: List[dict]

class ResumenMaquina(BaseModel):
    maquina: str
    ultimo_estado: List[dict]
    eventos_recientes: List[dict]

class LogConfig(BaseModel):
    LOGGER_NAME: str = "SensorApi"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "DEBUG"

    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": LOG_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    }
    handlers: dict = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    }
    loggers: dict = {
        LOGGER_NAME: {"handlers": ["default"], "level": LOG_LEVEL},
    }