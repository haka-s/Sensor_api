import paho.mqtt.client as mqtt
import threading
import json
import paho.mqtt.subscribe as subscribe
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPICS = {
    "motor_externo": "estacion_2/motor_externo",
    "motor_interno": "estacion_2/motor_interno",
    "energia": "estacion_2/energia",
    "caudalimetro": "estacion_2/caudalimetro",
    "distancia": "estacion_2/distancia",
    "actividad": "estacion_2/actividad"
}

def on_connect(client, userdata, flags, rc, properties):
    print("Connected with result code " + str(rc))
    # Subscribe to all topics here if connection was successful
    if rc == 0:
        for topic in MQTT_TOPICS.values():
            client.subscribe(topic)


def on_message(client, userdata, msg):
    print(f"Received '{msg.payload.decode()}' on topic '{msg.topic}'")
    # Here, you would handle the message

def start_mqtt():

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    client.loop_start()  # Starts the network loop in a non-blocking way

def stop_mqtt():
    client.loop_stop()  # Stop the network loop
    client.disconnect()  # Disconnect the client
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message