# Testomatic Dashboard Setup Guide

This guide will help you set up the Testomatic Dashboard.

## Linux Production Setup

I think there's something called UWSGI managing the processes, but I can't see 
how it's set up.

## Linux Local Setup (dev)

Todo

## MacOS Local Setup (dev)

The instructions below are for local setup on MacOS.

### Prerequisites

- Python 3.8+ (check with `python3 --version`)
- pip (Python package manager)
- Git (if cloning the repository)

### Step 1: Navigate to the Project Directory

```bash
cd /Users/jon/src/register/pyproj
```

### Step 2: Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt. Keep this terminal open and 
the virtual environment activated for all subsequent steps.

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Create Local Settings File

Create `conf/local_settings.py` from the template:

```bash
cp conf/local_settings.py.template conf/local_settings.py
```

Then edit `conf/local_settings.py` and keep only the SQLite configuration 
(the first section, lines 1-28). Remove or comment out the MySQL section below.

### Step 5: Create Environment Variables File

Create a `.env` file in the `pyproj` directory:

```bash
cd /Users/jon/src/register/pyproj
touch .env
```

Add the following to `.env`:

```env
SECRET_KEY=your-secret-key-here-change-this-in-production
DEPLOY_TYPE=dev
DEMO_MODE=False
API_ALLOW_IPV4_SUBNET=
```

**Important:** Generate a secure SECRET_KEY. You can use this command:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it as the value for `SECRET_KEY` in your `.env` file.

### Step 6: Run Database Migrations

```bash
python manage.py migrate
```

This will create the SQLite database file (`db.sqlite3`) and set up all 
the database tables.

### Step 7: Create a Superuser Account

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account. You'll use this to log 
into the admin interface.

### Step 8: Run the Development Server

```bash
python manage.py runserver
```

The server will start at `http://127.0.0.1:8000/`

### Step 9: Access the Application

- **Main application**: http://127.0.0.1:8000/device/
- **Admin interface**: http://127.0.0.1:8000/office/
- **API documentation**: http://127.0.0.1:8000/api/v1/docs (requires staff login)

### Testing the Excel Import

To test the Excel import command you just modified:

1. Prepare an Excel file with the required sheets (see the import command for format)
2. Run the import command:

```bash
python manage.py import-xlsx /path/to/your/file.xlsx
```

### Running Tests

To run the test suite:

```bash
pytest
```

Or with Django's test runner:

```bash
python manage.py test
```

### Troubleshooting

#### Import Errors
If you get import errors, make sure:
- Your virtual environment is activated (`source venv/bin/activate`)
- All dependencies are installed (`pip install -r requirements.txt`)

#### Database Errors
If you get database errors:
- Make sure migrations are run: `python manage.py migrate`
- Check that `conf/local_settings.py` exists and has the correct database configuration

#### Static Files Not Loading
If static files (CSS, images) don't load:
- In development, Django serves static files automatically
- Make sure `DEBUG = True` in your `local_settings.py`

### Deactivating the Virtual Environment

When you're done working, you can deactivate the virtual environment:

```bash
deactivate
```

### Next Steps

- Create some test data through the admin interface
- Create clients, designs, and devices
- Test the Excel import functionality
- Explore the API endpoints

