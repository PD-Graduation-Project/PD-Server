from marshmallow import EXCLUDE, Schema, fields


class QuestionnaireResponseSchema(Schema):
    class Meta:
        # Use EXCLUDE to prevent typos (like "QQ01") from being silently accepted
        unknown = EXCLUDE


# Dynamically add Q01-Q28 fields to the class
# This loop creates: Q01 = fields.Boolean(...), Q02 = fields.Boolean(...)
for i in range(1, 29):
    field_name = f"Q{i:02d}"
    setattr(
        QuestionnaireResponseSchema,
        field_name,
        fields.Boolean(required=False, allow_none=True),
    )
