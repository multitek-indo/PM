#!/usr/bin/env python3
"""Safely register password rotation middleware in a source-only Git checkout.

Idempotent; does not touch databases or deploy services. Use before committing the
updated installer to GitHub. Requires the new middleware file to be present.
"""
from pathlib import Path
import ast
import os
import stat
import sys
import tempfile


def stop(message):
    raise SystemExit("STOP: " + message)


def main():
    root = Path(__file__).resolve().parent.parent
    cfg = root / "app/config/settings.py"
    auth = root / "app/config/first_login.py"
    urls = root / "app/config/urls.py"
    for path in (cfg, auth, urls):
        if path.is_symlink() or not path.is_file():
            stop("Source wajib tidak tersedia/berupa symlink: " + str(path))
    if "path('password/'," not in urls.read_text():
        stop("URL /password/ tidak sesuai source PM yang diperiksa")
    original = cfg.read_text(encoding="utf-8")
    literal = "'django.contrib.auth.middleware.AuthenticationMiddleware'"
    extra = "'config.first_login.EnforceInitialAdminPasswordChange'"
    if original.count(extra) == 1:
        print("PASS: middleware first-login sudah aktif; tidak perlu patch ulang")
        return
    if original.count(literal) != 1 or extra in original:
        stop("Deklarasi AuthenticationMiddleware tidak cocok; review manual sebelum patch")
    revised = original.replace(literal, literal + ", " + extra)
    ast.parse(revised, filename=str(cfg))
    ast.parse(auth.read_text(), filename=str(auth))
    original_mode = stat.S_IMODE(cfg.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix=".settings-pm-", dir=str(cfg.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(revised)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(tmp, original_mode)
        os.replace(tmp, cfg)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print("PASS: middleware wajib ganti password awal ditambahkan ke settings.py")


if __name__ == "__main__":
    main()
