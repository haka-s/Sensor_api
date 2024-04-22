from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models,schemas,auth, dependencies
from datetime import datetime,timezone,timedelta
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

    
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.init_db() 
    yield

app = FastAPI(lifespan=lifespan)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
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
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
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
        raise HTTPException(status_code=400, detail="Username already registered")
    new_user = models.User(username=user.username)
    new_user.hash_password(user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/{user_id}", response_model=schemas.UserDisplay)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
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

    # Create new sensor
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
def get_sensor_history(sensor_id: int, 
                       start_date: datetime = Query(None), 
                       end_date: datetime = Query(None), 
                       db: Session = Depends(get_db)):
    query = db.query(models.Sensor).filter(models.Sensor.id == sensor_id)

    if start_date:
        query = query.filter(Sensor.fecha_hora >= start_date)
    if end_date:
        query = query.filter(Sensor.fecha_hora <= end_date)

    sensor_data = query.all()
    if not sensor_data:
        raise HTTPException(status_code=404, detail="No historical data found for this sensor.")

    return [{"valor": data.valor, "fecha_hora": data.fecha_hora} for data in sensor_data]
