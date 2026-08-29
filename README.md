# Sistema CV

Sistema de reclutamiento para gestionar plazas, perfiles profesionales,
postulaciones, entrevistas y análisis de currículums.

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
revisión humana. El procesamiento actual es síncrono; Celery y Redis quedan
para el módulo de procesamiento en segundo plano.

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

### Conexion con Neon

1. Crea `.env` a partir de `.env.example`.
2. Asigna la cadena de conexion de Neon a `DATABASE_URL`.
3. Instala dependencias con `python -m pip install -r requirements.txt`.
4. Verifica la conexion con `python manage.py check --database default`.

Los modelos se encuentran en `reclutamiento/models.py`. Las tablas ya existen
en Neon, por lo que los modelos usan `managed = False` y Django no intenta
crearlas ni eliminarlas mediante migraciones.

## Despliegue en Render

- Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start command: `gunicorn config.wsgi:application`
- Variables: `DEBUG=False` y `SECRET_KEY` con un valor seguro

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
