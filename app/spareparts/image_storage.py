"""Private storage for sanitized JPEG copies. Files are NOT served by WhiteNoise."""
import io
import os
import re
import uuid
import shutil
from pathlib import Path
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PIXELS = 24_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_ALLOWED = {'JPEG', 'PNG', 'WEBP'}
_NAME = re.compile(r'^[0-9a-f]{32}\.jpg$')


def media_root():
    return Path(getattr(settings, 'PM_SPAREPART_STORAGE_DIR', '/var/pm-spareparts'))


def normalize_image(upload):
    """Validate the decoded image and re-encode without EXIF/GPS metadata."""
    if upload.size > 6 * 1024 * 1024:
        raise ValidationError('Foto tidak boleh melebihi 6 MB.')
    try:
        upload.seek(0)
        with Image.open(upload) as img:
            if img.format not in _ALLOWED:
                raise ValidationError('Hanya JPG, PNG, dan WEBP yang diperbolehkan.')
            if img.width * img.height > MAX_PIXELS or img.width < 1 or img.height < 1:
                raise ValidationError('Dimensi foto melebihi batas 24 megapiksel.')
            img.verify()
        upload.seek(0)
        with Image.open(upload) as img:
            img.load()
            img = ImageOps.exif_transpose(img)
            img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            # Preserve transparency on white; all stored files become JPEG.
            if img.mode in ('RGBA', 'LA') or ('transparency' in img.info):
                rgba = img.convert('RGBA')
                bg = Image.new('RGB', rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.getchannel('A'))
                img = bg
            else:
                img = img.convert('RGB')
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=83, optimize=True)
            data = buf.getvalue()
        if not data or len(data) > 6 * 1024 * 1024:
            raise ValidationError('Foto gagal dikompresi hingga batas ukuran.')
        return data
    except ValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError, SyntaxError) as err:
        raise ValidationError('Foto tidak valid atau tidak dapat dibaca.') from err


def save_private(data):
    root = media_root()
    if not root.is_dir() or root.is_symlink():
        raise OSError('Folder foto privat tidak tersedia.')
    if shutil.disk_usage(root).free < 10 * 1024 * 1024 * 1024:
        raise OSError('Ruang disk untuk foto sudah di bawah batas aman 10 GiB.')
    name = uuid.uuid4().hex + '.jpg'
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        (root / name).unlink(missing_ok=True)
        raise
    return name


def open_private(name):
    if not _NAME.fullmatch(name):
        raise FileNotFoundError('Nama file tidak valid.')
    root = media_root()
    return os.fdopen(os.open(root / name, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)), 'rb')


def remove_private(name):
    if _NAME.fullmatch(name):
        (media_root() / name).unlink(missing_ok=True)
