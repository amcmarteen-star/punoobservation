"""Profile details: optional full name and PH mobile number."""

import re

FULL_NAME_MAX = 120


def normalize_ph_mobile(raw):
    """'0917 123 4567', '0917-123-4567' or '+639171234567' -> '09171234567'.
    Empty -> ''. Anything else -> None (invalid)."""
    value = re.sub(r'[\s\-]', '', raw or '')
    if not value:
        return ''
    if value.startswith('+63'):
        value = '0' + value[3:]
    return value if re.fullmatch(r'09\d{9}', value) else None
