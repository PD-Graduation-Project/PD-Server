from typing import Any, Tuple

from flask import Request as FlaskRequest
from flask import jsonify

ResponseLike = Tuple[Any, int]


def get_json_body(
    request: FlaskRequest,
) -> Tuple[dict[str, Any], None] | Tuple[None, ResponseLike]:
    """Get JSON body from request and validate it's a dict."""
    data = request.get_json()
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Invalid JSON body, expected object"}), 400)
    return data, None


def get_query_params(request: FlaskRequest) -> dict[str, Any]:
    """Convert request.args to dict for schema loading."""
    return dict(request.args)
