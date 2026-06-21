# Administration

This section covers installing, configuring, and operating the Testomatic Register.

| Guide | Description |
|---|---|
| [Development Setup](setup.md) | Run the application locally for development |
| [Production Deployment](deployment.md) | Serve the application with uWSGI on Linux |
| [Configuration Reference](configuration.md) | All environment variables |
| [Supplier API Setup](supplier-apis.md) | Connect to LCSC, DigiKey, Mouser, and Element14 |
| [Data Export & Import](data.md) | Back up and restore all application data |

## Admin interface

The Django admin interface is available at `/office/` and requires a staff account. Use it to manage users, create superusers, and access any model directly.

## Running tests

```bash
cd pyproj
source venv/bin/activate
pytest
```
