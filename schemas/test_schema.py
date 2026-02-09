from marshmallow import Schema, fields, validate


class TremorTestConfigSchema(Schema):
    step_0 = fields.Boolean(required=False, load_default=True)
    step_1 = fields.Boolean(required=False, load_default=True)
    step_2 = fields.Boolean(required=False, load_default=True)
    step_3 = fields.Boolean(required=False, load_default=True)
    step_4 = fields.Boolean(required=False, load_default=True)
    step_5 = fields.Boolean(required=False, load_default=True)
    step_6 = fields.Boolean(required=False, load_default=True)
    step_7 = fields.Boolean(required=False, load_default=True)
    step_8 = fields.Boolean(required=False, load_default=True)
    step_9 = fields.Boolean(required=False, load_default=True)
    step_10 = fields.Boolean(required=False, load_default=True)


class CreateTestSchema(Schema):
    test_type = fields.String(
        required=True, validate=validate.OneOf(["tremor", "drawing", "voice"])
    )
    device = fields.String(required=False, validate=validate.OneOf(["mobile", "esp32"]))

    config = fields.Dict(
        keys=fields.String(),
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
    test_type = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    device_source = fields.String(dump_only=True)
    config = fields.Dict(keys=fields.String(), values=fields.Boolean(), dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    completed_at = fields.DateTime(dump_only=True)
    ml_score = fields.Float(dump_only=True)
    inputs = fields.List(fields.Nested(TestInputSchema), dump_only=True)


class TestListQuerySchema(Schema):
    test_type = fields.String(
        required=False, validate=validate.OneOf(["tremor", "drawing", "voice"])
    )
    status = fields.String(
        required=False,
        validate=validate.OneOf(["pending", "in_progress", "completed", "failed"]),
    )
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
