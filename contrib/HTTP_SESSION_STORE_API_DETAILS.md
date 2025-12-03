# HTTP Session Store API - Detailed Specification

This document provides detailed information about the HTTP Session Store REST API, with a focus on the PUT request structure.

## PUT Request Structure (Save Session)

### Overview

The PUT request is used to save or update a session. OAuth2-proxy sends encrypted session data to your HTTP storage backend, where it should be stored with the specified TTL (Time To Live).

### Request Details

#### HTTP Method and URL
```
PUT {base_url}/sessions/{key}
```

**URL Components:**
- `{base_url}` - The base URL configured with `--http-store-base-url`
- `{key}` - The session ticket handle (URL-encoded)

**Key Format:** `{CookieName}-{ticketID}`
- Example: `_oauth2_proxy-a1b2c3d4e5f67890a1b2c3d4e5f67890`
- The `ticketID` is a 128-bit random number, hex-encoded (32 hex characters)
- The key is automatically URL-encoded, so special characters are escaped

#### Request Headers

```http
Content-Type: application/json
Authorization: Bearer {api_key}
```

**Header Details:**
- `Content-Type` is always `application/json`
- `Authorization` header is only sent if `--http-store-api-key` is configured
- The API key is sent as a Bearer token

#### Request Body

The body is JSON with exactly two fields:

```json
{
  "data": "base64-encoded-encrypted-session-data",
  "ttl_seconds": 3600
}
```

**Field Descriptions:**

1. **`data`** (string, required)
   - Base64-encoded encrypted session data
   - The session data is already encrypted by oauth2-proxy before being sent
   - Uses standard base64 encoding (RFC 4648)
   - Can be quite large (typically 1-5 KB, but can be larger with many tokens)

2. **`ttl_seconds`** (integer, required)
   - Time-to-live in seconds
   - How long the session should be stored before automatic expiration
   - Typically matches `--cookie-expire` setting (default: 168 hours = 604800 seconds)
   - Your backend should automatically delete the session after this duration

### Complete Example Request

```http
PUT https://session-store.example.com/sessions/_oauth2_proxy-a1b2c3d4e5f67890a1b2c3d4e5f67890 HTTP/1.1
Host: session-store.example.com
Content-Type: application/json
Authorization: Bearer mysecretapikey123
Content-Length: 1234

{
  "data": "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkwYWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY3ODkw",
  "ttl_seconds": 604800
}
```

### Response Expectations

**Success Responses:**
- `200 OK` - Session saved successfully (existing session updated)
- `201 Created` - Session created successfully (new session)

Both status codes are treated as success by oauth2-proxy.

**Error Responses:**
- `401 Unauthorized` - Invalid or missing API key
- `400 Bad Request` - Invalid request body (missing fields, invalid JSON)
- `500 Internal Server Error` - Storage backend error
- `503 Service Unavailable` - Backend temporarily unavailable

## Session Data Details

### What's in the Encrypted Data?

The `data` field contains encrypted session information. After decryption (which your backend should NOT do - store it as-is), the session contains:

- **OAuth Tokens:**
  - Access Token
  - ID Token
  - Refresh Token

- **User Information:**
  - Email address
  - Username
  - Groups
  - Preferred username

- **Session Metadata:**
  - Creation timestamp
  - Expiration time
  - Nonce (for security)

**Important:** Your HTTP storage backend should treat this data as an opaque encrypted blob. Do not attempt to decrypt or parse it - just store and retrieve it as-is.

### Session Data Encryption

The session data goes through this process before reaching your backend:

1. **Serialization:** Session struct → MessagePack format (with optional LZ4 compression)
2. **Encryption:** MessagePack data → AES-encrypted with per-session secret
3. **Base64 Encoding:** Encrypted bytes → Base64 string (for JSON transport)

Your backend only sees the base64-encoded encrypted data.

## Data Flow Example

Here's a complete example showing the data flow when oauth2-proxy saves a session:

### Step 1: User Authenticates
```
User → OAuth Provider → oauth2-proxy receives tokens
```

### Step 2: Session Creation
```go
// Inside oauth2-proxy
session := &SessionState{
    Email: "user@example.com",
    User: "user",
    AccessToken: "ya29.a0AfH6SMBx...",
    IDToken: "eyJhbGciOiJSUzI1NiIs...",
    RefreshToken: "1//0gvF5xK3...",
    ExpiresOn: time.Now().Add(1*time.Hour),
    CreatedAt: time.Now(),
}
```

### Step 3: Session Encryption
```go
// oauth2-proxy encrypts the session
ticketID := generateRandomID() // "a1b2c3d4e5f67890a1b2c3d4e5f67890"
secret := generateRandomSecret() // unique per session
key := "_oauth2_proxy-" + ticketID

// Serialize, compress, encrypt
serialized := msgpack.Marshal(session)
encrypted := aes.Encrypt(serialized, secret)
encodedData := base64.StdEncoding.EncodeToString(encrypted)
```

### Step 4: HTTP PUT Request
```http
PUT https://session-store.example.com/sessions/_oauth2_proxy-a1b2c3d4e5f67890a1b2c3d4e5f67890
Content-Type: application/json
Authorization: Bearer mysecretapikey123

{
  "data": "hQMK8yB7ImFjY2Vzc190b2tlbiI6InlhMjkuYTBBZkg2U01CeC4uLiIsImVtYWlsIjoidXNlckBleGFtcGxlLmNvbSIsInVzZXIiOiJ1c2VyIiwiaWRfdG9rZW4iOiJleUpoYkdjaU9pSlNVekkxTmlJcy4uLiIsInJlZnJlc2hfdG9rZW4iOiIxLy8wZ3ZGNXhLMy4uLiIsImV4cGlyZXNfb24iOjE3MDEyNzk2MDAsImNyZWF0ZWRfYXQiOjE3MDEyNzYwMDB9",
  "ttl_seconds": 604800
}
```

### Step 5: Backend Storage
Your backend should store this data structure:

```python
# Python example
sessions[key] = {
    'data': request.json['data'],  # Store as-is
    'expires_at': time.time() + request.json['ttl_seconds']
}
```

Or in Redis:
```python
redis.setex(
    key,
    request.json['ttl_seconds'],
    request.json['data']
)
```

## Implementation Examples

### Minimal Python Example
```python
from flask import Flask, request, jsonify
import time

app = Flask(__name__)
sessions = {}
API_KEY = "mysecretapikey123"

@app.route('/sessions/<key>', methods=['PUT'])
def save_session(key):
    # Verify API key
    auth = request.headers.get('Authorization', '')
    if auth != f'Bearer {API_KEY}':
        return jsonify({"error": "unauthorized"}), 401

    # Parse request
    data = request.get_json()
    if not data or 'data' not in data or 'ttl_seconds' not in data:
        return jsonify({"error": "invalid request"}), 400

    # Store session
    sessions[key] = {
        'data': data['data'],
        'expires_at': time.time() + data['ttl_seconds']
    }

    return jsonify({"status": "ok"}), 200
```

### Go Example
```go
package main

import (
    "encoding/json"
    "net/http"
    "time"
)

type SaveRequest struct {
    Data       string `json:"data"`
    TTLSeconds int64  `json:"ttl_seconds"`
}

type Session struct {
    Data      string
    ExpiresAt time.Time
}

var sessions = make(map[string]Session)
const apiKey = "mysecretapikey123"

func saveSession(w http.ResponseWriter, r *http.Request) {
    // Verify API key
    if r.Header.Get("Authorization") != "Bearer "+apiKey {
        http.Error(w, "unauthorized", http.StatusUnauthorized)
        return
    }

    // Extract key from URL
    key := r.URL.Path[len("/sessions/"):]

    // Parse request body
    var req SaveRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        http.Error(w, "invalid request", http.StatusBadRequest)
        return
    }

    // Store session
    sessions[key] = Session{
        Data:      req.Data,
        ExpiresAt: time.Now().Add(time.Duration(req.TTLSeconds) * time.Second),
    }

    w.WriteHeader(http.StatusOK)
    json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

### Node.js/Express Example
```javascript
const express = require('express');
const app = express();
app.use(express.json());

const sessions = new Map();
const API_KEY = 'mysecretapikey123';

app.put('/sessions/:key', (req, res) => {
    // Verify API key
    const auth = req.headers.authorization;
    if (auth !== `Bearer ${API_KEY}`) {
        return res.status(401).json({ error: 'unauthorized' });
    }

    // Validate request
    const { data, ttl_seconds } = req.body;
    if (!data || !ttl_seconds) {
        return res.status(400).json({ error: 'invalid request' });
    }

    // Store session
    const key = req.params.key;
    sessions.set(key, {
        data: data,
        expiresAt: Date.now() + (ttl_seconds * 1000)
    });

    res.json({ status: 'ok' });
});

app.listen(8080);
```

## Testing Your Implementation

### Using curl

```bash
# Save a session
curl -X PUT http://localhost:8080/sessions/_oauth2_proxy-test123 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mysecretapikey123" \
  -d '{
    "data": "dGVzdCBkYXRhIGhlcmU=",
    "ttl_seconds": 3600
  }'

# Expected response: {"status":"ok"}
```

### Using Python requests

```python
import requests
import base64

url = "http://localhost:8080/sessions/_oauth2_proxy-test123"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer mysecretapikey123"
}
data = {
    "data": base64.b64encode(b"test session data").decode('utf-8'),
    "ttl_seconds": 3600
}

response = requests.put(url, json=data, headers=headers)
print(response.status_code)  # Should be 200
print(response.json())       # Should be {"status":"ok"}
```

## Common Issues and Solutions

### Issue: Sessions are too large
**Cause:** Sessions with many OAuth scopes or large tokens
**Solution:** Ensure your backend can handle at least 10KB per session

### Issue: Base64 decoding errors
**Cause:** Storing the data as-is without proper handling
**Solution:** Store the base64 string directly; don't decode it

### Issue: Sessions expiring too early
**Cause:** Not implementing TTL correctly
**Solution:** Use `ttl_seconds` to set absolute expiration time

### Issue: Performance degradation
**Cause:** In-memory storage with many sessions
**Solution:** Use Redis or a database with automatic expiration

## Security Best Practices

1. **Always use HTTPS** - Protect API key and session data in transit
2. **Validate API key on every request** - Don't trust unauthenticated requests
3. **Store data as-is** - Don't decrypt or modify the session data
4. **Implement rate limiting** - Prevent abuse and DoS attacks
5. **Log suspicious activity** - Monitor for unusual patterns
6. **Set reasonable size limits** - Reject excessively large sessions (>10MB)
7. **Implement proper cleanup** - Remove expired sessions to prevent memory leaks

## Performance Considerations

- **Expected request rate:** Depends on traffic; typically 1-10 requests/second per oauth2-proxy instance
- **Typical session size:** 1-5 KB (base64-encoded)
- **TTL range:** Usually 1 hour to 7 days
- **Recommended timeout:** Backend should respond within 10 seconds (oauth2-proxy timeout is 30s)

## Additional Resources

- [Main Documentation](../docs/docs/configuration/sessions.md#http-storage)
- [Example Implementation](./http-session-store-example.py)
- [Deployment Guide](./HTTP_SESSION_STORE.md)
