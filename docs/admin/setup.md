# Development Setup

This guide walks through running the Testomatic Register locally for development.

## Prerequisites

- Python 3.12 (required to match the production uWSGI build; check with `python3 --version`)
- Git

## Step 1: Clone the repository

```bash
git clone https://github.com/SuperHouse/register.git
cd register
```

## Step 2: Create a virtual environment

```bash
cd pyproj
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt. Keep the virtual environment activated for all subsequent steps.

## Step 3: Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 4: Create the local settings file

```bash
cp conf/local_settings.py.template conf/local_settings.py
```

Edit `conf/local_settings.py`. For local development, the SQLite configuration is the simplest option — remove or comment out the MySQL section.

## Step 5: Create the environment file

Create `pyproj/.env` from the template:

```bash
cp .env.template .env
```

At minimum, set a `SECRET_KEY`. Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

A minimal `.env` for development:

```env
SECRET_KEY=<paste generated key here>
DEPLOY_TYPE=dev
DEMO_MODE=False
API_ALLOW_IPV4_SUBNET=
```

See [Configuration Reference](configuration.md) for all available variables.

## Step 6: Run database migrations

```bash
python manage.py migrate
```

## Step 7: Create a superuser account

```bash
python manage.py createsuperuser
```

This account is used to log in to both the main application and the admin interface at `/office/`.

## Step 8: Start the development server

```bash
python manage.py runserver
```

The server starts at `http://127.0.0.1:8000/`.

| URL | Description |
|---|---|
| `http://127.0.0.1:8000/` | Dashboard |
| `http://127.0.0.1:8000/device/` | Boards |
| `http://127.0.0.1:8000/design/` | Designs |
| `http://127.0.0.1:8000/organisation/` | Organisations |
| `http://127.0.0.1:8000/office/` | Admin interface |
| `http://127.0.0.1:8000/api/v1/docs` | Interactive API docs (staff login required) |

## Troubleshooting

**Import errors** — make sure the virtual environment is activated (`source venv/bin/activate`) and all dependencies are installed (`pip install -r requirements.txt`).

**Database errors** — check that `conf/local_settings.py` exists and that migrations have been applied (`python manage.py migrate`).

**Static files not loading** — in development, Django serves static files automatically when `DEBUG = True` in `local_settings.py`.
