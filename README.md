# Sistema CV

Sistema de reclutamiento para gestionar plazas, perfiles profesionales,
postulaciones, entrevistas y análisis de currículums.

El proyecto usa Python 3.11.9. La versión queda fijada para desarrollo en
`.python-version`, para Render en `runtime.txt` y para Docker en el `Dockerfile`.

## Ejecutar localmente

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py runserver
```

Abre <http://127.0.0.1:8000/> en el navegador.

## Autenticacion

El acceso usa la tabla `usuarios`, hashes de contrasena de Django, sesiones
firmadas y los roles existentes en `usuarios_roles`. Para crear la primera
cuenta ejecuta el comando sin `--password`; este la solicita de forma oculta y
evita guardarla en el historial del terminal:

```powershell
python manage.py crear_usuario admin@empresa.com `
  --nombres "Nombre" `
  --apellidos "Apellido" `
  --rol ADMINISTRADOR
```

Los roles permitidos son `ADMINISTRADOR`, `RRHH` y `ASPIRANTE`. El estado de
este y los siguientes modulos se mantiene en [`BACKEND_CHECKLIST.txt`](BACKEND_CHECKLIST.txt).

## Catalogos de plazas

Antes de crear la primera plaza, inicializa los catalogos base. El comando es
idempotente y puede ejecutarse nuevamente sin duplicar registros:

```powershell
python manage.py inicializar_catalogos
```

En PostgreSQL, las tablas y catálogos de notificaciones se aplican con el
script idempotente `database/migracion_notificaciones.sql`:

```powershell
psql $env:DATABASE_URL -f database/migracion_notificaciones.sql
```

Para una base vacía, el instalador versionado ejecuta primero `schema.sql`,
después `migracion_espanol.sql` y finalmente las migraciones incrementales:

```powershell
python manage.py migrate --noinput
python manage.py aplicar_migraciones --instalar-esquema --inicializar-catalogos
```

La gestion de plazas permite crear borradores, editar requisitos, publicar,
pausar, reactivar y cerrar procesos conservando su historial de estados.

## Perfil y postulaciones

El portal del aspirante permite completar información personal y profesional,
registrar experiencia, formación, habilidades, idiomas y certificaciones. Las
plazas publicadas vigentes se muestran en una bolsa de empleo y cada
postulación conserva su estado e historial. Recursos Humanos puede avanzar el
proceso y programar entrevistas.

Los currículums se validan como PDF y se identifican con SHA-256. Durante el
desarrollo se guardan en un directorio privado local. Configura
`PRIVATE_UPLOAD_ROOT` para elegir su ubicación. En producción se pueden guardar
en un bucket privado de Backblaze B2 mediante su API compatible con S3.
Antes de usar estos módulos ejecuta:

```powershell
python manage.py inicializar_catalogos
```

Para activar Backblaze en producción configura `BACKBLAZE_ENABLED=True`, las
credenciales de la aplicación, el nombre del bucket, su endpoint regional y
`BACKBLAZE_PRESIGNED_URL_EXPIRY`. Las descargas se entregan mediante URLs
firmadas y temporales; las credenciales nunca se guardan en PostgreSQL.

Cuando `BACKBLAZE_ENABLED=False`, `save_curriculum` guarda el PDF bajo
`PRIVATE_UPLOAD_ROOT/curriculos` y `curriculum_path` valida la ruta antes de
servirlo. En Render el sistema de archivos local es efímero; para conservar
currículos con Backblaze desactivado debes montar un Persistent Disk y definir
`PRIVATE_UPLOAD_ROOT` en su ruta montada. Sin ese disco, activa Backblaze para
evitar perder archivos durante un redeploy.

### Análisis inteligente

Recursos Humanos puede abrir una postulación y ejecutar el análisis de su CV.
El sistema extrae el texto con `pypdf`, usa OCR opcional para documentos
escaneados y envía únicamente el texto a la API de Groq. La respuesta se exige
en JSON, se valida y se guarda en las tablas
`analisis_cv`, `evaluaciones_postulacion` y `resultados_requisitos_evaluacion`.

Configura estas variables sin subir `.env` al repositorio:

```text
GROQ_API_KEY=...
GROQ_API_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_TIMEOUT_SECONDS=90
GROQ_MAX_TOKENS=2500
ANALYSIS_MAX_TEXT_CHARS=16000
ANALYSIS_OCR_ENABLED=True
ANALYSIS_OCR_MAX_PAGES=5
ANALYSIS_OCR_DPI=150
TESSERACT_CMD=
TESSERACT_LANG=spa+eng
```

El cálculo de compatibilidad es reproducible y usa el peso de cada requisito;
la IA aporta la extracción y la evidencia, pero el resultado no sustituye la
revisión humana.

#### Entorno OCR

`pytesseract` es el adaptador de Python; el ejecutable Tesseract y sus datos de
idioma se instalan aparte. La imagen definida en `Dockerfile` instala y valida
`tesseract-ocr-eng` y `tesseract-ocr-spa`, y usa `spa+eng` por defecto.

Para una instalación nativa basada en Debian o Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-spa
tesseract --list-langs
```

El resultado debe incluir `eng` y `spa`. En Windows instala Tesseract con los
datos de ambos idiomas y define `TESSERACT_CMD` con la ruta de
`tesseract.exe`; conserva `TESSERACT_LANG=spa+eng`.

### Procesamiento en segundo plano

Los análisis se preparan en una transacción y se envían a la cola `analysis` de
Celery. Los estados `PENDIENTE`, `PROCESANDO`, `COMPLETADO` y `FALLIDO` se
guardan en las tablas existentes, por lo que no se requiere una migración de
Django. La interfaz consulta el estado automáticamente mientras el trabajador
procesa el currículum.

Para ejecutar el trabajador localmente necesitas Redis. Por ejemplo, con
Docker:

```powershell
docker run --name nexo-redis -p 6379:6379 -d redis:7-alpine
$env:REDIS_URL="redis://127.0.0.1:6379/0"
$env:ANALYSIS_ASYNC_ENABLED="True"
celery -A config worker --loglevel=INFO --pool=solo --queues=analysis
```

En Render configura `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` con la URL
privada de Redis y define `ANALYSIS_ASYNC_ENABLED=True`. Crea un trabajador
Background Worker para este repositorio con el comando:

```text
celery -A config worker --loglevel=INFO --queues=analysis
```

Render requiere un plan de cómputo de pago para mantener un Background Worker;
la instancia web `free` actual conserva el respaldo síncrono hasta que se
configure ese trabajador y una instancia Redis.

Los fallos temporales de Groq (límites, timeouts y respuestas 5xx) se reintentan
hasta tres veces con espera incremental. Si Celery no está habilitado, el
servidor usa un respaldo síncrono local; si la cola no está disponible, el
análisis queda como `FALLIDO` y Recursos Humanos puede pulsar `Reintentar
análisis` sin crear duplicados.

### API REST

La API versionada está disponible bajo `/api/v1/` y usa autenticación de sesión
de Django. Las plazas publicadas pueden consultarse sin iniciar sesión; los
perfiles y postulaciones se filtran según el rol del usuario. Un aspirante puede
crear una postulación y consultar sus propios datos, mientras que RRHH y
Administración pueden consultar el proceso completo, cambiar estados y poner
análisis en cola.

Operaciones principales:

- `GET /api/v1/plazas/`: plazas publicadas, con `q`, `estado`, `departamento`,
  `ciudad`, `modalidad`, `tipo_empleo`, `abierta` y `ordering`.
- `GET /api/v1/aspirantes/`: perfiles visibles para RRHH o el propio aspirante.
- `GET|POST /api/v1/postulaciones/`: listar o crear postulaciones.
- `POST /api/v1/postulaciones/{id}/estado/`: solicitar un cambio de estado.
- `GET|POST /api/v1/postulaciones/{id}/analisis/`: consultar o iniciar un análisis.
- `GET /api/v1/catalogos/{catalogo}/`: catálogos usados por filtros y formularios.

Las listas usan `page` y `page_size` (máximo 100). La especificación OpenAPI y
las interfaces de consulta están disponibles en `/api/v1/schema/`,
`/api/v1/docs/` y `/api/v1/redoc/`.

### Notificaciones

Las postulaciones generan una confirmación, los cambios de estado generan una
actualización y al programar una entrevista se crea una invitación. Cada evento
se guarda como notificación interna y se registra su entrega por aplicación y
por correo en `entregas_notificacion`; los intentos y errores quedan en
`intentos_entrega_notificacion`.

El correo usa el backend configurable mediante `EMAIL_BACKEND`, `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_TIMEOUT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL`. Los mensajes incluyen versiones
HTML y texto plano. Las notificaciones se consultan en `/notificaciones/` y
pueden marcarse individualmente o todas a la vez como leídas.

Configuración de ejemplo para el entorno de producción:

```text
BACKBLAZE_ENABLED=True
BACKBLAZE_APPLICATION_KEY_ID=...
BACKBLAZE_APPLICATION_KEY=...
BACKBLAZE_BUCKET_NAME=sistema-cv-curriculos-privados
BACKBLAZE_ENDPOINT_URL=https://s3.REGION.backblazeb2.com
BACKBLAZE_OBJECT_PREFIX=curriculos
BACKBLAZE_PRESIGNED_URL_EXPIRY=300
```

## Pruebas

```powershell
$env:OMITIR_DOTENV="True"
python manage.py test
```

## Base de datos

El modelo PostgreSQL normalizado hasta tercera forma normal se documenta en
[`docs/database-design.md`](docs/database-design.md). El DDL de referencia esta
en [`database/schema.sql`](database/schema.sql) y su reversion en
[`database/rollback.sql`](database/rollback.sql).

El esquema desplegado en Neon utiliza nombres de tablas, columnas, indices,
restricciones, secuencias y catalogos en espanol. La transformacion aplicada se
encuentra en [`database/migracion_espanol.sql`](database/migracion_espanol.sql).
Las migraciones posteriores se encuentran en
[`database/migraciones`](database/migraciones) y se aplican con
`python manage.py aplicar_migraciones`. El comando registra cada versión y su
SHA-256 en `esquema_migraciones`, impide modificar migraciones ya aplicadas y
usa un bloqueo advisory para evitar ejecuciones concurrentes.

### Conexion con Neon

1. Crea `.env` a partir de `.env.example`.
2. Asigna la cadena de conexion de Neon a `DATABASE_URL`.
3. Instala dependencias con `python -m pip install -r requirements.txt`.
4. Ejecuta `python manage.py migrate --noinput`.
5. Ejecuta `python manage.py aplicar_migraciones --instalar-esquema --inicializar-catalogos`.
6. Verifica la conexión con `python manage.py check --database default`.

Los modelos se encuentran en `reclutamiento/models.py`. Usan `managed = False`
para que Django no intente crear ni eliminar las tablas de negocio; su creación
y actualización se controla mediante el DDL de referencia y las migraciones
SQL versionadas.

## Despliegue en Render

- Python: `3.11.9`, mediante `runtime.txt` o `PYTHON_VERSION=3.11.9`.
- Build command: `python -m pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start command: `python manage.py migrate --noinput && python manage.py aplicar_migraciones --instalar-esquema --inicializar-catalogos && gunicorn config.wsgi:application`
- Worker command: `python manage.py migrate --noinput && python manage.py aplicar_migraciones --instalar-esquema --inicializar-catalogos && celery -A config worker --loglevel=INFO --queues=analysis`
- Variables: `DEBUG=False`, `SECRET_KEY` con un valor seguro y `DATABASE_URL`.

Para un servicio Render que utilice OCR, selecciona el runtime Docker para que
se construya con el `Dockerfile` del repositorio. Esa imagen instala Tesseract
y los idiomas `spa` y `eng` durante el build; el runtime nativo debe instalar
los mismos paquetes del sistema antes de iniciar la aplicación. El comando de
inicio del `Dockerfile` ejecuta las migraciones de Django, instala el esquema
de referencia si la base está vacía, aplica las versiones pendientes y carga
los catálogos antes de iniciar Gunicorn.

### Configurar Backblaze en Render

El script [`configurar_backblaze_render.ps1`](configurar_backblaze_render.ps1)
lee el `.env` local si existe, actualiza solamente las variables `BACKBLAZE_*`
del servicio configurado y solicita el despliegue. Las credenciales se
guardan protegidas por DPAPI en el perfil local de Windows, nunca en el
repositorio:

```powershell
powershell -ExecutionPolicy Bypass -File .\configurar_backblaze_render.ps1
```

El endpoint debe ser el endpoint S3 regional del bucket privado. Para cambiar
las credenciales guardadas ejecuta el script con `-ForgetLocalCredentials` y
vuelve a iniciarlo. Usa `-SkipDeploy` si solo quieres actualizar las variables.
