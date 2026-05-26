from flask import Blueprint, g, jsonify, request

from middleware.authenticate import authenticate
from models.database import db
from models.test_models import TestInput
from utils.cache import invalidate_test_caches
from utils.s3_storage import get_storage, is_s3_enabled

file_bp = Blueprint("files", __name__, url_prefix="/api/files")


@file_bp.route("/<int:input_id>", methods=["GET"])
@authenticate
def get_file(input_id):
    """Get file URL (pre-signed URL for S3, or local path for filesystem)."""
    inp = db.session.get(TestInput, input_id)
    if not inp:
        return jsonify({"error": "File not found"}), 404

    # Ownership check
    if inp.test_session.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    # Return pre-signed URL for S3, or local path for filesystem
    if is_s3_enabled():
        storage = get_storage()
        url = storage.get_presigned_url(inp.file_path, expires_in=3600)
        if not url:
            return jsonify({"error": "Failed to generate URL"}), 500
        return jsonify({"url": url}), 200
    else:
        # Return local file path for filesystem storage
        return jsonify({"url": f"/{inp.file_path}"}), 200


@file_bp.route("/<int:input_id>", methods=["DELETE"])
@authenticate
def delete_file(input_id):
    """Delete a test input file."""
    inp = db.session.get(TestInput, input_id)
    if not inp:
        return jsonify({"error": "File not found"}), 404

    # Ownership check
    if inp.test_session.user_id != g.user_id:
        return jsonify({"error": "Forbidden"}), 403

    # Delete from storage
    from utils.storage import delete_file

    success = delete_file(inp.file_path)
    if not success:
        return jsonify({"error": "Failed to delete file"}), 500

    test_session_id = inp.test_session_id

    # Delete from DB
    db.session.delete(inp)
    db.session.commit()

    invalidate_test_caches(g.user_id, test_session_id)

    return jsonify({"success": True, "message": "File deleted"}), 200
