from fastapi_mqtt import FastMQTT, MQTTConfig
from .models import SessionLocal, Maquina, Sensor
from sqlalchemy.orm import Session
import json

# MQTT Configuration
mqtt_config = MQTTConfig(host="localhost", port=1883)
mqtt = FastMQTT(config=mqtt_config)

def db_session():
    """Yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@mqtt.on_connect()
def connect(client, flags, rc, properties):
    # Subscribe to a pattern
    client.subscribe("maquinas/estacion_2/#")
    
@mqtt.on_message()
def handle_message(client, topic, payload, qos, properties):
    print(f"Received message on {topic}: {payload.decode()}")
    process_message(topic, payload.decode())

def process_message(topic, message):
    # Example topic: machines/machine1/sensor
    parts = topic.split('/')
    machine_name = parts[1]
    sensor_data = json.loads(message)  # Assuming JSON payload
    print(machine_name,sensor_data)
    with db_session() as db:
        machine = db.query(Maquina).filter(Maquina.nombre == machine_name).first()
        if machine:
            print('found on db'+machine)
        else:
            print('not found' + machine_name)