from marshmallow import Schema, fields, validate


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=validate.Length(min=6))


class RegisterSchema(LoginSchema):
    # Inherits email and password validation from LoginSchema
    pass


class RefreshSchema(Schema):
    refresh_token = fields.String(required=True)


class SessionSchema(Schema):
    id = fields.Integer()
    device_info = fields.String()
    ip_address = fields.String()
    created_at = fields.DateTime(attribute="created_at")
    expires_at = fields.DateTime(attribute="expires_at")
