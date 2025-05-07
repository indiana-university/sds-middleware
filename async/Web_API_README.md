# SDS Middleware Web APIs

The SDS (Scholarly Data Share) middleware provides a set of web APIs for retrieving data from SDA (Scholarly Data Archive) storage. These APIs are implemented using the Tornado web framework.

## API Overview

There are two main endpoints:

1. **Synchronous API** - `/sds/get`: For immediate file download
2. **Asynchronous API** - `/sds/pull`: For queuing download requests

## Endpoint Details

### 1. Synchronous API (`SyncSDSFilePullHandler`)

**Endpoint:** `/{base_path}/sds/get`

**Method:** GET

**Parameters:**
- `p`: Path to the file in SDA storage

**Description:**
This endpoint retrieves a file directly from SDA storage and streams it to the client. It uses HSI (HPSS Secure Interface) commands to access the SDA storage.

**Process Flow:**
1. Receives a file path parameter
2. Creates a temporary directory for file transfer
3. Constructs and executes HSI command to pull the file from SDA
4. Streams the downloaded file to the client with appropriate headers
5. Cleans up temporary storage

**Example Usage:**
```
GET /sds/get?p=path/to/file.zip
```

**Response:**
- Success: File content with `Content-Type: application/octet-stream` and appropriate filename
- Error: HTTP 400 with error message

### 2. Asynchronous API (`AsyncSDSFilePullHandler`)

**Endpoint:** `/{base_path}/sds/pull`

**Method:** GET

**Parameters:**
- `p`: Path to the file in SDA storage
- `uid`: User email address for notification

**Description:**
This endpoint queues a download request into RabbitMQ for asynchronous processing. It records the job in a database and returns a confirmation to the user. When the job completes, the user will receive an email notification with a download link.

**Process Flow:**
1. Validates user is not in blacklist
2. Checks for duplicate requests within minimum interval
3. Generates a unique job ID
4. Enqueues the job to RabbitMQ
5. Records job details in database
6. Returns acknowledgment to user

**Example Usage:**
```
GET /sds/pull?p=path/to/file.zip&uid=user@example.com
```

**Response:**
- Success: JSON with acknowledgment message
  ```json
  {
    "Acknowledgement": "Your download request has been submitted. You will receive an email response to your request with a download link. Once your request has been processed, the download link will remain valid for 24 hours"
  }
  ```
- Blacklisted: JSON with warning message
- Duplicate Request: JSON with invalid request message
- Error: HTTP 400 with error message

## Implementation Notes

- Both handlers support only GET requests (POST method is defined but not implemented)
- The synchronous API is suitable for smaller files that can be downloaded quickly
- The asynchronous API is designed for large files where immediate download would be impractical
- The asynchronous system uses:
  - RabbitMQ for job queuing
  - MySQL database for job tracking
  - Email notifications for completion alerts
  - File caching to avoid redundant downloads

The API server can be configured using the `sds.cfg` configuration file, which controls parameters like HSI connectivity, database connections, and message broker settings.