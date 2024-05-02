import requests

base_url = "http://localhost:8000" 

def create_sensor_types():
    sensor_types = [
        {"nombre": "Sensor de Encendido/Apagado de Motor (Externo)", "unidad": "binario"},
        {"nombre": "Sensor de Encendido/Apagado de Motor (Interno)", "unidad": "binario"},
        {"nombre": "Sensor de Medición de Corriente", "unidad": "amperes"},
        {"nombre": "Caudalímetro", "unidad": "litros por minuto"},
        {"nombre": "Sensor de Medición de Distancia", "unidad": "metros"},
        {"nombre": "Sensor de Detección de Actividad", "unidad": "binario"}
    ]
    for sensor_type in sensor_types:
        response = requests.post(f"{base_url}/tipo-sensor/", json=sensor_type)
        print(f"Tipo de sensor creado {sensor_type['nombre']}: Estado {response.status_code}")

def create_machine():
    machine_data = {"nombre": "estacion_2"}
    response = requests.post(f"{base_url}/maquinas/", json=machine_data)
    if response.status_code == 200:
        machine_id = response.json()['id']
        print(f"Máquina 'Estacion 2' creada con ID {machine_id}")
        return machine_id
    else:
        print("Falló la creación de la máquina")
        return None

def create_sensors(machine_id):

    sensor_creations = [
        {"tipo_sensor_id": 1, "maquina_id": machine_id, "estado": False, "valor": 0.0},  # Sensor de Encendido/Apagado de Motor (Externo)
        {"tipo_sensor_id": 2, "maquina_id": machine_id, "estado": False, "valor": 0.0},  # Sensor de Encendido/Apagado de Motor (Interno)
        {"tipo_sensor_id": 3, "maquina_id": machine_id, "estado": False, "valor": 0.0},  # Sensor de Medición de Corriente
        {"tipo_sensor_id": 4, "maquina_id": machine_id, "estado": False, "valor": 0.0},  # Caudalímetro
        {"tipo_sensor_id": 5, "maquina_id": machine_id, "estado": False, "valor": 0.0},  # Sensor de Medición de Distancia
        {"tipo_sensor_id": 6, "maquina_id": machine_id, "estado": False, "valor": 0.0}   # Sensor de Detección de Actividad
    ]
    for sensor in sensor_creations:
        response = requests.post(f"{base_url}/sensores/", json=sensor)
        print(f"Sensor agregado con ID de tipo {sensor['tipo_sensor_id']} a la máquina {machine_id}: Estado {response.status_code}")

create_sensor_types()
machine_id = create_machine()
if machine_id:
    create_sensors(machine_id)