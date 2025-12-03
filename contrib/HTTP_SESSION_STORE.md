# HTTP Session Store

This directory contains an example implementation of an HTTP session store backend for oauth2-proxy.

## Overview

The HTTP session store allows oauth2-proxy to store session data on a remote server via a REST API instead of in cookies or Redis. This is useful when:

- You want to use a different storage backend (e.g., PostgreSQL, MySQL, DynamoDB)
- You need centralized session management across multiple oauth2-proxy instances
- You want to implement custom session management logic
- You have an existing session management system to integrate with

## Quick Start

### 1. Start the Example HTTP Session Store

```bash
# Install dependencies
pip install flask redis

# Run with in-memory storage (for testing)
python3 http-session-store-example.py

# Or run with Redis (for production)
REDIS_URL=redis://localhost:6379 API_KEY=mysecret python3 http-session-store-example.py
```

### 2. Configure oauth2-proxy

Add these flags to your oauth2-proxy configuration:

```bash
oauth2-proxy \
  --session-store-type=http \
  --http-store-base-url=http://localhost:8080 \
  --http-store-api-key=your-secret-api-key-here \
  ... other options ...
```

Or in a config file:

```toml
session_store_type = "http"
http_store_base_url = "http://localhost:8080"
http_store_api_key = "your-secret-api-key-here"
```

## REST API Specification

The HTTP session store must implement the following endpoints:

### Authentication

All requests include an `Authorization` header with a Bearer token:
```
Authorization: Bearer {api-key}
```

### Endpoints

#### Save Session
```
PUT /sessions/{key}
Content-Type: application/json

{
  "data": "base64-encoded-encrypted-session-data",
  "ttl_seconds": 3600
}
```

Response: `200 OK` or `201 Created`

#### Load Session
```
GET /sessions/{key}
```

Response:
- `200 OK` with `{"data": "base64-encoded-encrypted-session-data"}`
- `404 Not Found` if session doesn't exist

#### Clear Session
```
DELETE /sessions/{key}
```

Response: `200 OK` or `204 No Content`

#### Health Check
```
GET /health
```

Response: `200 OK` if healthy

## Security Considerations

- **Always use HTTPS in production** to protect the API key and session data
- **Use strong API keys** - generate them with `openssl rand -base64 32`
- **Implement rate limiting** to prevent abuse
- **Monitor for suspicious activity** - implement logging and alerting
- **Rotate API keys regularly** if possible
- **Use Redis or a database** instead of in-memory storage for production
- **Implement proper access controls** on the session store backend

## Production Deployment

For production use, consider:

1. **Use a proper WSGI server** instead of Flask's development server:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8080 http-session-store-example:app
   ```

2. **Add HTTPS/TLS support** using a reverse proxy (nginx, HAProxy) or application-level TLS

3. **Use persistent storage**:
   - Redis (recommended)
   - PostgreSQL with automatic expiration
   - MySQL/MariaDB
   - DynamoDB
   - Any other database with TTL support

4. **Add monitoring**:
   - Health checks
   - Metrics (session count, request rate, errors)
   - Logging
   - Alerting

5. **Implement high availability**:
   - Run multiple instances behind a load balancer
   - Use persistent storage (Redis, database)
   - Implement graceful shutdown

## Example Production Setup

### Using Docker Compose

```yaml
version: '3'
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  session-store:
    build: .
    environment:
      - REDIS_URL=redis://redis:6379
      - API_KEY=${API_KEY}
    depends_on:
      - redis
    ports:
      - "8080:8080"

  oauth2-proxy:
    image: quay.io/oauth2-proxy/oauth2-proxy:latest
    command:
      - --session-store-type=http
      - --http-store-base-url=http://session-store:8080
      - --http-store-api-key=${API_KEY}
    depends_on:
      - session-store

volumes:
  redis-data:
```

## Troubleshooting

### Connection refused
- Ensure the session store is running and accessible
- Check firewall rules
- Verify the base URL is correct

### 401 Unauthorized
- Verify the API key matches between oauth2-proxy and the session store
- Check the Authorization header is being sent correctly

### Sessions not persisting
- Check the TTL is being set correctly
- Verify the storage backend is working (Redis connection, disk space)
- Check for errors in the session store logs

### Performance issues
- Use persistent storage (Redis) instead of in-memory
- Scale horizontally by running multiple session store instances
- Implement caching if needed
- Monitor and optimize database queries

## Further Reading

- [OAuth2 Proxy Session Storage Documentation](https://oauth2-proxy.github.io/oauth2-proxy/docs/configuration/session_storage#http-storage)
- [OAuth2 Proxy Configuration Options](https://oauth2-proxy.github.io/oauth2-proxy/docs/configuration/overview)
