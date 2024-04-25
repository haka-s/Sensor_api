from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

DATABASE_URL = f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@db/{os.environ['DB_NAME']}"  

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)
    def verify_password(self, password):
        return pwd_context.verify(password, self.hashed_password)

    def hash_password(self, password):
        self.hashed_password = pwd_context.hash(password)

class Maquina(Base):
    __tablename__ = 'maquinas'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    sensores = relationship("Sensor", back_populates="maquina")

class TipoSensor(Base):
    __tablename__ = 'tipos_sensor'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)  
    unidad = Column(String, nullable=False) 
    sensores = relationship("Sensor", back_populates="tipo_sensor")

class Sensor(Base):
    __tablename__ = 'sensores'
    id = Column(Integer, primary_key=True, index=True)
    tipo_sensor_id = Column(Integer, ForeignKey('tipos_sensor.id'))
    maquina_id = Column(Integer, ForeignKey('maquinas.id'))
    estado = Column(Boolean)
    valor = Column(Float)
    fecha_hora = Column(DateTime, default=datetime.now(timezone.utc))
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")
    maquina = relationship("Maquina", back_populates="sensores")

def init_db():
    Base.metadata.create_all(bind=engine)