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
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.authentication import BearerTransport
from sqlalchemy.future import select
from .users import auth_backend, current_active_user, fastapi_users
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
dictConfig(schemas.LogConfig().model_dump())
logger = logging.getLogger("SensorApi")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
    db = models.get_async_session()
    yield db
    
    
async def listen(client):
    db_session: get_db
    async for message in client.messages:
        logger.info(f"Topic: {message.topic}")
        logger.info(f"Payload: {message.payload.decode()}")

        if not validate_topic(message.topic):  # Check if topic is valid
            continue  # Skip to the next message if the topic is invalid
        
        maquina, tipo_sensor_nombre = parse_topic(message.topic)
        if maquina is None or tipo_sensor_nombre is None:
            continue  # This continue might be redundant if validate_topic always ensures correct parsing

        try:
            sensor_data = json.loads(message.payload.decode())
            await process_sensor_data(db_session, maquina, tipo_sensor_nombre, sensor_data)
        except (json.JSONDecodeError, KeyError):
            logger.error("Invalid payload data")
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")

def validate_topic(topic):
    logger.info('validation')
    topic_parts = topic.split('/')
    logger.info(topic_parts)
    if len(topic_parts) != 3:
        logger.error("Invalid topic format")
        return False
    return True

def parse_topic(topic):
    logger.info('parse')
    _, maquina, tipo_sensor_nombre = topic.split('/')
    return maquina, tipo_sensor_nombre

async def process_sensor_data(db_session, maquina, tipo_sensor_nombre, sensor_data):
    logger.info('process')
    sensor_value = sensor_data['value']
    maquina_id = select(models.Maquina).where(models.Maquina.nombre == maquina)

    tipo_sensor_stmt = select(models.TipoSensor).where(models.TipoSensor.nombre == tipo_sensor_nombre)
    tipo_sensor_result = await db_session.execute(tipo_sensor_stmt)
    tipo_sensor = tipo_sensor_result.scalars().first()

    if tipo_sensor is None:
        logger.error("Sensor no encontrado")
        return

    sensor_stmt = select(models.Sensor).where(
        models.Sensor.maquina_id == maquina_id,
        models.Sensor.tipo_sensor_id == tipo_sensor.id
    )
    sensor_result = await db_session.execute(sensor_stmt)
    sensor = sensor_result.scalars().first()

    if sensor is None:
        sensor = models.Sensor(
            maquina_id=maquina_id,
            tipo_sensor_id=tipo_sensor.id,
            estado=True,
        )
        db_session.add(sensor)

    sensor.valor = sensor_value
    sensor.fecha_hora = datetime.now(timezone.utc)

    await db_session.commit()
    logger.info(f"Sensor data updated for {tipo_sensor.nombre} on machine {maquina}")

        
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
async def create_machine(machine_data: schemas.MachineCreate, db: AsyncSession = Depends(models.get_async_session)):
    new_machine = models.Maquina(nombre=machine_data.nombre)
    db.add(new_machine)
    await db.commit()
    await db.refresh(new_machine)

    for sensor_data in machine_data.sensores:
        new_sensor = models.Sensor(
            tipo_sensor_id=sensor_data.tipo_sensor_id,  
            maquina_id=new_machine.id,
            estado=True,
            valor=0.0
        )
        db.add(new_sensor)
    await db.commit()

    return {"id": new_machine.id, "nombre": new_machine.nombre}

@app.post("/datos-sensor/")
async def crear_datos_sensor(sensor_id: int, valor: float, db: AsyncSession = Depends(models.get_async_session)):
    result = await db.execute(select(models.Sensor).where(models.Sensor.id == sensor_id))
    sensor = result.scalars().first()
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor no encontrado")
    
    datos_sensor = models.Sensor(valor=valor, fecha_hora=datetime.now(timezone.utc), tipo_sensor_id=sensor.tipo_sensor_id, maquina_id=sensor.maquina_id)
    db.add(datos_sensor)
    await db.commit()
    return {"mensaje": "Datos añadidos exitosamente", "datos": datos_sensor}
@app.post("/sensores/")
async def create_sensor(sensor_data: schemas.SensorCreate, db: AsyncSession = Depends(models.get_async_session)):
    result = await db.execute(select(models.Maquina).where(models.Maquina.id == sensor_data.maquina_id))
    machine = result.scalars().first()
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    new_sensor = models.Sensor(
        tipo_sensor_id=sensor_data.tipo_sensor_id,
        maquina_id=sensor_data.maquina_id,
        estado=sensor_data.estado,
        valor=sensor_data.valor,
    )
    db.add(new_sensor)
    await db.commit()
    await db.refresh(new_sensor)
    return {"id": new_sensor.id, "type": new_sensor.tipo_sensor_id}

@app.get("/tipo-sensor/", response_model=schemas.TipoSensorList)
async def list_tipo_sensor(db: AsyncSession = Depends(models.get_async_session)):
    result = await db.execute(select(models.TipoSensor))
    sensor_types = result.scalars().all()
    return schemas.TipoSensorList(tipos=sensor_types)

@app.post("/tipo-sensor/", response_model=schemas.TipoSensorCreate)
async def create_tipo_sensor(sensor_data: schemas.TipoSensorCreate, db: AsyncSession = Depends(models.get_async_session)):
    existing_sensor_type = await db.execute(select(models.TipoSensor).filter(models.TipoSensor.nombre == sensor_data.nombre))
    if existing_sensor_type.scalars().first():
        raise HTTPException(status_code=400, detail="Sensor type already exists")
    new_sensor_type = models.TipoSensor(nombre=sensor_data.nombre, unidad=sensor_data.unidad)
    db.add(new_sensor_type)
    await db.commit()
    await db.refresh(new_sensor_type)
    return new_sensor_type

@app.get("/maquinas/{maquina_id}")
async def read_maquina(maquina_id: int, db: AsyncSession = Depends(models.get_async_session)):
    result = await db.execute(select(models.Maquina).where(models.Maquina.id == maquina_id))
    maquina = result.scalars().first()
    if not maquina:
        raise HTTPException(status_code=404, detail="Machine not found")

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
async def get_sensor_history(
    sensor_id: int, 
    query: schemas.SensorHistoryQuery = Depends(),
    db: AsyncSession = Depends(models.get_async_session)):

    if not query:
        raise HTTPException(status_code=400, detail="Invalid date parameters")

    query_statement = select(models.Sensor).where(models.Sensor.id == sensor_id)
    if query.start_date:
        query_statement = query_statement.filter(models.Sensor.fecha_hora >= query.start_date)
    if query.end_date:
        query_statement = query_statement.filter(models.Sensor.fecha_hora <= query.end_date)

    result = await db.execute(query_statement)
    sensor_data = result.scalars().all()
    if not sensor_data:
        raise HTTPException(status_code=404, detail="No historical data found for this sensor.")

    return [{"value": data.valor, "datetime": data.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')} for data in sensor_data]
