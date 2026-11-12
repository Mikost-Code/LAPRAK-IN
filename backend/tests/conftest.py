import io
import os
import tempfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEMP = tempfile.mkdtemp(prefix="laprak-test-")
os.environ.update({
    "LAPRAK_DATA_DIR": TEMP,
    "LAPRAK_DEV_LOGIN": "1",
    "LAPRAK_DATABASE_URL": "sqlite:///" + (Path(TEMP) / "test.sqlite").as_posix(),
    "LAPRAK_SECRET_KEY": "test-secret",
    "LAPRAK_MASTER_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
})

from fastapi.testclient import TestClient  # noqa: E402

from laprak.main import app  # noqa: E402

HEADERS = {"x-laprak-client": "1"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        c.headers.update(HEADERS)
        yield c


@pytest.fixture
def user(client):
    response = client.post("/api/auth/dev-login", json={"email": "a@example.com", "name": "Tester"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def project(client, user):
    response = client.post("/api/projects", json={"title": "Laporan uji", "language": "id",
                                                  "identity": {"name": "Mahasiswa", "nim": "123", "title": "Uji & Coba", "members": "A\nB"}})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def png_bytes():
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (120, 60), "white").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def template_zip():
    source = ROOT / "template"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in source.rglob("*"):
            if path.is_file() and path.suffix.lower() not in (".pdf", ".log", ".aux", ".synctex.gz"):
                zf.write(path, path.relative_to(source).as_posix())
    return buffer.getvalue()
