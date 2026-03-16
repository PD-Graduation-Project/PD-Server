from marshmallow import Schema, ValidationError, fields, validate, validates_schema


class TremorTestConfigSchema(Schema):
    @validates_schema
    def validate_config(self, data, **kwargs):
        valid_keys = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
        for key, value in data.items():
            if key not in valid_keys:
                raise ValidationError(
                    f"Invalid config key: {key}. Must be one of 0-10",
                    field_name=key,
                )
            if not isinstance(value, bool):
                raise ValidationError(
                    f"Invalid config value for {key}: must be boolean, got {type(value).__name__}",
                    field_name=key,
                )


class CreateTestSchema(Schema):
    test_type = fields.String(
        required=True, validate=validate.OneOf(["tremor", "drawing", "voice"])
    )
    group_id = fields.Integer(required=True)
    device = fields.String(required=False, validate=validate.OneOf(["mobile", "esp32"]))

    config = fields.Nested(
        TremorTestConfigSchema,
        required=False,
        load_default=dict,
    )
    device = fields.String(required=False, validate=validate.OneOf(["mobile", "esp32"]))

    config = fields.Dict(
        keys=fields.String(
            validate=validate.OneOf(
                ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
            )
        ),
        values=fields.Boolean(),
        required=False,
        load_default=dict,
    )


class TestInputSchema(Schema):
    id = fields.Integer(dump_only=True)
    input_type = fields.String(dump_only=True)
    file_path = fields.String(dump_only=True)
    mime_type = fields.String(dump_only=True)
    file_size = fields.Integer(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    expires_at = fields.DateTime(dump_only=True)


class TestSessionSchema(Schema):
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True)
    group_id = fields.Integer(dump_only=True, allow_none=True)
    test_type = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    device_source = fields.String(dump_only=True)
    config = fields.Dict(keys=fields.String(), values=fields.Boolean(), dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True)
    ml_score = fields.Float(dump_only=True, allow_none=True)
    ml_status = fields.String(dump_only=True, allow_none=True)
    ml_job_id = fields.String(dump_only=True, allow_none=True)
    inputs = fields.List(fields.Nested(TestInputSchema), dump_only=True)


class TestListQuerySchema(Schema):
    test_type = fields.String(
        required=False, validate=validate.OneOf(["tremor", "drawing", "voice"])
    )
    status = fields.String(
        required=False,
        validate=validate.OneOf(["pending", "in_progress", "completed", "failed"]),
    )
    group_id = fields.Integer(required=False)
    page = fields.Integer(
        required=False, validate=validate.Range(min=1), load_default=1
    )
    per_page = fields.Integer(
        required=False, validate=validate.Range(min=1, max=100), load_default=20
    )


class TestListResponseSchema(Schema):
    tests = fields.List(fields.Nested(TestSessionSchema))
    total = fields.Integer()
    page = fields.Integer()
    per_page = fields.Integer()
    pages = fields.Integer()


# File Upload Schemas
class TremorUploadSchema(Schema):
    subtest = fields.String(
        required=True,
        validate=validate.OneOf(
            ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        ),
    )
    hand = fields.String(required=True, validate=validate.OneOf(["l", "r"]))


class TremorUploadResponseSchema(Schema):
    id = fields.Integer()
    input_type = fields.String()
    subtest = fields.String()
    hand = fields.String()
    file_path = fields.String()


class DrawingUploadResponseSchema(Schema):
    inputs = fields.List(fields.Dict())


class VoiceUploadResponseSchema(Schema):
    id = fields.Integer()
    input_type = fields.String()
    file_path = fields.String()


class CompleteTestResponseSchema(Schema):
    message = fields.String()
    status = fields.String()
    uploaded_count = fields.Integer()
    expected_count = fields.Integer()
    missing = fields.List(fields.String())
