# Sistema CV

Aplicación mínima que muestra `Hola, mundo!` en la ruta principal.

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
