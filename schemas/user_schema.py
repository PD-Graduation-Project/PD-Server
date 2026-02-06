from marshmallow import Schema, fields, validate


class UserDemographicsSchema(Schema):
    class Meta:
        fields = (
            "id",
            "age",
            "height",
            "weight",
            "gender",
            "pd_appearance_in_kinship",
            "pd_appearance_in_first_grade_kinship",
        )

    id = fields.Integer(dump_only=True)
    age = fields.Integer(required=False, validate=validate.Range(min=0, max=100))
    height = fields.Integer(required=False, validate=validate.Range(min=0, max=300))
    weight = fields.Integer(required=False, validate=validate.Range(min=0, max=500))
    gender = fields.String(required=False, validate=validate.OneOf(["male", "female"]))
    pd_appearance_in_kinship = fields.Boolean(required=False)
    pd_appearance_in_first_grade_kinship = fields.Boolean(required=False)
