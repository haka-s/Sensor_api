from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models,schemas
from datetime import datetime,timezone,timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import asyncio
import aiomqtt
from logging.config import dictConfig
import logging
import os
from fastapi_users.authentication import BearerTransport

from .users import auth_backend, current_active_user, fastapi_users
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
dictConfig(schemas.LogConfig().model_dump())
logger = logging.getLogger("SensorApi")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def listen(client):
    async for message in client.messages:
        pass
        #logger.info(message.topic)
        #logger.info(message.payload.decode())

background_tasks = set()
client = None
@asynccontextmanager
async def lifespan(app):
    await models.create_db_and_tables()
    global client
    async with aiomqtt.Client(os.getenv('HOST_IP', 'localhost'),1883,username=None,password=None) as c:
        client = c
        await client.subscribe("maquinas/+/+")
        loop = asyncio.get_event_loop()
        task = loop.create_task(listen(client))
        background_tasks.add(task) # work around for blocking issues
        task.add_done_callback(background_tasks.remove) 
        yield 
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
app = FastAPI(lifespan=lifespan)
def get_db():
    db = models.async_session_maker()
    try:
        yield db
    finally:
        db.close()

        
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(schemas.UserRead, schemas.UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(schemas.UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(schemas.UserRead, schemas.UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.get("/authenticated-route")
async def authenticated_route(user: models.User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}

@app.post("/maquinas/")
def create_machine(machine_data: schemas.MachineCreate, db: Session = Depends(get_db)):
    new_machine = models.Maquina(nombre=machine_data.nombre)
    db.add(new_machine)
    db.commit()
    db.refresh(new_machine)

    for sensor_data in machine_data.sensores:
        new_sensor = models.Sensor(
            tipo_sensor_id=sensor_data.tipo_sensor_id,  
            maquina_id=new_machine.id,
            estado=True,
            valor=0.0
        )
        db.add(new_sensor)
    db.commit()

    return {"id": new_machine.id, "nombre": new_machine.nombre}

@app.post("/datos-sensor/")
async def crear_datos_sensor(sensor_id: int, valor: float, db: Session = Depends(get_db)):
    sensor = db.query(models.Sensor).filter(models.Sensor.id == sensor_id).first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")
    datos_sensor = models.Sensor(valor=valor, fecha_hora=datetime.now(timezone.utc), tipo_sensor_id=sensor.tipo_sensor_id, maquina_id=sensor.maquina_id)
    db.add(datos_sensor)
    db.commit()
    return {"mensaje": "Datos añadidos exitosamente", "datos": datos_sensor}

@app.post("/sensores/")
def create_sensor(sensor_data: schemas.SensorCreate, db: Session = Depends(get_db)):
    machine = db.query(models.Maquina).filter(models.Maquina.id == sensor_data.maquina_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    new_sensor = models.Sensor(
        tipo_sensor_id=sensor_data.tipo_sensor_id,
        maquina_id=sensor_data.maquina_id,
        estado=sensor_data.estado,
        valor=sensor_data.valor,
    )
    db.add(new_sensor)
    db.commit()
    db.refresh(new_sensor)
    return {"id": new_sensor.id, "type": new_sensor.tipo_sensor_id}

@app.get("/tipo-sensor/", response_model=schemas.TipoSensorList)
def list_tipo_sensor(db: Session = Depends(get_db)):
    sensor_types = db.query(models.TipoSensor).all()
    return schemas.TipoSensorList(tipos=sensor_types)

@app.post("/tipo-sensor/", response_model=schemas.TipoSensorCreate)
def create_tipo_sensor(sensor_data: schemas.TipoSensorCreate, db: Session = Depends(get_db)):
    existing_sensor_type = db.query(models.TipoSensor).filter(models.TipoSensor.nombre == sensor_data.nombre).first()
    if existing_sensor_type:
        raise HTTPException(status_code=400, detail="Sensor type already exists")
    new_sensor_type = models.TipoSensor(nombre=sensor_data.nombre, unidad=sensor_data.unidad)
    db.add(new_sensor_type)
    db.commit()
    db.refresh(new_sensor_type)
    return new_sensor_type

@app.get("/maquinas/{maquina_id}")
def read_maquina(maquina_id: int, db: Session = Depends(get_db)):
    maquina = db.query(models.Maquina).filter(models.Maquina.id == maquina_id).first()
    if not maquina:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Preparing data for response
    machine_data = {
        "id": maquina.id,
        "nombre": maquina.nombre,
        "sensores": [
            {
                "id": sensor.id,
                "tipo": sensor.tipo_sensor.nombre,
                "unidad": sensor.tipo_sensor.unidad,
                "estado": sensor.estado,
                "valor": sensor.valor,
                "fecha_hora": sensor.fecha_hora
            } for sensor in maquina.sensores
        ]
    }

    return machine_data
@app.get("/sensors/{sensor_id}/history")
def get_sensor_history(
    sensor_id: int, 
    query: schemas.SensorHistoryQuery = Depends(),
    db: Session = Depends(get_db)):

    if not query:
        raise HTTPException(status_code=400, detail="Invalid date parameters")

    query_statement = db.query(models.Sensor).filter(models.Sensor.id == sensor_id)
    if query.start_date:
        query_statement = query_statement.filter(models.Sensor.fecha_hora >= query.start_date)
    if query.end_date:
        query_statement = query_statement.filter(models.Sensor.fecha_hora <= query.end_date)

    sensor_data = query_statement.all()
    if not sensor_data:
        raise HTTPException(status_code=404, detail="No historical data found for this sensor.")

    return [{"value": data.valor, "datetime": data.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} for data in sensor_data]