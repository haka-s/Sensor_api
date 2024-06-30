Descripción General de la API
-----------------------------

La API desarrollada actúa como una interfaz esencial entre los sensores físicos y el sistema de frontend, permitiendo la monitorización y análisis en tiempo real de los datos recolectados por diversos sensores. Esta API facilita la captura, el almacenamiento, y el acceso seguro a la información, proporcionando una plataforma robusta para la toma de decisiones y análisis avanzados.

### Funcionalidades Principales

1.  Captura de Datos en Tiempo Real:

    -   Los sensores envían datos a la API en intervalos regulares.
    -   La API procesa y almacena estos datos en una base de datos para su acceso y análisis posterior.
2.  Autenticación y Seguridad:

    -   La API utiliza tokens JWT para asegurar el acceso a la información.
    -   Solo los usuarios autenticados pueden insertar o acceder a los datos de los sensores.
3.  Análisis de Datos:

    -   La API permite consultas complejas para analizar los datos almacenados.
    -   Los usuarios pueden solicitar agregaciones de datos, tendencias históricas y alertas en tiempo real.
4.  Interfaz de Usuario:

    -   A través de un frontend conectado a la API, los usuarios pueden visualizar los datos en formas gráficas.
    -   Se proporcionan dashboards para una visualización intuitiva del estado actual y las métricas históricas.

### Flujo de Datos

1.  Recepción: Los datos son enviados por los sensores directamente a la API en formatos predefinidos.
2.  Procesamiento y Almacenamiento: La API procesa los datos recibidos para validar su formato y exactitud antes de almacenarlos en la base de datos.
3.  Acceso y Visualización: Los usuarios acceden al sistema a través de un frontend, donde pueden consultar, visualizar y analizar los datos.
4.  Análisis en Tiempo Real: Se utilizan algoritmos para analizar los datos en tiempo real y generar alertas basadas en parámetros específicos.

### Seguridad

-   La seguridad de la API se refuerza mediante el uso de HTTPS para todas las comunicaciones.
-   Los tokens JWT proporcionan un método seguro y eficiente para la autenticación de usuarios y dispositivos.

## Set Up
> [!NOTE]
> Debes tener docker instalado y corriendo
-   `git clone https://github.com/haka-s/Sensor_api`
-   `touch .env`
> [!IMPORTANT]
> es recomendable generar la key con el siguiente comando : `python -c 'import secrets; print(secrets.token_urlsafe(26))'`

> [!IMPORTANT]
> para generar un certificado self signed para testing utiliza `openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout certs/privkey.pem -out certs/fullchain.pem -config localhost.cnf`
> de otro modo puedes utilizar let's encrypt para generar automáticamente un certificado
> en windows se puede convertir el certificado para poder importarlo a la entidad de certificación de confianza `openssl x509 -outform der -in certs/fullchain.pem -out localhost.cer`

-   dentro del archivo .env
    ```
    DB_USER=""
    DB_PASSWORD=""
    DB_NAME=""
    KEY=""
    HOST_IP=""
    USE_MAIL=False
    MAIL_USERNAME=
    MAIL_PASSWORD=
    MAIL_FROM= 
    MAIL_SERVER=smtp.google.com
    MAIL_STARTTLS=True
    MAIL_SSL_TLS=True
    ```
-   `docker-compose --env-file .env up --build`


### Tecnologías Utilizadas

-   FastAPI 🚪
-   SQLAlchemy 📟
-   JWT 🔐
-   PostgreSQL 🔑
-   Docker 🐳
-   Asyncio MQTT 📢
-   Mosquitto 🌐

## Project Todo List

For a complete list of tasks and enhancements planned for this project, see the [Todo List](ToDo.md).