#!/usr/bin/env python3
"""
Example HTTP Session Store Backend for oauth2-proxy

This is a simple example implementation of an HTTP session store backend
that can be used with oauth2-proxy's HTTP session storage option.

Usage:
    python3 http-session-store-example.py

Requirements:
    pip install flask redis

Configuration in oauth2-proxy:
    --session-store-type=http
    --http-store-base-url=http://localhost:8080
    --http-store-api-key=your-secret-api-key-here

For production use, consider:
- Using a proper WSGI server (gunicorn, uwsgi)
- Adding HTTPS/TLS support
- Using Redis or a database instead of in-memory storage
- Adding monitoring and logging
- Implementing rate limiting
- Using environment variables for configuration
"""

from flask import Flask, request, jsonify
import time
import os
import redis
from typing import Dict, Optional

app = Flask(__name__)

# Configuration
API_KEY = os.environ.get('API_KEY', 'your-secret-api-key-here')
REDIS_URL = os.environ.get('REDIS_URL', None)

# Storage backend
if REDIS_URL:
    # Use Redis for production
    redis_client = redis.from_url(REDIS_URL)
    storage_backend = 'redis'
    print(f"Using Redis storage: {REDIS_URL}")
else:
    # Use in-memory storage for testing (not suitable for production)
    sessions: Dict[str, Dict] = {}
    storage_backend = 'memory'
    print("Using in-memory storage (not recommended for production)")


def check_auth() -> bool:
    """Verify the API key from the Authorization header"""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    return auth[7:] == API_KEY


def get_session(key: str) -> Optional[Dict]:
    """Retrieve a session from storage"""
    if storage_backend == 'redis':
        data = redis_client.get(key)
        if data is None:
            return None
        import json
        return json.loads(data)
    else:
        return sessions.get(key)


def set_session(key: str, data: Dict, ttl_seconds: int):
    """Store a session in storage"""
    if storage_backend == 'redis':
        import json
        redis_client.setex(key, ttl_seconds, json.dumps(data))
    else:
        data['expires_at'] = time.time() + ttl_seconds
        sessions[key] = data


def delete_session(key: str):
    """Delete a session from storage"""
    if storage_backend == 'redis':
        redis_client.delete(key)
    else:
        sessions.pop(key, None)


def cleanup_expired_sessions():
    """Clean up expired sessions (only for in-memory storage)"""
    if storage_backend == 'memory':
        now = time.time()
        expired = [k for k, v in sessions.items() if v.get('expires_at', 0) < now]
        for key in expired:
            del sessions[key]
        if expired:
            print(f"Cleaned up {len(expired)} expired sessions")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    # Optionally check storage backend connectivity
    if storage_backend == 'redis':
        try:
            redis_client.ping()
        except Exception as e:
            return jsonify({"error": f"redis connection failed: {str(e)}"}), 503

    return jsonify({
        "status": "healthy",
        "storage": storage_backend,
        "session_count": redis_client.dbsize() if storage_backend == 'redis' else len(sessions)
    }), 200


@app.route('/sessions/<key>', methods=['PUT'])
def save_session(key: str):
    """Save or update a session"""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        data = request.get_json()
        if not data or 'data' not in data or 'ttl_seconds' not in data:
            return jsonify({"error": "invalid request: missing data or ttl_seconds"}), 400

        set_session(key, {
            'data': data['data'],
            'created_at': time.time()
        }, int(data['ttl_seconds']))

        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/sessions/<key>', methods=['GET'])
def load_session(key: str):
    """Load a session"""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        # Clean up expired sessions periodically (for in-memory storage)
        if storage_backend == 'memory':
            cleanup_expired_sessions()

        session = get_session(key)
        if session is None:
            return jsonify({"error": "session not found"}), 404

        # Check if session is expired (for in-memory storage)
        if storage_backend == 'memory':
            if time.time() > session.get('expires_at', 0):
                delete_session(key)
                return jsonify({"error": "session expired"}), 404

        return jsonify({"data": session['data']}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/sessions/<key>', methods=['DELETE'])
def clear_session(key: str):
    """Delete a session"""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    try:
        delete_session(key)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/stats', methods=['GET'])
def stats():
    """Statistics endpoint (optional, for monitoring)"""
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    if storage_backend == 'memory':
        cleanup_expired_sessions()
        return jsonify({
            "total_sessions": len(sessions),
            "storage_backend": storage_backend
        }), 200
    else:
        return jsonify({
            "total_sessions": redis_client.dbsize(),
            "storage_backend": storage_backend
        }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("OAuth2 Proxy HTTP Session Store Example")
    print("=" * 60)
    print(f"Storage backend: {storage_backend}")
    print(f"API Key: {API_KEY}")
    print("\nEndpoints:")
    print("  GET  /health          - Health check")
    print("  PUT  /sessions/{key}  - Save session")
    print("  GET  /sessions/{key}  - Load session")
    print("  DELETE /sessions/{key} - Delete session")
    print("  GET  /stats           - Statistics (optional)")
    print("\nConfigure oauth2-proxy with:")
    print("  --session-store-type=http")
    print("  --http-store-base-url=http://localhost:8080")
    print(f"  --http-store-api-key={API_KEY}")
    print("=" * 60)

    # Run Flask development server
    # In production, use a proper WSGI server like gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8080 http-session-store-example:app
    app.run(host='0.0.0.0', port=8080, debug=False)
