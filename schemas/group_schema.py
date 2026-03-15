from marshmallow import Schema, fields, validate

from schemas.test_schema import TestSessionSchema


class CreateGroupSchema(Schema):
    """Schema for POST /api/groups — no input fields required; body can be empty."""

    pass


class GroupSchema(Schema):
    """Full serialisation of a TestGroup with its nested test sessions."""

    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    status = fields.String(dump_only=True)
    overall_score = fields.Float(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True, allow_none=True)
    tests = fields.List(fields.Nested(TestSessionSchema), dump_only=True)


class GroupListQuerySchema(Schema):
    """Query params for GET /api/groups."""

    status = fields.String(
        required=False,
        validate=validate.OneOf(["pending", "in_progress", "completed"]),
    )
    page = fields.Integer(
        required=False, validate=validate.Range(min=1), load_default=1
    )
    per_page = fields.Integer(
        required=False, validate=validate.Range(min=1, max=100), load_default=20
    )
