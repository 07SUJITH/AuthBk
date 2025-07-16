# Redis Setup & Django Integration Guide

This document explains how to install a local Redis instance and integrate it with a Django project for caching and rate-limiting.

---

## Prerequisites

- Python ≥ 3.8
- Django ≥ 4.0
- A Debian/Ubuntu-based Linux distribution (commands may differ on other OSs)

---

## 1. Install required Python packages

```bash
pip install django-redis django-ratelimit
pip freeze > requirements.txt   # (optional) lock versions
```

---

## 2. Enable `django_ratelimit`

Add the package to your `INSTALLED_APPS` list in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_ratelimit',
]
```

---

## 3. Configure Redis caching in `settings.py`

```python
from decouple import config  # or use os.environ.get

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# Rate-limit settings
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"
```

---

## 4. Update your codebase

- Add rate-limiting decorators (e.g., `@ratelimit(key='ip', rate='5/m')`) to authentication/OTP views.
- Update OTP-related serializers to respect rate-limits.
- Update user-registration serializer if necessary.

---

## 5. Install Redis on Ubuntu/Debian

Redis is lightweight (a few MB RAM) and runs as a background service.

```bash
sudo apt update
sudo apt install redis-server
```

### Verify the installation

```bash
sudo systemctl start redis-server  # Start if not already running
redis-cli ping                     # Should respond with: PONG
```

### Start & stop manually

```bash
sudo systemctl stop redis-server   # Stop Redis
sudo systemctl start redis-server  # Start Redis
```

---

## 6. Useful `redis-cli` commands

```bash
redis-cli
> keys *           # list all keys (use patterns in production)
> get mykey        # retrieve value of a key
> flushall         # remove ALL keys (irreversible!)
```

---

## 7. Next steps

1. Run your Django test-suite to ensure caching is working.
2. For production, use a managed Redis service (Docker, AWS ElastiCache, DigitalOcean, etc.).
3. Monitor memory usage with `redis-cli info memory` or a dedicated dashboard.

---

<!-- Legacy instructions retained below for reference -->

2. pip freeze > requirements.txt
3. add to installed apps => 'django_ratelimit',
4. add these in settings.py

# Redis cache configuration (use local Redis for development/testing)

CACHES = {
'default': {
'BACKEND': 'django_redis.cache.RedisCache',
'LOCATION': config('REDIS_URL', default='redis://localhost:6379/0'),
'OPTIONS': {
'CLIENT_CLASS': 'django_redis.client.DefaultClient',
}
}
}

# Rate limiting settings

RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

5. updated verify otp serializer and resend otp serializer.
6. updated user registration serializer in user apps.
7. updated views in authentication views with a decorators , and rate limit function response.

8. local redis server .
