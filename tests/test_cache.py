import fakeredis
import pytest
from flask import Flask, g, jsonify

from utils.cache import _redis, cached, invalidates, invalidate_test_caches


@pytest.fixture(autouse=True)
def patch_redis(monkeypatch):
    server = fakeredis.FakeServer()
    fr = fakeredis.FakeRedis(server=server, decode_responses=True)
    monkeypatch.setattr("utils.cache._redis", lambda: fr)
    return fr


@pytest.fixture
def fake_redis(patch_redis):
    return patch_redis


@pytest.fixture
def cached_app(fake_redis):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["CACHE_ENABLED"] = True

    @app.before_request
    def set_user():
        g.user_id = 1

    @app.route("/test/<int:test_id>")
    @cached(ttl=30, prefix="test")
    def test_get(test_id):
        return jsonify({"id": test_id, "value": "fresh"}), 200

    @app.route("/test/<int:test_id>/mutate", methods=["POST"])
    @invalidates("test:{test_id}", "tests:*")
    def test_mutate(test_id):
        return jsonify({"success": True}), 200

    @app.route("/test/<int:test_id>/mutate-only", methods=["POST"])
    @invalidates("test:{test_id}")
    def test_mutate_only(test_id):
        return jsonify({"success": True}), 200

    return app.test_client()


class TestCachedDecorator:
    def test_cache_hit_returns_cached_response(self, cached_app):
        resp1 = cached_app.get("/test/1")
        assert resp1.status_code == 200
        assert resp1.get_json() == {"id": 1, "value": "fresh"}

        resp2 = cached_app.get("/test/1")
        assert resp2.status_code == 200
        assert resp2.get_json() == {"id": 1, "value": "fresh"}

    def test_cache_miss_for_different_resource(self, cached_app):
        cached_app.get("/test/1")
        resp2 = cached_app.get("/test/2")
        assert resp2.get_json() == {"id": 2, "value": "fresh"}

    def test_cache_skipped_when_disabled(self, fake_redis):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["CACHE_ENABLED"] = False

        call_count = 0

        @app.before_request
        def set_user():
            g.user_id = 1

        @app.route("/test/<int:test_id>")
        @cached(ttl=30, prefix="test")
        def test_get(test_id):
            nonlocal call_count
            call_count += 1
            return jsonify({"id": test_id}), 200

        client = app.test_client()
        client.get("/test/1")
        client.get("/test/1")
        assert call_count == 2

    def test_error_responses_not_cached(self, fake_redis):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["CACHE_ENABLED"] = True

        @app.before_request
        def set_user():
            g.user_id = 1

        @app.route("/error")
        @cached(ttl=30, prefix="error")
        def error_route():
            return jsonify({"error": "not found"}), 404

        client = app.test_client()
        client.get("/error")
        client.get("/error")

        keys = [k for k in fake_redis.keys("cache:*")]
        assert len(keys) == 0

    def test_cache_returns_correct_status_code(self, cached_app):
        resp = cached_app.get("/test/42")
        assert resp.status_code == 200

    def test_cache_has_ttl(self, fake_redis, cached_app):
        cached_app.get("/test/1")
        keys = [k for k in fake_redis.keys("cache:*")]
        assert len(keys) > 0
        assert any(fake_redis.ttl(k) > 0 for k in keys)


class TestInvalidatesDecorator:
    def test_invalidates_specific_key(self, cached_app, fake_redis):
        cached_app.get("/test/1")
        assert fake_redis.exists("cache:v1:user:1:test:1")

        cached_app.post("/test/1/mutate-only")
        assert not fake_redis.exists("cache:v1:user:1:test:1")

    def test_invalidates_list_pattern(self, cached_app, fake_redis):
        cached_app.get("/test/1")
        fake_redis.set("cache:v1:user:1:tests:abc123", '"data"|||200')

        cached_app.post("/test/1/mutate")

        assert not fake_redis.exists("cache:v1:user:1:test:1")
        list_keys = [k for k in fake_redis.keys("cache:v1:user:1:tests:*")]
        assert len(list_keys) == 0

    def test_invalidation_does_not_affect_other_users(self, cached_app, fake_redis):
        cached_app.get("/test/1")
        fake_redis.set("cache:v1:user:2:test:1", '"other"|||200')

        cached_app.post("/test/1/mutate-only")

        assert fake_redis.exists("cache:v1:user:2:test:1")


class TestInvalidateTestCaches:
    def test_removes_test_and_list_caches(self, fake_redis):
        fake_redis.set("cache:v1:user:1:test:42", '"data"|||200')
        fake_redis.set("cache:v1:user:1:tests:abc", '"data"|||200')
        fake_redis.set("cache:v1:user:1:tests:def", '"data"|||200')

        invalidate_test_caches(1, 42)

        assert not fake_redis.exists("cache:v1:user:1:test:42")
        list_keys = list(fake_redis.scan_iter("cache:v1:user:1:tests:*"))
        assert len(list_keys) == 0

    def test_does_not_affect_other_tests(self, fake_redis):
        fake_redis.set("cache:v1:user:1:test:42", '"data"|||200')
        fake_redis.set("cache:v1:user:1:test:99", '"other"|||200')

        invalidate_test_caches(1, 42)

        assert fake_redis.exists("cache:v1:user:1:test:99")
