import random
import time
import paho.mqtt.client as mqtt
import os
import math

MQTT_BROKER = 'localhost'
MQTT_PORT = 1883
MQTT_TOPICS = {
    "motor_externo": "maquinas/estacion_2/boolean/motor_externo",
    "motor_interno": "maquinas/estacion_2/boolean/motor_interno",
    "energia": "maquinas/estacion_2/energia/torcha",
    "caudalimetro": "maquinas/estacion_2/volumen/caudalimetro",
    "distancia": "maquinas/estacion_2/distancia/encoder",
    "actividad": "maquinas/estacion_2/boolean/actividad"
}

# Configuración de simulación
NORMAL_MODE = 0
FAILURE_MODE = 1
MAINTENANCE_MODE = 2

class SensorSimulator:
    def __init__(self):
        self.mode = NORMAL_MODE
        self.time = 0
        self.motor_external_status = False
        self.motor_internal_status = False
        self.energy_trend = 50
        self.flow_rate_trend = 50
        self.distance_trend = 50

    def update(self):
        self.time += 1
        if random.random() < 0.01:  # 1% de probabilidad de cambiar de modo
            self.mode = random.choice([NORMAL_MODE, FAILURE_MODE, MAINTENANCE_MODE])

    def get_motor_external_status(self):
        if self.mode == MAINTENANCE_MODE:
            return False
        elif self.mode == FAILURE_MODE:
            return random.random() < 0.2  # 20% de probabilidad de estar encendido en modo de falla
        else:
            if random.random() < 0.1:  # 10% de probabilidad de cambiar de estado
                self.motor_external_status = not self.motor_external_status
            return self.motor_external_status

    def get_motor_internal_status(self):
        if self.mode == MAINTENANCE_MODE:
            return False
        elif self.mode == FAILURE_MODE:
            return random.random() < 0.2  # 20% de probabilidad de estar encendido en modo de falla
        else:
            if random.random() < 0.1:  # 10% de probabilidad de cambiar de estado
                self.motor_internal_status = not self.motor_internal_status
            return self.motor_internal_status

    def get_energy(self):
        if self.mode == MAINTENANCE_MODE:
            return random.uniform(0, 10)
        elif self.mode == FAILURE_MODE:
            return random.uniform(80, 120)
        else:
            self.energy_trend += random.uniform(-5, 5)
            self.energy_trend = max(0, min(100, self.energy_trend))
            return self.energy_trend + random.uniform(-2, 2)

    def get_flow_rate(self):
        if self.mode == MAINTENANCE_MODE:
            return random.uniform(0, 5)
        elif self.mode == FAILURE_MODE:
            return random.uniform(90, 110)
        else:
            self.flow_rate_trend += random.uniform(-2, 2)
            self.flow_rate_trend = max(0, min(100, self.flow_rate_trend))
            return self.flow_rate_trend + random.uniform(-1, 1)

    def get_distance(self):
        if self.mode == MAINTENANCE_MODE:
            return random.uniform(0, 1)
        elif self.mode == FAILURE_MODE:
            return random.uniform(95, 105)
        else:
            self.distance_trend += random.uniform(-1, 1)
            self.distance_trend = max(0, min(100, self.distance_trend))
            return self.distance_trend + 10 * math.sin(self.time / 10)  # Añade una oscilación sinusoidal

    def get_activity(self):
        if self.mode == MAINTENANCE_MODE:
            return False
        elif self.mode == FAILURE_MODE:
            return random.random() < 0.5  # 50% de probabilidad de actividad en modo de falla
        else:
            return random.random() < 0.8  # 80% de probabilidad de actividad en modo normal

def connect_mqtt():
    client = mqtt.Client(client_id="SimulatedSensors", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    return client

def publish(client):
    simulator = SensorSimulator()
    while True:
        simulator.update()

        # Simulate Motor On/Off Sensor (External)
        motor_external_status = simulator.get_motor_external_status()
        client.publish(MQTT_TOPICS["motor_externo"], str(motor_external_status))
        
        # Simulate Motor On/Off Sensor (Internal)
        motor_internal_status = simulator.get_motor_internal_status()
        client.publish(MQTT_TOPICS["motor_interno"], str(motor_internal_status))
        
        # Simulate Current Measurement Sensor
        current_value = simulator.get_energy()
        client.publish(MQTT_TOPICS["energia"], f"{current_value:.2f}")
        
        # Simulate Flow Rate Sensor
        flow_rate = simulator.get_flow_rate()
        client.publish(MQTT_TOPICS["caudalimetro"], f"{flow_rate:.2f}")
        
        # Simulate Distance Measurement Sensor
        distance = simulator.get_distance()
        client.publish(MQTT_TOPICS["distancia"], f"{distance:.2f}")
        
        # Simulate Activity Detection Sensor
        activity_status = simulator.get_activity()
        client.publish(MQTT_TOPICS["actividad"], str(activity_status))

        print(f"Data sent to all topics. Mode: {simulator.mode}")
        time.sleep(1)  # Send a message every second for all sensors

if __name__ == "__main__":
    mqtt_client = connect_mqtt()
    publish(mqtt_client)