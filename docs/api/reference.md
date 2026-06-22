# API Reference

The Testomatic Register provides a REST API for integrating automated test equipment, programming jigs, and other external systems.

## Base URL

```
/api/v1/
```

For example: `https://portal.superhouse.tv/api/v1/`

## Interactive documentation

An interactive API explorer (Swagger UI) is available at `/api/v1/docs` for any installation. It requires a staff login to access. Use it to browse all endpoints and try requests directly in the browser.

## Authentication

Most endpoints require an API key sent in a request header:

```
X-API-Key: your-api-key-here
```

API keys are associated with Organisation records. Contact your administrator to obtain a key.

### IP restrictions

API requests are accepted only from:

- Localhost (`127.0.0.0/24`) — always allowed
- The subnet configured in `API_ALLOW_IPV4_SUBNET` (if set)

Requests from other IP addresses are rejected even with a valid key.

---

## Endpoints

### Designs

#### List designs

```http
GET /api/v1/designs/
```

Returns all designs accessible to the API key. Optionally filter by organisation:

```
GET /api/v1/designs/?client_pk=1
```

**Response:**
```json
[
  {
    "id": 1,
    "sku": "ABC123",
    "name": "Example Board",
    "hw_version": "1.0",
    "client": {"id": 1, "company_name": "Example Co"}
  }
]
```

---

### Devices (Boards)

#### Create or update a device

```http
POST /api/v1/device/add/
Content-Type: application/json
X-API-Key: your-key
```

Creates a new board or updates an existing one (matched by `pk`).

**Request body:**
```json
{
  "pk": 12345,
  "design_pk": 1,
  "creation_dt": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `pk` | integer | Yes | Board serial number |
| `design_pk` | integer | Yes | Design to associate with this board |
| `creation_dt` | datetime (ISO 8601) | No | Defaults to current time if omitted |

**Response codes:** `201` Created, `200` Updated, `400` Invalid request.

---

#### Get a device

```http
GET /api/v1/device/{pk}/
X-API-Key: your-key
```

Returns basic details for a board.

**Response:**
```json
{
  "design_pk": 1,
  "creation_dt": "2024-01-15T10:30:00Z"
}
```

---

#### Record a firmware programming event

```http
POST /api/v1/device/{pk}/program/
Content-Type: application/json
X-API-Key: your-key
```

```json
{"sw_version": "2.1.0"}
```

Records a `SW_VERSION` DeviceEvent against the board.

---

#### Add a test record

```http
POST /api/v1/device/{pk}/add-tr/
Content-Type: application/json
X-API-Key: your-key
```

```json
{
  "result": "PASS",
  "test_dt": "2024-01-15T14:30:00Z",
  "notes": "All tests passed"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `result` | string | Yes | One of `NEW`, `PASS`, `FAIL`, `HUH?` |
| `test_dt` | datetime | No | Defaults to current time |
| `notes` | string | No | Additional notes |

**Response:** `{"pk": 42}` — the test record primary key, used to attach images.

---

#### Upload a test image

```http
POST /api/v1/device/{testrecord_pk}/add-image/
Content-Type: multipart/form-data
X-API-Key: your-key
```

Attach a photo to a test record. Send the image as a form field named `file`.

**Response:** `{"thumbnail": "/media/test_images/12345/image.jpg"}`

---

#### Upload a device image

```http
POST /api/v1/device/{pk}/add-device-image/
Content-Type: multipart/form-data
X-API-Key: your-key
```

Attach a photo directly to a board (not tied to a test record). Send the image as a form field named `file`. An optional `notes` form field can also be included.

The API key must belong to the client associated with the board's design.

If the filename matches the pattern `{pk}-YYYY-MM-DD_H-M-S.ext`, the datetime is extracted and used as the image timestamp.

---

### Dashboard statistics

```http
GET /api/v1/dashboard-stats/
```

Returns summary counts and chart data. Accepts either API key auth or a Django session cookie (used by the dashboard's browser-based polling).

---

## Complete workflow example

```bash
BASE=https://portal.superhouse.tv/api/v1
KEY=your-api-key

# 1. Check available designs
curl -H "X-API-Key: $KEY" $BASE/designs/

# 2. Register a new board
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"pk": 12345, "design_pk": 1}' $BASE/device/add/

# 3. Program with a firmware version
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"sw_version": "2.1.0"}' $BASE/device/12345/program/

# 4. Record a test result
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"result": "PASS", "notes": "All tests passed"}' \
  $BASE/device/12345/add-tr/

# 5. Upload a test image (test record pk returned in step 4)
curl -X POST -H "X-API-Key: $KEY" \
  -F "file=@test_image.jpg" $BASE/device/42/add-image/
```

## Error responses

All errors return JSON with a `message` field:

```json
{"message": "Design not found"}
```

Standard HTTP status codes are used: `200` OK, `201` Created, `400` Bad Request, `401` Unauthorized, `403` Forbidden, `404` Not Found.

## Date/time format

All datetime fields use ISO 8601 with timezone:

```
2024-01-15T10:30:00Z
2024-01-15T10:30:00+10:00
```
