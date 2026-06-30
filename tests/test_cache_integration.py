"""Integration tests for Redis response caching against real API routes.

Uses fakeredis to mock Redis and creates a fresh Flask app per test
with CACHE_ENABLED=True so the @cached / @invalidates decorators fire.
"""

import fakeredis
import pytest

from utils.cache import _redis


def _create_test_session(client, headers):
    """Helper: create a group + test session, return (group_id, test_id)."""
    resp = client.post("/api/groups", headers=headers)
    assert resp.status_code == 201
    group_id = resp.get_json()["data"]["id"]

    resp = client.post(
        "/api/tests",
        headers=headers,
        json={"test_type": "tremor", "group_id": group_id},
    )
    assert resp.status_code == 201
    test_id = resp.get_json()["data"]["id"]

    return group_id, test_id


def _tremor_payload():
    return {
        "subtest_id": "0",
        "hand": "l",
        "imu_data": {
            "ax": [1.0], "ay": [2.0], "az": [3.0],
            "gx": [0.1], "gy": [0.2], "gz": [0.3],
        },
    }


@pytest.fixture
def fake_redis(monkeypatch):
    server = fakeredis.FakeServer()
    fr = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr("utils.cache._redis", lambda: fr)
    return fr


@pytest.fixture
def cached_env(fake_redis, monkeypatch):
    monkeypatch.setattr("config.Config.STORAGE_BACKEND", "local")
    from app import create_app
    from models.database import db
    from models.user import User

    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
        "JWT_ALGORITHM": "HS256",
        "FACTORY_SECRET": "test_factory_secret",
        "RATE_LIMIT_ENABLED": False,
        "CACHE_ENABLED": True,
    })

    with app.app_context():
        db.create_all()
        user = User(email="test@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()

        resp = client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        headers = {
            "Authorization": f"Bearer {resp.get_json()['access_token']}",
            "Content-Type": "application/json",
        }

        yield client, headers, user, fake_redis

        db.drop_all()


class TestCacheIntegration:

    def test_get_test_creates_cache_entry(self, cached_env):
        client, headers, user, fr = cached_env
        _, test_id = _create_test_session(client, headers)

        resp = client.get(f"/api/tests/{test_id}", headers=headers)
        assert resp.status_code == 200

        key = f"cache:v1:user:{user.id}:test:{test_id}"
        assert fr.exists(key)
        assert fr.ttl(key) > 0

    def test_second_get_returns_same_data(self, cached_env):
        client, headers, user, _ = cached_env
        _, test_id = _create_test_session(client, headers)

        resp1 = client.get(f"/api/tests/{test_id}", headers=headers)
        resp2 = client.get(f"/api/tests/{test_id}", headers=headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.get_json() == resp2.get_json()

    def test_mutation_invalidates_test_and_list_cache(self, cached_env):
        client, headers, user, fr = cached_env
        _, test_id = _create_test_session(client, headers)

        client.get(f"/api/tests/{test_id}", headers=headers)

        key = f"cache:v1:user:{user.id}:test:{test_id}"
        assert fr.exists(key)

        resp = client.post(
            f"/api/tests/{test_id}/tremor",
            headers=headers,
            json=_tremor_payload(),
        )
        assert resp.status_code == 200

        assert not fr.exists(key)
        list_keys = list(fr.scan_iter(f"cache:v1:user:{user.id}:tests:*"))
        assert len(list_keys) == 0

    def test_create_test_clears_list_cache(self, cached_env):
        client, headers, user, fr = cached_env
        _, test_id = _create_test_session(client, headers)

        resp = client.get("/api/tests", headers=headers)
        assert resp.status_code == 200

        list_keys = list(fr.scan_iter(f"cache:v1:user:{user.id}:tests:*"))
        assert len(list_keys) == 1

        _create_test_session(client, headers)

        list_keys_after = list(fr.scan_iter(f"cache:v1:user:{user.id}:tests:*"))
        assert len(list_keys_after) == 0

    def test_create_group_clears_groups_list_cache(self, cached_env):
        client, headers, user, fr = cached_env

        resp = client.get("/api/groups", headers=headers)
        assert resp.status_code == 200

        group_keys = list(fr.scan_iter(f"cache:v1:user:{user.id}:groups:*"))
        assert len(group_keys) == 1

        resp = client.post("/api/groups", headers=headers)
        assert resp.status_code == 201

        group_keys_after = list(fr.scan_iter(f"cache:v1:user:{user.id}:groups:*"))
        assert len(group_keys_after) == 0

    def test_user_isolation_on_invalidation(self, fake_redis, monkeypatch):
        monkeypatch.setattr("config.Config.STORAGE_BACKEND", "local")
        from app import create_app
        from models.database import db
        from models.user import User

        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
            "JWT_ALGORITHM": "HS256",
            "FACTORY_SECRET": "test_factory_secret",
            "RATE_LIMIT_ENABLED": False,
            "CACHE_ENABLED": True,
        })

        with app.app_context():
            db.create_all()
            user_a = User(email="alice@example.com")
            user_a.set_password("password123")
            user_b = User(email="bob@example.com")
            user_b.set_password("password456")
            db.session.add_all([user_a, user_b])
            db.session.commit()

            client = app.test_client()

            resp_a = client.post(
                "/api/auth/login",
                json={"email": "alice@example.com", "password": "password123"},
            )
            headers_a = {
                "Authorization": f"Bearer {resp_a.get_json()['access_token']}",
                "Content-Type": "application/json",
            }

            resp_b = client.post(
                "/api/auth/login",
                json={"email": "bob@example.com", "password": "password456"},
            )
            headers_b = {
                "Authorization": f"Bearer {resp_b.get_json()['access_token']}",
                "Content-Type": "application/json",
            }

            _, test_a_id = _create_test_session(client, headers_a)
            _, test_b_id = _create_test_session(client, headers_b)

            client.get(f"/api/tests/{test_a_id}", headers=headers_a)
            client.get(f"/api/tests/{test_b_id}", headers=headers_b)

            key_a = f"cache:v1:user:{user_a.id}:test:{test_a_id}"
            key_b = f"cache:v1:user:{user_b.id}:test:{test_b_id}"
            assert fake_redis.exists(key_a)
            assert fake_redis.exists(key_b)

            client.post(
                f"/api/tests/{test_a_id}/tremor",
                headers=headers_a,
                json=_tremor_payload(),
            )

            assert not fake_redis.exists(key_a)
            assert fake_redis.exists(key_b)

            db.drop_all()

    def test_list_cache_key_includes_query_hash(self, cached_env):
        client, headers, user, fr = cached_env
        _, test_id = _create_test_session(client, headers)

        resp = client.get("/api/tests?status=pending", headers=headers)
        assert resp.status_code == 200

        list_keys = list(fr.scan_iter(f"cache:v1:user:{user.id}:tests:*"))
        assert len(list_keys) == 1

        last_part = list_keys[0].split(":")[-1]
        assert len(last_part) == 8, f"Expected 8-char hash, got {last_part}"
        int(last_part, 16)

    def test_error_responses_not_cached(self, cached_env):
        client, headers, _, fr = cached_env

        resp = client.get("/api/tests/99999", headers=headers)
        assert resp.status_code == 404

        all_keys = list(fr.scan_iter("cache:*"))
        assert len(all_keys) == 0

    def test_cache_disabled_is_noop(self, monkeypatch):
        server = fakeredis.FakeServer()
        fr = fakeredis.FakeRedis(server=server, decode_responses=True)
        monkeypatch.setattr("utils.cache._redis", lambda: fr)
        monkeypatch.setattr("config.Config.STORAGE_BACKEND", "local")

        from app import create_app
        from models.database import db
        from models.user import User

        app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-secret-key-do-not-use-in-production",
            "JWT_ALGORITHM": "HS256",
            "FACTORY_SECRET": "test_factory_secret",
            "RATE_LIMIT_ENABLED": False,
            "CACHE_ENABLED": False,
        })

        with app.app_context():
            db.create_all()
            user = User(email="test@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()

            client = app.test_client()
            resp = client.post(
                "/api/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )
            headers = {
                "Authorization": f"Bearer {resp.get_json()['access_token']}",
                "Content-Type": "application/json",
            }

            _, test_id = _create_test_session(client, headers)
            client.get(f"/api/tests/{test_id}", headers=headers)

            all_keys = list(fr.scan_iter("cache:*"))
            assert len(all_keys) == 0

            db.drop_all()
