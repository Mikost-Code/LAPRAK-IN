from pathlib import Path

from pypdf import PdfReader


def extract_module(path: Path, max_mb=50, max_pages=200):
    if path.stat().st_size > max_mb * 1024**2:
        raise ValueError(f"PDF melebihi batas {max_mb} MB.")
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("PDF terenkripsi. Gunakan salinan tanpa password.")
    if not 0 < len(reader.pages) <= max_pages:
        raise ValueError(f"PDF harus berisi 1–{max_pages} halaman.")
    pages = []
    for number, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if contents and len(contents.get_data()) > 20 * 1024**2:
            raise ValueError(f"Konten halaman {number} terlalu besar. Optimalkan PDF dahulu.")
        text = page.extract_text() or ""
        pages.append({"page": number, "printed_page": None, "text": text, "needs_vision": len(text.strip()) < 20})
    return pages


def render_pages(path, pages, directory, cancel):
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtPdf import QPdfDocument
    document = QPdfDocument()
    error = document.load(str(path))
    if error != QPdfDocument.Error.None_:
        raise ValueError("PDF tidak dapat dirender untuk vision.")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        for page in pages:
            if cancel.is_set():
                raise RuntimeError("Ekstraksi dibatalkan.")
            size = document.pagePointSize(page["page"]-1)
            image = document.render(page["page"]-1, QSize(1200, int(1200 * size.height()/size.width())))
            white = QImage(image.size(), QImage.Format.Format_RGB32)
            white.fill(0xffffffff)
            painter = QPainter(white)
            painter.drawImage(0, 0, image)
            painter.end()
            target = directory / f"page-{page['page']:04}.png"
            if image.isNull() or not white.save(str(target)):
                raise ValueError(f"Halaman {page['page']} gagal dirender.")
            page["image_path"] = target
    finally:
        document.close()
