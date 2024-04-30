from fastapi import Depends
from sqlalchemy import Column, Integer, Float, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship,DeclarativeBase
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import AsyncGenerator
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

DATABASE_URL = f"postgresql+asyncpg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@db/{os.environ['DB_NAME']}"  
class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

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

