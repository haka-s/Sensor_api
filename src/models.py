from sqlalchemy.future import select
from fastapi import Depends
from sqlalchemy import UUID, Column, Integer, Float, Boolean, String, DateTime, ForeignKey, create_engine
from sqlalchemy.orm import relationship, DeclarativeBase, sessionmaker
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import AsyncGenerator
from sqlalchemy.types import TIMESTAMP
from contextlib import asynccontextmanager

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
DATABASE_URL = f"postgresql+asyncpg://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}@db/{os.environ['DB_NAME']}"

class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String, nullable=True)

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def initialize_sensor_types():
    async with get_async_session() as db_session:
        predefined_sensor_types = [
            {"tipo": "boolean", "unidad": "estado"},
            {"tipo": "distancia", "unidad": "metros"},
            {"tipo": "velocidad", "unidad": "metros/segundo"},
            {"tipo": "energia", "unidad": "kWh"},  
            {"tipo": "presion", "unidad": "pascal"},
            {"tipo": "volumen", "unidad": "litros"},
            {"tipo": "temperatura", "unidad": "grados Celsius"}
        ]
        for sensor_type in predefined_sensor_types:
            existing_type = await db_session.execute(
                select(TipoSensor).where(TipoSensor.tipo == sensor_type["tipo"])
            )
            if not existing_type.scalars().first():
                new_type = TipoSensor(tipo=sensor_type["tipo"], unidad=sensor_type["unidad"])
                db_session.add(new_type)

        await db_session.commit()

@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_async_no_context_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = Depends(get_async_no_context_session)):
    yield SQLAlchemyUserDatabase(session, User)

class Maquina(Base):
    __tablename__ = 'maquinas'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    sensores = relationship("Sensor", back_populates="maquina", lazy="selectin")

class TipoSensor(Base):
    __tablename__ = 'tipos_sensor'
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String, nullable=False)  
    unidad = Column(String, nullable=False) 
    sensores = relationship("Sensor", back_populates="tipo_sensor", lazy="selectin")

class Sensor(Base):
    __tablename__ = 'sensores'
    id = Column(Integer, primary_key=True, index=True)
    tipo_sensor_id = Column(Integer, ForeignKey('tipos_sensor.id'))
    maquina_id = Column(Integer, ForeignKey('maquinas.id'))
    nombre = Column(String, nullable=False)  
    estado = Column(Boolean)
    valor = Column(Float)
    fecha_hora = Column(type_=TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    tipo_sensor = relationship("TipoSensor", back_populates="sensores")
    maquina = relationship("Maquina", back_populates="sensores")
    eventos_criticos = relationship("EventosCriticos", back_populates="sensor")

class EventosCriticos(Base):
    __tablename__ = 'eventos_criticos'
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    sensor_id = Column(Integer, ForeignKey('sensores.id'))
    value = Column(Float)
    description = Column(String)
    
    sensor = relationship("Sensor", back_populates="eventos_criticos")
    notificaciones = relationship("Notificaciones", back_populates="evento_critico")

class Notificaciones(Base):
    __tablename__ = 'notificaciones'
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey('eventos_criticos.id'))
    sent_to = Column(String)
    sent_timestamp = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    status = Column(String)
    
    evento_critico = relationship("EventosCriticos", back_populates="notificaciones")