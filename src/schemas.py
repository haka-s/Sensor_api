from pydantic import BaseModel
from typing import List, Optional

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