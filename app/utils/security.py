"""
Password rules and upload size checks, shared by every route that takes
a password or a file. The limits live in app/config.py.
"""

import re

from flask import current_app


def password_problem(password):
    """
    What is wrong with a new password, as a message for the user.
    None when it is acceptable.
    """
    cfg = current_app.config
    low, high = cfg['PASSWORD_MIN_LENGTH'], cfg['PASSWORD_MAX_LENGTH']
    password = password or ''
    if len(password) < low:
        return f"Use at least {low} characters for the password."
    if len(password) > high:
        return f"Use at most {high} characters for the password."
    if not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        return "Use at least one letter and one number in the password."
    return None


def file_size(file_storage):
    """Size in bytes of an uploaded file, without consuming it."""
    stream = file_storage.stream
    here = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(here)
    return size


def upload_problem(files, max_files=None):
    """
    What is wrong with a set of uploaded files, as a message for the user.
    None when they are acceptable. Empty file inputs are ignored.
    """
    max_mb = current_app.config['MAX_UPLOAD_MB']
    chosen = [f for f in files if f and f.filename]

    if max_files is not None and len(chosen) > max_files:
        return f"Attach at most {max_files} files."

    too_big = [f.filename for f in chosen
               if file_size(f) > max_mb * 1024 * 1024]
    if too_big:
        return (f"Each file must be {max_mb} MB or smaller. Too big: "
                + ", ".join(too_big) + ".")
    return None
