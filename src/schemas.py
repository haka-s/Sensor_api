
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator
from typing import List, Optional
import datetime

class UserCreate(BaseModel):
    username: str
    password: str
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
class UserDisplay(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True
class SensorCreate(BaseModel):
    tipo_sensor_id: int
    maquina_id: int
    estado: bool
    valor: float
    
class MachineCreate(BaseModel):
    nombre: str
    sensores: List[SensorCreate] = []
    
class TipoSensorCreate(BaseModel):
    nombre: str
    unidad: str
    
class TipoSensorList(BaseModel):
    tipos: List[TipoSensorCreate]

class SensorHistoryQuery(BaseModel):
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None

    @model_validator(mode='before')
    def check_dates(cls, values):
        start_date = values.get('start_date')
        end_date = values.get('end_date')
        if  not start_date or not end_date:
            raise HTTPException(status_code=401, detail="Parámetros inválidos")
        elif start_date >= end_date:
            raise HTTPException(status_code=403, detail="fecha inicio debe ser menor a fecha final")
        return values
class LogConfig(BaseModel):
    """Logging configuration to be set for the server"""

    LOGGER_NAME: str = "SensorApi"
    LOG_FORMAT: str = "%(levelprefix)s | %(asctime)s | %(message)s"
    LOG_LEVEL: str = "DEBUG"

    # Logging config
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