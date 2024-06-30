#include <SPI.h>
#include <Ethernet.h>
#include <PubSubClient.h>
// Para TLS, descomenta la siguiente línea:
// #include <WiFiClientSecure.h>

// Configuración de Ethernet
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress ip(192, 168, 1, 177); // Establece una IP estática si es necesario, o usa DHCP
IPAddress server(192, 168, 1, 100); // IP del broker MQTT

// Configuración MQTT
const char* mqtt_topic_publish = "maquinas/estacion_2/datos";
// Para autenticación por contraseña, descomenta y configura estas líneas:
// const char* mqtt_username = "tu_usuario";
// const char* mqtt_password = "tu_contraseña";

// Definición de pines
const int PIN_MOTOR_EXTERNO = 22;
const int PIN_MOTOR_INTERNO = 24;
const int CURRENT_SENSOR = A0;
const int ENCODER_PIN_A = 2;
const int ENCODER_PIN_B = 3;

// Variables para las lecturas de los sensores
volatile long encoderValue = 0;
int currentValue = 0;
bool motorExternoState = false;
bool motorInternoState = false;

EthernetClient ethClient;
// Para TLS, comenta la línea anterior y descomenta la siguiente:
// WiFiClientSecure ethClient;
PubSubClient client(ethClient);

void setup() {
  Serial.begin(115200);
  
  // Inicializar conexión Ethernet
  Ethernet.begin(mac, ip);
  delay(1500); // Dar tiempo al shield Ethernet para inicializarse
  
  Serial.println("Ethernet conectado");
  Serial.print("Dirección IP: ");
  Serial.println(Ethernet.localIP());
  
  // Configurar modos de los pines
  pinMode(PIN_MOTOR_EXTERNO, INPUT);
  pinMode(PIN_MOTOR_INTERNO, INPUT);
  pinMode(CURRENT_SENSOR, INPUT);
  pinMode(ENCODER_PIN_A, INPUT_PULLUP);
  pinMode(ENCODER_PIN_B, INPUT_PULLUP);
  
  // Adjuntar interrupción para el encoder
  attachInterrupt(digitalPinToInterrupt(ENCODER_PIN_A), updateEncoder, CHANGE);
  
  // Configurar cliente MQTT
  client.setServer(server, 1883);  // Puerto MQTT estándar
  // Para TLS, usa el puerto 8883 en su lugar:
  // client.setServer(server, 8883);
  
  // Para TLS, necesitarías establecer el certificado SSL/TLS aquí
  // ethClient.setCACert(root_ca);  // Certificado de la CA raíz

  // Conectar al broker MQTT
  reconnect();
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  
  // Leer sensores
  motorExternoState = digitalRead(PIN_MOTOR_EXTERNO);
  motorInternoState = digitalRead(PIN_MOTOR_INTERNO);
  currentValue = analogRead(CURRENT_SENSOR);
  
  // Preparar carga útil JSON
  char payload[200];
  snprintf(payload, sizeof(payload), 
           "{\"motor_externo\": %s, \"motor_interno\": %s, \"corriente\": %d, \"encoder\": %ld}",
           motorExternoState ? "true" : "false",
           motorInternoState ? "true" : "false",
           currentValue,
           encoderValue);
  
  // Publicar datos
  client.publish(mqtt_topic_publish, payload);
  
  Serial.println("Datos publicados:");
  Serial.println(payload);
  
  delay(5000); // Publicar cada 5 segundos
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Intentando conexión MQTT...");
    // Si estás usando autenticación por usuario/contraseña, usa esto:
    // if (client.connect("ArduinoMegaClient", mqtt_username, mqtt_password)) {
    // Para sin autenticación:
    if (client.connect("ArduinoMegaClient")) {
      Serial.println("conectado");
    } else {
      Serial.print("falló, rc=");
      Serial.print(client.state());
      Serial.println(" intentar de nuevo en 5 segundos");
      delay(5000);
    }
  }
}

void updateEncoder() {
  int b = digitalRead(ENCODER_PIN_B);
  if (b > 0) {
    encoderValue++;
  } else {
    encoderValue--;
  }
}