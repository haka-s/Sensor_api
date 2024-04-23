
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
            raise HTTPException(status_code=401, detail="Invalid date parameters!!")
        elif start_date >= end_date:
            raise HTTPException(status_code=403, detail="fecha inicio debe ser menor a fecha final")
        return values