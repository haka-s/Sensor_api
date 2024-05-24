from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Depends, HTTPException, status,Query
from sqlalchemy.orm import selectinload,joinedload
from . import models,schemas
from datetime import tzinfo,datetime,timezone,timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import asyncio
import aiomqtt
from logging.config import dictConfig
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.authentication import BearerTransport
from sqlalchemy.future import select
from sqlalchemy.orm import aliased
from sqlalchemy import and_, desc, func
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
    await models.initialize_sensor_types()
    global client
    async with aiomqtt.Client(os.getenv('HOST_IP', 'localhost'), 1883) as c:
        client = c
        await client.subscribe("maquinas/+/+/+")
        loop = asyncio.get_event_loop()
        task = loop.create_task(listen(client))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        yield
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        

app = FastAPI(lifespan=lifespan)
@asynccontextmanager
async def get_db():
    async with models.get_async_session() as session:
        yield session
async def listen(client):
    async for message in client.messages:
        logger.info(f"Topic: {message.topic}")
        logger.info(f"Payload: {message.payload.decode()}")

        topic_str = str(message.topic)
        if not validate_topic(topic_str):
            continue

        maquina, tipo_sensor_nombre, sensor_name = parse_topic(topic_str)

        try:
            sensor_data = message.payload.decode()
            async with get_db() as db_session:
                await process_sensor_data(db_session, maquina, tipo_sensor_nombre, sensor_name, sensor_data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Invalid payload data: {e}")
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")

def validate_topic(topic):
    parts = topic.split('/')
    if len(parts) != 4:
        logger.error(f"Invalid topic format: {topic}")
        return False
    return True

def parse_topic(topic):
    _, maquina, tipo_sensor_nombre, sensor_name = topic.split('/')
    return maquina, tipo_sensor_nombre, sensor_name

async def process_sensor_data(db_session, maquina, tipo_sensor_nombre, sensor_name, sensor_data):
    maquina_obj = await get_or_create(db_session, models.Maquina, nombre=maquina)
    tipo_sensor = await get_or_create(db_session, models.TipoSensor, tipo=tipo_sensor_nombre)

    # Create a new sensor data record instead of updating an existing one
    new_sensor_data = models.Sensor(
        maquina_id=maquina_obj.id,
        tipo_sensor_id=tipo_sensor.id,
        nombre=sensor_name,
        estado=convert_to_boolean(sensor_data),
        valor=convert_to_float(sensor_data),
        fecha_hora=datetime.now(timezone.utc)
    )
    db_session.add(new_sensor_data)
    await db_session.commit()
    logger.info(f"New sensor data recorded for '{sensor_name}' in machine '{maquina}' with type '{tipo_sensor_nombre}'.")
def convert_to_boolean(sensor_data):
    if isinstance(sensor_data, str):
        return sensor_data.lower() in ['true', '1', 't', 'y', 'yes']
    return bool(sensor_data)

def convert_to_float(sensor_data):
    if isinstance(sensor_data, str) and sensor_data.lower() in ['true', 'false']:
        return 1.0 if sensor_data.lower() == 'true' else 0.0
    try:
        return float(sensor_data)
    except ValueError:
        logger.error(f"Could not convert data to float: '{sensor_data}'")
        return 0.0  # Default value or handle error appropriately
async def get_or_create(db_session, model, **kwargs):
    instance = await db_session.execute(select(model).filter_by(**kwargs))
    instance = instance.scalars().first()
    if not instance:
        instance = model(**kwargs)
        db_session.add(instance)
        await db_session.flush()
        await db_session.refresh(instance)
    return instance
        
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


@app.get("/tipo-sensor/", response_model=schemas.TipoSensorList)
async def list_tipo_sensor(db: AsyncSession = Depends(models.get_async_no_context_session)):
    result = await db.execute(select(models.TipoSensor))
    sensor_types = result.scalars().all()
    return schemas.TipoSensorList(tipos=sensor_types)

@app.post("/tipo-sensor/", response_model=schemas.TipoSensorCreate)
async def create_tipo_sensor(sensor_data: schemas.TipoSensorCreate,db: AsyncSession = Depends(models.get_async_no_context_session)):
    existing_sensor_type = await db.execute(select(models.TipoSensor).filter(models.TipoSensor.nombre == sensor_data.nombre))
    if existing_sensor_type.scalars().first():
        raise HTTPException(status_code=400, detail="Ya existe este tipo de sensor")
    new_sensor_type = models.TipoSensor(nombre=sensor_data.nombre, unidad=sensor_data.unidad)
    db.add(new_sensor_type)
    await db.commit()
    await db.refresh(new_sensor_type)
    return new_sensor_type

@app.get("/maquinas/{maquina_id}")
async def read_maquina(maquina_id: int, db: AsyncSession = Depends(models.get_async_no_context_session)):
    async with db as session:
        # Construct the subquery to find the latest sensor entry by type and name
        subquery = (
            select(
                models.Sensor.tipo_sensor_id,
                models.Sensor.nombre,
                func.max(models.Sensor.fecha_hora).label("max_fecha_hora")
            )
            .where(models.Sensor.maquina_id == maquina_id)
            .group_by(models.Sensor.tipo_sensor_id, models.Sensor.nombre)
            .subquery()
        )

        # Retrieve the latest sensors based on the subquery
        ultimo_sensor_query = (
            select(models.Sensor)
            .join(
                subquery,
                (models.Sensor.tipo_sensor_id == subquery.c.tipo_sensor_id) &
                (models.Sensor.nombre == subquery.c.nombre) &
                (models.Sensor.fecha_hora == subquery.c.max_fecha_hora)
            )
            .order_by(desc(models.Sensor.fecha_hora))
            .options(joinedload(models.Sensor.tipo_sensor))
        )

        # Fetch machine details
        maquina_result = await session.execute(
            select(models.Maquina)
            .where(models.Maquina.id == maquina_id)
            .options(selectinload(models.Maquina.sensores).joinedload(models.Sensor.tipo_sensor))
        )
        maquina = maquina_result.scalars().first()
        if not maquina:
            raise HTTPException(status_code=404, detail="Machine not found")

        # Execute the sensor query
        ultimo_sensor_data = await session.execute(ultimo_sensor_query)
        ultimos_sensores = ultimo_sensor_data.scalars().all()

        # Serialize machine and sensor data
        maquina_data = {
            "id": maquina.id,
            "nombre": maquina.nombre,
            "sensores": [
                {
                    "id": sensor.id,
                    "nombre": sensor.nombre,
                    "tipo": sensor.tipo_sensor.tipo,
                    "unidad": sensor.tipo_sensor.unidad,
                    "estado": sensor.estado,
                    "valor": sensor.valor,
                    "fecha_hora": sensor.fecha_hora.isoformat()
                } for sensor in ultimos_sensores
            ]
        }

        return maquina_data
@app.get("/maquinas/{maquina_id}/sensores/historial")
async def obtener_historial_sensores(
    maquina_id: int,
    nombre_sensor: str = Query(None, description="Filtrar por nombre del sensor"),
    tipo_sensor: str = Query(None, description="Filtrar por tipo de sensor"),
    fecha_inicio: datetime = Query(None, description="Fecha de inicio del historial en formato YYYY-MM-DD HH:MM:SS"),
    fecha_fin: datetime = Query(None, description="Fecha de fin del historial en formato YYYY-MM-DD HH:MM:SS"),
    db: AsyncSession = Depends(models.get_async_no_context_session)):

    # Construir la subconsulta para encontrar las últimas entradas de sensores según los filtros
    subquery = (
        select(
            models.Sensor.id,
            func.max(models.Sensor.fecha_hora).label("max_fecha_hora")
        )
        .where(models.Sensor.maquina_id == maquina_id)
        .group_by(models.Sensor.id)
        .subquery()
    )

    # Crear la consulta principal usando la subconsulta para asegurar que solo se obtengan los datos más recientes
    sensores_query = (
        select(models.Sensor)
        .join(subquery, (models.Sensor.id == subquery.c.id) & (models.Sensor.fecha_hora == subquery.c.max_fecha_hora))
        .options(joinedload(models.Sensor.tipo_sensor))
    )

    # Aplicar filtros adicionales si se proporcionan
    if nombre_sensor:
        sensores_query = sensores_query.filter(models.Sensor.nombre == nombre_sensor)
    if tipo_sensor:
        sensores_query = sensores_query.filter(models.Sensor.tipo_sensor.has(tipo=tipo_sensor))
    if fecha_inicio:
        sensores_query = sensores_query.filter(models.Sensor.fecha_hora >= fecha_inicio)
    if fecha_fin:
        sensores_query = sensores_query.filter(models.Sensor.fecha_hora <= fecha_fin)

    # Ejecutar la consulta
    sensores_data = await db.execute(sensores_query)
    sensores = sensores_data.scalars().all()

    # Manejar el caso de no encontrar datos
    if not sensores:
        raise HTTPException(status_code=404, detail="No se encontraron datos históricos para los criterios especificados.")

    # Formatear y devolver los datos
    return [{
        "sensor_id": sensor.id,
        "nombre_sensor": sensor.nombre,
        "tipo_sensor": sensor.tipo_sensor.tipo,
        "valor": sensor.valor,
        "fecha_hora": sensor.fecha_hora.isoformat()
    } for sensor in sensores]
