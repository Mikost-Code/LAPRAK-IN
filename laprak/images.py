import shutil
from pathlib import Path

from PIL import Image

from .storage import digest, inside, uid


def prepare_image(root, path, cancel):
    if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise ValueError("Bukti harus berformat PNG atau JPEG.")
    for attempt in range(5):
        try:
            with Image.open(path) as image:
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError("Isi file bukan PNG/JPEG.")
                image.verify()
            break
        except OSError:
            if attempt == 4 or cancel.wait(0.3):
                raise
    file_hash = digest(path)
    if cancel.is_set():
        raise RuntimeError("Impor dibatalkan.")
    evidence_id = uid()
    relative = f"screenshots/originals/{evidence_id}{path.suffix.lower()}"
    shutil.copy2(path, inside(root, relative))
    if digest(inside(root, relative)) != file_hash:
        inside(root, relative).unlink(missing_ok=True)
        raise ValueError("Gambar berubah saat diimpor. Tunggu file selesai ditulis dan impor ulang.")
    return {"id": evidence_id, "hash": file_hash, "path": relative, "name": path.name}


def derivative(root, source_relative, rect=None, maximum=None):
    source = inside(root, source_relative)
    target = f"screenshots/derived/{uid()}.png"
    with Image.open(source) as image:
        image.load()
        if rect:
            x, y, width, height = rect
            if min(x, y) < 0 or min(width, height) < 1 or x+width > image.width or y+height > image.height:
                raise ValueError("Area crop harus berada di dalam gambar asli.")
            image = image.crop((x, y, x+width, y+height))
        if maximum:
            image.thumbnail((maximum, maximum))
        image.save(inside(root, target))
    return target
