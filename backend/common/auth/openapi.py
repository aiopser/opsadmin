from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CustomJWTScheme(OpenApiAuthenticationExtension):
    target_class = "common.auth.jwt.JWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
