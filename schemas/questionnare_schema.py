# schemas/questionnaire_schema.py
from marshmallow import INCLUDE, Schema, fields, validate


class QuestionnaireResponseSchema(Schema):
    class Meta:
        unknown = INCLUDE

    Q01 = fields.Boolean(required=False, allow_none=True)
    Q02 = fields.Boolean(required=False, allow_none=True)
    Q03 = fields.Boolean(required=False, allow_none=True)
    Q04 = fields.Boolean(required=False, allow_none=True)
    Q05 = fields.Boolean(required=False, allow_none=True)
    Q06 = fields.Boolean(required=False, allow_none=True)
    Q07 = fields.Boolean(required=False, allow_none=True)
    Q08 = fields.Boolean(required=False, allow_none=True)
    Q09 = fields.Boolean(required=False, allow_none=True)
    Q10 = fields.Boolean(required=False, allow_none=True)
    Q11 = fields.Boolean(required=False, allow_none=True)
    Q12 = fields.Boolean(required=False, allow_none=True)
    Q13 = fields.Boolean(required=False, allow_none=True)
    Q14 = fields.Boolean(required=False, allow_none=True)
    Q15 = fields.Boolean(required=False, allow_none=True)
    Q16 = fields.Boolean(required=False, allow_none=True)
    Q17 = fields.Boolean(required=False, allow_none=True)
    Q18 = fields.Boolean(required=False, allow_none=True)
    Q19 = fields.Boolean(required=False, allow_none=True)
    Q20 = fields.Boolean(required=False, allow_none=True)
    Q21 = fields.Boolean(required=False, allow_none=True)
    Q22 = fields.Boolean(required=False, allow_none=True)
    Q23 = fields.Boolean(required=False, allow_none=True)
    Q24 = fields.Boolean(required=False, allow_none=True)
    Q25 = fields.Boolean(required=False, allow_none=True)
    Q26 = fields.Boolean(required=False, allow_none=True)
    Q27 = fields.Boolean(required=False, allow_none=True)
    Q28 = fields.Boolean(required=False, allow_none=True)


class QuestionnaireBulkSchema(Schema):
    resource_type = fields.String(
        required=True, validate=validate.Equal("questionnaire_response")
    )
    # Validate that 'item' is a list of dictionaries
    item = fields.List(fields.Dict(), required=True)
