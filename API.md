# API Documentation

## Overview

This API provides endpoints for managing devices, designs, clients, test records, and test images. The API uses API key authentication and IP-based access control for security.

## Base URL

All API endpoints are prefixed with:
```
/api/v1/
```

For example, if your server is running at `https://example.com`, the full URL would be:
```
https://example.com/api/v1/
```

## Authentication

The API uses API key authentication via HTTP headers. Most endpoints require authentication, with the exception of the test endpoint.

### Authentication Method

Include your API key in the request header:
```
X-API-Key: your-api-key-here
```

### IP Restrictions

For security, API requests are only accepted from:
- Localhost network: `127.0.0.0/24` (for local development)
- Configured subnet: As specified in `API_ALLOW_IPV4_SUBNET` setting (if configured)

Requests from other IP addresses will be rejected, even with a valid API key.

### Getting an API Key

API keys are associated with `Client` objects in the system. Contact your administrator to obtain an API key for your client account.

## Interactive API Documentation

An interactive API explorer is available at:
```
http://localhost:8000/api/v1/docs
```

Note: The documentation interface requires staff login, but does not require an API key to view.

## Endpoints

### Test Endpoints

#### Test Endpoint (No Authentication)
```http
GET /api/v1/test-endpoint-noauth/
```

**Description:** Simple test endpoint that doesn't require authentication.

**Response:**
```json
{
  "message": "Success."
}
```

#### Test Endpoint (With Authentication)
```http
GET /api/v1/test-endpoint/
```

**Description:** Simple test endpoint that requires authentication. Use this to verify your API key is working correctly.

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
{
  "message": "Success."
}
```

### Client Endpoints

#### List Clients
```http
GET /api/v1/clients/
```

**Description:** Retrieve a list of all clients in the system.

**Headers:**
- `X-API-Key`: Your API key (required)

**Response:**
```json
[
  {
    "id": 1,
    "company_name": "Example Company"
  },
  {
    "id": 2,
    "company_name": "Another Company"
  }
]
```

### Design Endpoints

#### List Designs
```http
GET /api/v1/designs/?client_pk={client_id}
```

**Description:** Retrieve a list of all designs. Optionally filter by client ID.

**Headers:**
- `X-API-Key`: Your API key (required)

**Query Parameters:**
- `client_pk` (optional): Filter designs by client primary key

**Response:**
```json
[
  {
    "id": 1,
    "sku": "ABC123",
    "client": {
      "id": 1,
      "company_name": "Example Company"
    },
    "name": "Product Name",
    "hw_version": "1.0",
    "description": "Product description"
  }
]
```

**Example:**
```bash
# Get all designs
curl -H "X-API-Key: your-key" https://example.com/api/v1/designs/

# Get designs for a specific client
curl -H "X-API-Key: your-key" https://example.com/api/v1/designs/?client_pk=1
```

### Device Endpoints

#### Add or Update Device
```http
POST /api/v1/device/add/
```

**Description:** Create a new device or update an existing device. If a device with the given primary key already exists, it will be updated; otherwise, a new device will be created.

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: `application/json`

**Request Body:**
```json
{
  "pk": 12345,
  "design_pk": 1,
  "creation_dt": "2024-01-15T10:30:00Z"
}
```

**Fields:**
- `pk` (integer, required): Device serial number/primary key
- `design_pk` (integer, required): Primary key of the design to associate with this device
- `creation_dt` (datetime, optional): Creation date/time in ISO 8601 format. If not provided, current timestamp is used.

**Response Codes:**
- `200`: Device was updated successfully
- `201`: Device was created successfully
- `400`: Invalid request (e.g., design not found)

**Response (200/201):**
```json
{
  "message": "Ok"
}
```

**Response (400):**
```json
{
  "message": "Design not found"
}
```

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"pk": 12345, "design_pk": 1, "creation_dt": "2024-01-15T10:30:00Z"}' \
  https://example.com/api/v1/device/add/
```

#### Get Device
```http
GET /api/v1/device/{device_pk}/
```

**Description:** Retrieve information about an existing device.

**Headers:**
- `X-API-Key`: Your API key (required)

**Path Parameters:**
- `device_pk`: Device primary key (serial number)

**Response:**
```json
{
  "design_pk": 1,
  "creation_dt": "2024-01-15T10:30:00Z"
}
```

**Response Codes:**
- `200`: Success
- `404`: Device not found

**Example:**
```bash
curl -H "X-API-Key: your-key" https://example.com/api/v1/device/12345/
```

#### Program Device
```http
POST /api/v1/device/{device_pk}/program/
```

**Description:** Record a software version programming event for a device.

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: `application/json`

**Path Parameters:**
- `device_pk`: Device primary key (serial number)

**Request Body:**
```json
{
  "sw_version": "2.1.0"
}
```

**Fields:**
- `sw_version` (string, required): Software version string

**Response:**
```json
{
  "message": "Ok"
}
```

**Response Codes:**
- `200`: Success
- `404`: Device not found

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"sw_version": "2.1.0"}' \
  https://example.com/api/v1/device/12345/program/
```

#### Add Test Record
```http
POST /api/v1/device/{device_pk}/add-tr/
```

**Description:** Add a test record for a device.

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: `application/json`

**Path Parameters:**
- `device_pk`: Device primary key (serial number)

**Request Body:**
```json
{
  "result": "PASS",
  "test_dt": "2024-01-15T14:30:00Z",
  "notes": "All tests passed successfully"
}
```

**Fields:**
- `result` (string, required): Test result. Must be one of: `"NEW"`, `"PASS"`, `"FAIL"`, `"HUH?"`
- `test_dt` (datetime, optional): Test date/time in ISO 8601 format. If not provided, current timestamp is used.
- `notes` (string, optional): Additional notes about the test

**Response (200):**
```json
{
  "pk": 42
}
```

**Response (400):**
```json
{
  "message": "Invalid value for result"
}
```

**Response Codes:**
- `200`: Test record created successfully
- `400`: Invalid request (e.g., invalid result value)
- `404`: Device not found

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"result": "PASS", "notes": "All tests passed"}' \
  https://example.com/api/v1/device/12345/add-tr/
```

### Test Image Endpoints

#### Add Test Image
```http
POST /api/v1/device/{testrecord_pk}/add-image/
```

**Description:** Upload an image associated with a test record.

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: `multipart/form-data`

**Path Parameters:**
- `testrecord_pk`: Test record primary key

**Request Body:**
- Form data with a file field containing the image

**Response:**
```json
{
  "thumbnail": "/media/test_images/12345/image.jpg"
}
```

**Response Codes:**
- `200`: Image uploaded successfully
- `404`: Test record not found

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@/path/to/image.jpg" \
  https://example.com/api/v1/device/42/add-image/
```

**Note:** This endpoint uses `multipart/form-data` content type, not `application/json`. The file must be sent as form data.

### Device Image Endpoints

#### Add Device Image
```http
POST /api/v1/device/{device_pk}/add-device-image/
```

**Description:** Upload an image directly associated with a device. This endpoint requires that the API key belongs to the client associated with the device's design. The image datetime can be automatically extracted from the filename if it matches the pattern `id-YYYY-MM-DD_h-m-s` (e.g., `123-2024-01-15_14-30-45`).

**Headers:**
- `X-API-Key`: Your API key (required)
- `Content-Type`: `multipart/form-data`

**Path Parameters:**
- `device_pk`: Device primary key (serial number)

**Request Body:**
- Form data with:
  - `file` (required): Image file to upload
  - `notes` (optional): Additional notes about the image

**Response (200):**
```json
{
  "image_url": "/media/device_images/12345/image.jpg",
  "pk": 42
}
```

**Response Codes:**
- `200`: Image uploaded successfully
- `403`: API key does not have access to this device, or invalid API key
- `404`: Device not found

**Example:**
```bash
# Upload image with notes
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@/path/to/image.jpg" \
  -F "notes=Device inspection photo" \
  https://example.com/api/v1/device/12345/add-device-image/

# Upload image without notes
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@/path/to/image.jpg" \
  https://example.com/api/v1/device/12345/add-device-image/

# Upload image with datetime in filename (e.g., "12345-2024-01-15_14-30-45.jpg")
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@12345-2024-01-15_14-30-45.jpg" \
  https://example.com/api/v1/device/12345/add-device-image/
```

**Note:** 
- This endpoint uses `multipart/form-data` content type, not `application/json`. The file must be sent as form data.
- The API key must belong to the client associated with the device's design. If the API key belongs to a different client, the request will be rejected with a 403 error.
- If the filename matches the pattern `id-YYYY-MM-DD_h-m-s`, the datetime will be extracted and used as the image timestamp. Otherwise, the current timestamp will be used.

## Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid API key
- `403 Forbidden`: IP address not allowed
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses typically include a message:
```json
{
  "message": "Error description"
}
```

## Date/Time Format

All datetime fields should be provided in ISO 8601 format with timezone information:
```
2024-01-15T10:30:00Z
2024-01-15T10:30:00+10:00
```

## Test Result Values

When creating test records, the `result` field must be one of these exact values:
- `"NEW"` - Test started
- `"PASS"` - Test passed
- `"FAIL"` - Test failed
- `"HUH?"` - Test inconclusive

## Examples

### Complete Workflow Example

Here's an example of a complete workflow to add a device, program it, and record test results:

```bash
# 1. Get available designs
curl -H "X-API-Key: your-key" https://example.com/api/v1/designs/

# 2. Create a new device
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"pk": 12345, "design_pk": 1}' \
  https://example.com/api/v1/device/add/

# 3. Program the device with software version
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"sw_version": "2.1.0"}' \
  https://example.com/api/v1/device/12345/program/

# 4. Record a test result
curl -X POST \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"result": "PASS", "notes": "All tests passed"}' \
  https://example.com/api/v1/device/12345/add-tr/

# 5. Upload a test image (assuming test record ID is 42)
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@test_image.jpg" \
  https://example.com/api/v1/device/42/add-image/

# 6. Upload a device image
curl -X POST \
  -H "X-API-Key: your-key" \
  -F "file=@device_image.jpg" \
  -F "notes=Device inspection" \
  https://example.com/api/v1/device/12345/add-device-image/
```

## Python Example

```python
import requests

API_BASE = "https://example.com/api/v1"
API_KEY = "your-api-key-here"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Get designs
response = requests.get(f"{API_BASE}/designs/", headers=headers)
designs = response.json()

# Create a device
device_data = {
    "pk": 12345,
    "design_pk": 1,
    "creation_dt": "2024-01-15T10:30:00Z"
}
response = requests.post(f"{API_BASE}/device/add/", headers=headers, json=device_data)
print(response.json())

# Program device
program_data = {"sw_version": "2.1.0"}
response = requests.post(
    f"{API_BASE}/device/12345/program/",
    headers=headers,
    json=program_data
)
print(response.json())

# Add test record
test_data = {
    "result": "PASS",
    "notes": "All tests passed"
}
response = requests.post(
    f"{API_BASE}/device/12345/add-tr/",
    headers=headers,
    json=test_data
)
test_record = response.json()
test_record_pk = test_record["pk"]

# Upload test image
with open("test_image.jpg", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"{API_BASE}/device/{test_record_pk}/add-image/",
        headers={"X-API-Key": API_KEY},
        files=files
    )
    print(response.json())

# Upload device image
with open("device_image.jpg", "rb") as f:
    files = {"file": f}
    data = {"notes": "Device inspection photo"}
    response = requests.post(
        f"{API_BASE}/device/12345/add-device-image/",
        headers={"X-API-Key": API_KEY},
        files=files,
        data=data
    )
    print(response.json())
```

## Support

For API support or to obtain an API key, please contact your system administrator.

