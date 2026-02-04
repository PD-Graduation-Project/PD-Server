from marshmallow import EXCLUDE, Schema, fields, validate


class QuestionnaireItemSchema(Schema):
    class Meta:
        unknown = EXCLUDE  # Ignore extra fields in the item object

    link_id = fields.String(required=True)
    answer = fields.Boolean(required=False, allow_none=True)


class QuestionnaireBulkSchema(Schema):
    resource_type = fields.String(
        required=True, validate=validate.Equal("questionnaire_response")
    )
    # Use Nested validation to ensure every item has link_id and answer
    item = fields.List(fields.Nested(QuestionnaireItemSchema), required=True)


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
