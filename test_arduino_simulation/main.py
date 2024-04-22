import random
import time
import paho.mqtt.client as mqtt

# MQTT Settings
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = {
    "motor_externo": "sensor/motor_externo",
    "motor_interno": "sensor/motor_interno",
    "energia": "sensor/energia",
    "caudalimetro": "sensor/caudalimetro",
    "distnacia": "sensor/distancia",
    "actividad": "sensor/actividad"
}

def connect_mqtt():
    client = mqtt.Client(client_id="SimulatedSensors", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    return client

def publish(client):
    while True:
        # Simulate Motor On/Off Sensor (External)
        motor_external_status = random.choice([True, False])
        client.publish(MQTT_TOPICS["motor_externo"], str(motor_external_status))
        
        # Simulate Motor On/Off Sensor (Internal)
        motor_internal_status = random.choice([True, False])
        client.publish(MQTT_TOPICS["motor_interno"], str(motor_internal_status))
        
        # Simulate Current Measurement Sensor
        current_value = random.uniform(0, 100)  # Simulates current in amperes
        client.publish(MQTT_TOPICS["energia"], f"{current_value:.2f}")
        
        # Simulate Flow Rate Sensor
        flow_rate = random.uniform(0, 100)  # Simulates flow rate in liters per minute
        client.publish(MQTT_TOPICS["caudalimetro"], f"{flow_rate:.2f}")
        
        # Simulate Distance Measurement Sensor
        distance = random.uniform(0, 100)  # Simulates distance in meters
        client.publish(MQTT_TOPICS["distnacia"], f"{distance:.2f}")
        
        # Simulate Activity Detection Sensor
        activity_status = random.choice([True, False])
        client.publish(MQTT_TOPICS["actividad"], str(activity_status))

        print("Data sent to all topics")
        time.sleep(5)  # Send a message every 5 seconds for all sensors

if __name__ == "__main__":
    mqtt_client = connect_mqtt()
    publish(mqtt_client)