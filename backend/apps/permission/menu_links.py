from django.core.exceptions import ValidationError
from django.core.validators import URLValidator


def is_valid_menu_link(value):
    if not value:
        return True
    try:
        URLValidator(schemes=["http", "https"])(value)
    except ValidationError:
        return False
    return True
