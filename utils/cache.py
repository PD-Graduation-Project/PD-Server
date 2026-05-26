import hashlib
from functools import wraps

from flask import Response, current_app, g, request
from redis import ConnectionPool, Redis

from config import Config

_pool = ConnectionPool.from_url(
    Config.REDIS_URL,
    decode_responses=True,
    max_connections=10,
)


def _redis() -> Redis:
    return Redis(connection_pool=_pool)


def _cache_key(prefix: str, **kwargs) -> str:
    user_id = getattr(g, "user_id", "anon")
    key = f"cache:v1:user:{user_id}:{prefix}"

    if kwargs:
        resource_part = "_".join(str(v) for v in kwargs.values())
        key = f"{key}:{resource_part}"

    qs = request.query_string.decode() if request.query_string else ""
    if qs:
        param_hash = hashlib.md5(qs.encode()).hexdigest()[:8]
        key = f"{key}:{param_hash}"

    return key


def _unpack(result):
    if isinstance(result, tuple):
        resp, status = result[0], result[1]
    else:
        resp, status = result, 200

    if hasattr(resp, "get_json"):
        body = resp.get_data()
        body_str = body.decode("utf-8") if isinstance(body, bytes) else str(body)
    elif isinstance(resp, (dict, list)):
        body_str = resp  # type: ignore
    else:
        body_str = str(resp)

    return body_str, status


def cached(ttl: int = 30, prefix: str | None = None):
    """Cache the JSON response of a GET endpoint in Redis.

    Args:
        ttl: Time-to-live in seconds (default 30)
        prefix: Cache key prefix. If None, uses request.endpoint.
                E.g. prefix="test" produces key cache:v1:user:{uid}:test:{id}
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("CACHE_ENABLED", True):
                return fn(*args, **kwargs)

            if request.method != "GET":
                return fn(*args, **kwargs)

            p = prefix or (request.endpoint or "unknown").replace(".", ":")
            key = _cache_key(p, **kwargs)

            r = _redis()
            cached_data = r.get(key)
            if cached_data is not None:
                body_str, status_str = cached_data.rsplit("|||", 1)
                return Response(body_str, status=int(status_str), content_type="application/json")

            result = fn(*args, **kwargs)
            body_str, status = _unpack(result)

            if status < 400:
                r.setex(key, ttl, f"{body_str}|||{status}")

            return result
        return wrapper
    return decorator


def invalidates(*patterns: str):
    """Invalidate cache keys matching patterns after a mutating endpoint.

    Patterns may contain {param_name} placeholders resolved from
    the route's URL path parameters (kwargs).

    Patterns ending with '*' use scan_iter for glob matching.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("CACHE_ENABLED", True):
                return fn(*args, **kwargs)

            user_id = getattr(g, "user_id", "anon")
            r = _redis()

            for pattern in patterns:
                resolved = pattern.format(**kwargs)
                full_pattern = f"cache:v1:user:{user_id}:{resolved}"

                if full_pattern.endswith("*"):
                    for key in r.scan_iter(full_pattern):
                        r.delete(key)
                else:
                    r.delete(full_pattern)

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def invalidate_test_caches(user_id: int, test_id: int):
    """Invalidate all caches for a specific test (detail + list)."""
    r = _redis()
    r.delete(f"cache:v1:user:{user_id}:test:{test_id}")
    for key in r.scan_iter(f"cache:v1:user:{user_id}:tests:*"):
        r.delete(key)
