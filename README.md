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

## Pruebas

```powershell
python manage.py test
```

## Despliegue en Render

- Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- Start command: `gunicorn config.wsgi:application`
- Variables: `DEBUG=False` y `SECRET_KEY` con un valor seguro
