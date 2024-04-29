from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models,schemas,auth, dependencies
from datetime import datetime,timezone,timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import asyncio
import aiomqtt
from logging.config import dictConfig
import logging
import os

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
    models.init_db()
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
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()

        
@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="usuario o contraseña incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role == 'mqqt_broker':
        access_token_expires = timedelta(minutes=900)
    else:    
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserDisplay)
def read_users_me(current_user: str = Depends(dependencies.get_current_user), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == current_user).first()
    return user
@app.post("/users/", response_model=schemas.UserDisplay)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="usuario ya registrado")
    new_user = models.User(username=user.username, role=user.role)
    
    new_user.hash_password(user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/{user_id}", response_model=schemas.UserDisplay)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user

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
def create_tipo_sensor(sensor_data: schemas.TipoSensorCreate, db: Session = Depends(get_db),current_user: models.User = Depends(dependencies.require_role('admin'))):
    existing_sensor_type = db.query(models.TipoSensor).filter(models.TipoSensor.nombre == sensor_data.nombre).first()
    if existing_sensor_type:
        raise HTTPException(status_code=400, detail="Sensor type already exists")
    new_sensor_type = models.TipoSensor(nombre=sensor_data.nombre, unidad=sensor_data.unidad)
    db.add(new_sensor_type)
    db.commit()
    db.refresh(new_sensor_type)
    return new_sensor_type

@app.get("/maquinas/{maquina_id}")
def read_maquina(maquina_id: int, db: Session = Depends(get_db),current_user: models.User = Depends(dependencies.require_role('admin'))):
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