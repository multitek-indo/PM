"""Read the one application version source. No network or database calls."""
from pathlib import Path
import re


def read_version(path=None):
    value = (path or Path(__file__).resolve().parent.parent / 'VERSION.txt').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise ValueError('VERSION.txt harus berformat MAJOR.MINOR.PATCH, contoh 0.3.0.')
    return value


APP_VERSION = read_version()
