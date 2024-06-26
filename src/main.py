from contextlib import asynccontextmanager
import json
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import selectinload, joinedload
from . import models, schemas
from datetime import datetime, timezone, timedelta
from fastapi.security import OAuth2PasswordBearer
import asyncio
import aiomqtt
from logging.config import dictConfig
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi_users.authentication import BearerTransport
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from .users import auth_backend, current_active_user, fastapi_users
from scipy import stats
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from fpdf import FPDF

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
dictConfig(schemas.LogConfig().model_dump())
logger = logging.getLogger("SensorApi")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
tareas_fondo = set()
cliente = None

# Configuración de correo electrónico
conf_correo = ConnectionConfig(
    MAIL_USERNAME = str(os.getenv("MAIL_USERNAME")),
    MAIL_PASSWORD = str(os.getenv("MAIL_PASSWORD")),
    MAIL_FROM = str("sistemas@bauduccosa.com.ar"),
    MAIL_PORT = 25,
    MAIL_SERVER = str(os.getenv("MAIL_SERVER")),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

fastmail = FastMail(conf_correo)

@asynccontextmanager
async def lifespan(app):
    await models.create_db_and_tables()
    await models.initialize_sensor_types()
    global cliente
    async with aiomqtt.Client(os.getenv('HOST_IP', 'localhost'), 1883) as c:
        cliente = c
        await cliente.subscribe("maquinas/+/+/+")
        bucle = asyncio.get_event_loop()
        tarea = bucle.create_task(escuchar(cliente))
        tareas_fondo.add(tarea)
        tarea.add_done_callback(tareas_fondo.discard)
        yield
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan, root_path="/api/")

@asynccontextmanager
async def obtener_db():
    async with models.get_async_session() as sesion:
        yield sesion

async def escuchar(cliente):
    async for mensaje in cliente.messages:
        logger.info(f"Tema: {mensaje.topic}")
        logger.info(f"Carga útil: {mensaje.payload.decode()}")

        tema_str = str(mensaje.topic)
        if not validar_tema(tema_str):
            continue

        maquina, tipo_sensor_nombre, nombre_sensor = analizar_tema(tema_str)

        try:
            datos_sensor = mensaje.payload.decode()
            async with obtener_db() as sesion_db:
                await procesar_datos_sensor(sesion_db, maquina, tipo_sensor_nombre, nombre_sensor, datos_sensor)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Datos de carga útil inválidos: {e}")
        except Exception as e:
            logger.error(f"Error al procesar datos del sensor: {e}")

def validar_tema(tema):
    partes = tema.split('/')
    if len(partes) != 4:
        logger.error(f"Formato de tema inválido: {tema}")
        return False
    return True

def analizar_tema(tema):
    _, maquina, tipo_sensor_nombre, nombre_sensor = tema.split('/')
    return maquina, tipo_sensor_nombre, nombre_sensor

async def procesar_datos_sensor(sesion_db, maquina, tipo_sensor_nombre, nombre_sensor, datos_sensor):
    maquina_obj = await obtener_o_crear(sesion_db, models.Maquina, nombre=maquina)
    tipo_sensor = await obtener_o_crear(sesion_db, models.TipoSensor, tipo=tipo_sensor_nombre)

    nuevos_datos_sensor = models.Sensor(
        maquina_id=maquina_obj.id,
        tipo_sensor_id=tipo_sensor.id,
        nombre=nombre_sensor,
        estado=convertir_a_booleano(datos_sensor),
        valor=convertir_a_float(datos_sensor),
        fecha_hora=datetime.now(timezone.utc)
    )
    sesion_db.add(nuevos_datos_sensor)
    await sesion_db.commit()
    
    # Analizar anomalías
    await analizar_anomalias(sesion_db, nuevos_datos_sensor)

    logger.info(f"Nuevos datos de sensor registrados para '{nombre_sensor}' en la máquina '{maquina}' con tipo '{tipo_sensor_nombre}'.")

def convertir_a_booleano(datos_sensor):
    if isinstance(datos_sensor, str):
        return datos_sensor.lower() in ['true', '1', 't', 'y', 'yes']
    return bool(datos_sensor)

def convertir_a_float(datos_sensor):
    if isinstance(datos_sensor, str) and datos_sensor.lower() in ['true', 'false']:
        return 1.0 if datos_sensor.lower() == 'true' else 0.0
    try:
        return float(datos_sensor)
    except ValueError:
        logger.error(f"No se pudo convertir datos a float: '{datos_sensor}'")
        return 0.0

async def obtener_o_crear(sesion_db, modelo, **kwargs):
    instancia = await sesion_db.execute(select(modelo).filter_by(**kwargs))
    instancia = instancia.scalars().first()
    if not instancia:
        instancia = modelo(**kwargs)
        sesion_db.add(instancia)
        await sesion_db.flush()
        await sesion_db.refresh(instancia)
    return instancia

async def analizar_anomalias(sesion_db, nuevo_dato):
    # Obtener datos históricos del mismo sensor
    datos_historicos = await sesion_db.execute(
        select(models.Sensor.valor)
        .filter(
            models.Sensor.maquina_id == nuevo_dato.maquina_id,
            models.Sensor.tipo_sensor_id == nuevo_dato.tipo_sensor_id,
            models.Sensor.nombre == nuevo_dato.nombre
        )
        .order_by(models.Sensor.fecha_hora.desc())
        .limit(100)
    )
    valores_historicos = [row[0] for row in datos_historicos.fetchall()]

    if len(valores_historicos) < 2:
        return  # No hay suficientes datos para análisis

    # Calcular Z-score
    media = stats.mean(valores_historicos)
    desviacion_estandar = stats.stdev(valores_historicos)
    z_score = (nuevo_dato.valor - media) / desviacion_estandar

    # Definir umbral para eventos críticos
    umbral_z_score = 3

    if abs(z_score) > umbral_z_score:
        descripcion = f"Valor anómalo detectado: {nuevo_dato.valor} (Z-score: {z_score:.2f})"
        evento_critico = models.EventosCriticos(
            sensor_id=nuevo_dato.id,
            value=nuevo_dato.valor,
            description=descripcion
        )
        sesion_db.add(evento_critico)
        await sesion_db.commit()

        # Generar notificación
        await generar_notificacion(sesion_db, evento_critico)

async def generar_notificacion(sesion_db, evento_critico,usuario: models.User = Depends(current_active_user)):
    notificacion = models.Notificaciones(
        event_id=evento_critico.id,
        sent_to=usuario.email,
        status="pendiente"
    )
    sesion_db.add(notificacion)
    await sesion_db.commit()

    # Enviar correo electrónico
    await enviar_correo_notificacion(evento_critico, notificacion)

async def enviar_correo_notificacion(evento_critico, notificacion):
    contenido_pdf = generar_pdf_evento(evento_critico)
    
    mensaje = MessageSchema(
        subject="Notificación de Evento Crítico",
        recipients=[notificacion.sent_to],
        body="Se ha detectado un evento crítico. Por favor, revise el archivo adjunto para más detalles.",
        attachments=[{
            "file": contenido_pdf,
            "filename": "evento_critico.pdf",
            "mime_type": "application/pdf",
        }]
    )

    await fastmail.send_message(mensaje)
    
    # Actualizar estado de notificación
    async with obtener_db() as sesion:
        notificacion.status = "enviado"
        await sesion.commit()

def generar_pdf_evento(evento_critico):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Evento Crítico ID: {evento_critico.id}", ln=1, align="C")
    pdf.cell(200, 10, txt=f"Fecha y Hora: {evento_critico.timestamp}", ln=1)
    pdf.cell(200, 10, txt=f"Sensor ID: {evento_critico.sensor_id}", ln=1)
    pdf.cell(200, 10, txt=f"Valor: {evento_critico.value}", ln=1)
    pdf.cell(200, 10, txt=f"Descripción: {evento_critico.description}", ln=1)
    return pdf.output(dest="S").encode("latin1")

# Rutas de autenticación y usuarios
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

@app.get("/ruta-autenticada")
async def ruta_autenticada(usuario: models.User = Depends(current_active_user)):
    return {"mensaje": f"¡Hola {usuario.email}!"}

@app.get("/tipo-sensor/", response_model=schemas.TipoSensorList)
async def listar_tipos_sensor(db: AsyncSession = Depends(models.get_async_no_context_session)):
    resultado = await db.execute(select(models.TipoSensor))
    tipos_sensor = resultado.scalars().all()
    return schemas.TipoSensorList(tipos=tipos_sensor)

@app.post("/tipo-sensor/", response_model=schemas.TipoSensorCreate)
async def crear_tipo_sensor(datos_sensor: schemas.TipoSensorCreate, db: AsyncSession = Depends(models.get_async_no_context_session)):
    tipo_sensor_existente = await db.execute(select(models.TipoSensor).filter(models.TipoSensor.nombre == datos_sensor.nombre))
    if tipo_sensor_existente.scalars().first():
        raise HTTPException(status_code=400, detail="Ya existe este tipo de sensor")
    nuevo_tipo_sensor = models.TipoSensor(nombre=datos_sensor.nombre, unidad=datos_sensor.unidad)
    db.add(nuevo_tipo_sensor)
    await db.commit()
    await db.refresh(nuevo_tipo_sensor)
    return nuevo_tipo_sensor

@app.get("/maquinas/{maquina_id}")
async def leer_maquina(maquina_id: int, db: AsyncSession = Depends(models.get_async_no_context_session)):
    async with db as sesion:
        subconsulta = (
            select(
                models.Sensor.tipo_sensor_id,
                models.Sensor.nombre,
                func.max(models.Sensor.fecha_hora).label("max_fecha_hora")
            )
            .where(models.Sensor.maquina_id == maquina_id)
            .group_by(models.Sensor.tipo_sensor_id, models.Sensor.nombre)
            .subquery()
        )

        consulta_ultimo_sensor = (
            select(models.Sensor)
            .join(
                subconsulta,
                (models.Sensor.tipo_sensor_id == subconsulta.c.tipo_sensor_id) &
                (models.Sensor.nombre == subconsulta.c.nombre) &
                (models.Sensor.fecha_hora == subconsulta.c.max_fecha_hora)
            )
            .order_by(desc(models.Sensor.fecha_hora))
            .options(joinedload(models.Sensor.tipo_sensor))
        )

        resultado_maquina = await sesion.execute(
            select(models.Maquina)
            .where(models.Maquina.id == maquina_id)
            .options(selectinload(models.Maquina.sensores).joinedload(models.Sensor.tipo_sensor))
        )
        maquina = resultado_maquina.scalars().first()
        if not maquina:
            raise HTTPException(status_code=404, detail="Máquina no encontrada")

        datos_ultimo_sensor = await sesion.execute(consulta_ultimo_sensor)
        ultimos_sensores = datos_ultimo_sensor.scalars().all()

        datos_maquina = {
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

        return datos_maquina

@app.get("/maquinas/{maquina_id}/sensores/historial")
async def obtener_historial_sensores(
    maquina_id: int,
    nombre_sensor: str = Query(None, description="Filtrar por nombre del sensor"),
    tipo_sensor: str = Query(None, description="Filtrar por tipo de sensor"),
    fecha_inicio: datetime = Query(None, description="Fecha de inicio del historial en formato YYYY-MM-DD HH:MM:SS"),
    fecha_fin: datetime = Query(None, description="Fecha de fin del historial en formato YYYY-MM-DD HH:MM:SS"),
    db: AsyncSession = Depends(models.get_async_no_context_session)):

    # Construir la subconsulta para encontrar las últimas entradas de sensores según los filtros
    subconsulta = (
        select(
            models.Sensor.id,
            func.max(models.Sensor.fecha_hora).label("max_fecha_hora")
        )
        .where(models.Sensor.maquina_id == maquina_id)
        .group_by(models.Sensor.id)
        .subquery()
    )

    # Crear la consulta principal usando la subconsulta para asegurar que solo se obtengan los datos más recientes
    consulta_sensores = (
        select(models.Sensor)
        .join(subconsulta, (models.Sensor.id == subconsulta.c.id) & (models.Sensor.fecha_hora == subconsulta.c.max_fecha_hora))
        .options(joinedload(models.Sensor.tipo_sensor))
    )

    # Aplicar filtros adicionales si se proporcionan
    if nombre_sensor:
        consulta_sensores = consulta_sensores.filter(models.Sensor.nombre == nombre_sensor)
    if tipo_sensor:
        consulta_sensores = consulta_sensores.filter(models.Sensor.tipo_sensor.has(tipo=tipo_sensor))
    if fecha_inicio:
        consulta_sensores = consulta_sensores.filter(models.Sensor.fecha_hora >= fecha_inicio)
    if fecha_fin:
        consulta_sensores = consulta_sensores.filter(models.Sensor.fecha_hora <= fecha_fin)

    # Ejecutar la consulta
    datos_sensores = await db.execute(consulta_sensores)
    sensores = datos_sensores.scalars().all()

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

@app.get("/eventos-criticos/", response_model=List[schemas.EventoCriticoRead])
async def listar_eventos_criticos(
    db: AsyncSession = Depends(models.get_async_no_context_session),
    skip: int = 0,
    limit: int = 100
):
    resultado = await db.execute(
        select(models.EventosCriticos)
        .order_by(models.EventosCriticos.timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    eventos = resultado.scalars().all()
    return eventos

@app.get("/notificaciones/", response_model=List[schemas.NotificacionRead])
async def listar_notificaciones(
    db: AsyncSession = Depends(models.get_async_no_context_session),
    skip: int = 0,
    limit: int = 100
):
    resultado = await db.execute(
        select(models.Notificaciones)
        .order_by(models.Notificaciones.sent_timestamp.desc())
        .offset(skip)
        .limit(limit)
    )
    notificaciones = resultado.scalars().all()
    return notificaciones

@app.post("/reenviar-notificacion/{notificacion_id}")
async def reenviar_notificacion(
    notificacion_id: int,
    tareas_fondo: BackgroundTasks,
    db: AsyncSession = Depends(models.get_async_no_context_session)
    ):
    notificacion = await db.get(models.Notificaciones, notificacion_id)
    if not notificacion:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    evento_critico = await db.get(models.EventosCriticos, notificacion.event_id)
    if not evento_critico:
        raise HTTPException(status_code=404, detail="Evento crítico no encontrado")

    # Reenviar notificación en segundo plano
    tareas_fondo.add_task(enviar_correo_notificacion, evento_critico, notificacion)

    return {"mensaje": "Notificación programada para reenvío"}

@app.get("/analisis-tendencias/{maquina_id}/{sensor_nombre}")
async def analizar_tendencias(
    maquina_id: int,
    sensor_nombre: str,
    dias: int = Query(7, description="Número de días para el análisis"),
    db: AsyncSession = Depends(models.get_async_no_context_session)
):
    fecha_limite = datetime.now(timezone.utc) - timedelta(days=dias)
    
    resultado = await db.execute(
        select(models.Sensor)
        .filter(
            models.Sensor.maquina_id == maquina_id,
            models.Sensor.nombre == sensor_nombre,
            models.Sensor.fecha_hora >= fecha_limite
        )
        .order_by(models.Sensor.fecha_hora)
    )
    datos = resultado.scalars().all()

    if not datos:
        raise HTTPException(status_code=404, detail="No se encontraron datos para el análisis")

    valores = [dato.valor for dato in datos]
    fechas = [dato.fecha_hora for dato in datos]

    # Calcular tendencia lineal
    x = range(len(valores))
    pendiente, intercepto, r_valor, p_valor, error_estandar = stats.linregress(x, valores)

    tendencia = "creciente" if pendiente > 0 else "decreciente" if pendiente < 0 else "estable"

    return {
        "sensor": sensor_nombre,
        "tendencia": tendencia,
        "pendiente": pendiente,
        "r_cuadrado": r_valor**2,
        "datos": [{"fecha": fecha.isoformat(), "valor": valor} for fecha, valor in zip(fechas, valores)]
    }

@app.get("/resumen-maquina/{maquina_id}")
async def obtener_resumen_maquina(
    maquina_id: int,
    db: AsyncSession = Depends(models.get_async_no_context_session)
):
    maquina = await db.get(models.Maquina, maquina_id)
    if not maquina:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    resultado_sensores = await db.execute(
        select(models.Sensor)
        .filter(models.Sensor.maquina_id == maquina_id)
        .order_by(models.Sensor.fecha_hora.desc())
        .limit(10)
    )
    sensores = resultado_sensores.scalars().all()

    resultado_eventos = await db.execute(
        select(models.EventosCriticos)
        .join(models.Sensor)
        .filter(models.Sensor.maquina_id == maquina_id)
        .order_by(models.EventosCriticos.timestamp.desc())
        .limit(5)
    )
    eventos = resultado_eventos.scalars().all()

    return {
        "maquina": maquina.nombre,
        "ultimo_estado": [
            {
                "sensor": sensor.nombre,
                "tipo": sensor.tipo_sensor.tipo,
                "valor": sensor.valor,
                "fecha": sensor.fecha_hora.isoformat()
            } for sensor in sensores
        ],
        "eventos_recientes": [
            {
                "id": evento.id,
                "descripcion": evento.description,
                "fecha": evento.timestamp.isoformat()
            } for evento in eventos
        ]
    }
