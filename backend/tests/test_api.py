import json

from laprak.ai import prompts
from laprak.crypto import decrypt_secret, encrypt_secret, new_wrapped_data_key, unwrap_data_key
from laprak.latex.build import detect_compiler
from laprak.latex.text import escape


def test_auth_required_and_csrf_header(client):
    client.cookies.clear()
    assert client.get("/api/projects").status_code == 401
    client.post("/api/auth/dev-login", json={"email": "b@example.com"})
    assert client.get("/api/projects").status_code == 200
    bare = client.post("/api/projects", json={"title": "x"}, headers={"x-laprak-client": ""})
    assert bare.status_code == 403


def test_crypto_roundtrip_and_tamper():
    master = b"m" * 32
    wrapped = new_wrapped_data_key(master, "user1")
    key = unwrap_data_key(master, wrapped, "user1")
    token = encrypt_secret(key, "sk-secret", "profile1")
    assert decrypt_secret(key, token, "profile1") == "sk-secret"
    try:
        decrypt_secret(key, token, "profile2")
        assert False, "aad mismatch must fail"
    except ValueError:
        pass
    try:
        unwrap_data_key(b"x" * 32, wrapped, "user1")
        assert False
    except ValueError:
        pass


def test_ai_profile_secret_never_in_listing(client, user):
    created = client.post("/api/ai-profiles", json={"name": "Router", "base_url": "http://localhost:20128/v1",
                                                     "text_model": "gpt-x", "api_key": "sk-123"})
    assert created.status_code == 201, created.text
    profile = created.json()
    assert "sk-123" not in json.dumps(profile) and "api_key_enc" not in profile and profile["has_api_key"]
    assert client.get(f"/api/ai-profiles/{profile['id']}/secret").json()["api_key"] == "sk-123"
    bad = client.post("/api/ai-profiles", json={"base_url": "http://example.com/v1"})
    assert bad.status_code == 422
    other = client.post("/api/auth/dev-login", json={"email": "intruder@example.com"})
    assert other.status_code == 200
    assert client.get(f"/api/ai-profiles/{profile['id']}/secret").status_code == 404


def test_project_steps_evidence_flow(client, project, png_bytes):
    pid = project["id"]
    step = client.post(f"/api/projects/{pid}/steps", json={"title": "Konfigurasi awal", "instruction": "Atur IP"}).json()
    second = client.post(f"/api/projects/{pid}/steps", json={"title": "Pengujian"}).json()
    upload = client.post(f"/api/projects/{pid}/evidence", data={"step_id": step["id"]},
                         files=[("files", ("a.png", png_bytes, "image/png")), ("files", ("b.png", png_bytes, "image/png"))])
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert len(body["created"]) == 1 and body["skipped"][0]["reason"] == "duplicate"
    evidence = body["created"][0]
    assert evidence["url"].startswith("/api/files/")
    assert client.get(evidence["url"]).status_code == 200
    assert client.get("/api/files/forged-token").status_code == 403

    reviewed = client.post(f"/api/steps/{step['id']}/review", json={"reviewed": True, "revision": 99})
    assert reviewed.status_code == 409
    current = client.get(f"/api/projects/{pid}/steps").json()[0]
    assert client.post(f"/api/steps/{step['id']}/review", json={"reviewed": True, "revision": current["revision"]}).json()["reviewed"]
    patched = client.patch(f"/api/steps/{step['id']}", json={"notes": "diperbaiki"}).json()
    assert patched["reviewed"] is False, "editing invalidates review"

    moved = client.patch(f"/api/evidence/{evidence['id']}", json={"step_id": second["id"]}).json()
    assert moved["step_id"] == second["id"]
    order = client.put(f"/api/projects/{pid}/steps/order", json={"ids": [second["id"], step["id"]]})
    assert [s["title"] for s in order.json()] == ["Pengujian", "Konfigurasi awal"]
    blockers = client.get(f"/api/projects/{pid}/blockers").json()
    assert any(b["target"] == "template" for b in blockers)
    bad = client.post(f"/api/projects/{pid}/evidence", data={}, files=[("files", ("x.png", b"notanimage", "image/png"))])
    assert bad.status_code == 415


def test_template_upload_detects_itera_and_creates_sections(client, project, template_zip):
    pid = project["id"]
    response = client.post(f"/api/projects/{pid}/template", files={"file": ("template.zip", template_zip, "application/zip")})
    assert response.status_code == 201, response.text
    template = response.json()
    assert template["status"] == "mapped" and template["engine"] == "xelatex"
    assert "documentation" in template["slot_map"]["slots"] and "main.tex" in template["files"]
    sections = client.get(f"/api/projects/{pid}/sections").json()
    assert {s["key"] for s in sections} >= {"theory", "tools", "summary"}
    text = client.get(f"/api/projects/{pid}/template/file", params={"path": "main.tex"}).json()
    assert "documentclass" in text["content"]
    assert client.get(f"/api/projects/{pid}/template/file", params={"path": "../../x"}).status_code == 400
    broken = dict(template["slot_map"], slots={})
    assert client.put(f"/api/projects/{pid}/template/slots", json={"slot_map": broken}).status_code == 422


def test_ai_prepare_complete_keeps_user_text(client, project, png_bytes):
    pid = project["id"]
    step = client.post(f"/api/projects/{pid}/steps", json={"title": "Ping", "instruction": "Uji ping"}).json()
    client.post(f"/api/projects/{pid}/evidence", data={"step_id": step["id"]}, files=[("files", ("p.png", png_bytes, "image/png"))])
    package = client.post(f"/api/projects/{pid}/ai/prepare", json={"operation": "analyze_evidence", "step_id": step["id"]})
    assert package.status_code == 200, package.text
    pkg = package.json()
    assert pkg["needs_vision"] and pkg["schema_name"] == "EvidenceAnalysis"
    assert any(part["type"] == "image" for part in pkg["messages"][0]["content"])
    assert "Bahasa Indonesia" in pkg["system"]

    raw = json.dumps({"facts": [{"type": "status", "value": "Reply from 10.0.0.1", "source": "visible", "reviewed": True}],
                      "narrative": "Ping berhasil.", "unknown": [], "result": "success"})
    done = client.post(f"/api/projects/{pid}/ai/complete", json={"operation": "analyze_evidence", "raw": raw, "target": pkg["target"]}).json()
    assert done["applied"] and done["content"]["facts"][0]["reviewed"] is False

    client.patch(f"/api/steps/{step['id']}", json={"narrative": "Tulisan saya sendiri."})
    pkg2 = client.post(f"/api/projects/{pid}/ai/prepare", json={"operation": "describe_step", "step_id": step["id"]}).json()
    done2 = client.post(f"/api/projects/{pid}/ai/complete", json={"operation": "describe_step", "target": pkg2["target"],
                                                                 "raw": json.dumps({"narrative": "Draf AI"})}).json()
    assert done2["applied"] is False
    assert client.get(f"/api/projects/{pid}/steps").json()[0]["narrative"] == "Tulisan saya sendiri."
    drafts = client.get(f"/api/projects/{pid}/drafts", params={"target_id": step["id"]}).json()
    assert len(drafts) == 2
    client.post(f"/api/drafts/{done2['draft']['id']}/apply", json={"field": "narrative"})
    assert client.get(f"/api/projects/{pid}/steps").json()[0]["narrative"] == "Draf AI"

    invalid = client.post(f"/api/projects/{pid}/ai/complete", json={"operation": "describe_step", "raw": "{not json", "target": {}})
    assert invalid.status_code == 422


def test_prompt_builder_language_and_validation():
    pkg = prompts.build("draft_section", "en", {"section": "Discussion", "steps": [{"id": "s1"}]})
    assert "formal English" in pkg.system and pkg.messages[0].content[0].text.startswith("Write the following report section")
    assert prompts.validate("draft_section", {"content": "ok", "sources": ["s1"]})["content"] == "ok"
    try:
        prompts.validate("draft_section", {"content": "x", "extra": 1})
        assert False
    except ValueError:
        pass


def test_latex_render_and_optional_build(client, project, template_zip, png_bytes, tmp_path):
    from laprak.latex.render import generate
    from laprak.latex.slots import ITERA_SLOT_MAP
    pid = project["id"]
    client.post(f"/api/projects/{pid}/template", files={"file": ("t.zip", template_zip, "application/zip")})
    step = client.post(f"/api/projects/{pid}/steps", json={"title": "Langkah & satu"}).json()
    client.post(f"/api/projects/{pid}/evidence", data={"step_id": step["id"]}, files=[("files", ("p.png", png_bytes, "image/png"))])
    client.patch(f"/api/steps/{step['id']}", json={"narrative": "Teks 100% aman.\n\n```\nping 10.0.0.1\n```"})
    from laprak.config import get_settings
    from laprak.deps import get_storage
    from laprak.service import snapshot
    from laprak.db import get_engine
    from laprak.models import Project
    from sqlmodel import Session
    storage = get_storage()
    with Session(get_engine(), expire_on_commit=False) as session:
        snap = snapshot(session, session.get(Project, pid))
    template_root = storage.path(snap["template"]["root"])
    workspace, main = generate(template_root, ITERA_SLOT_MAP, snap, storage.root, tmp_path)
    doc = (workspace / "generated" / "documentation.tex").read_text(encoding="utf-8")
    assert "Langkah \\& satu" in doc and "lstinputlisting" in doc and "Draf" in doc
    identity = (workspace / "generated" / "identity.tex").read_text(encoding="utf-8")
    assert "\\newcommand{\\judul}{Uji \\& Coba}" in identity and "A\\\\B" in identity
    assert "\\input{../generated/identity}" in main.read_text(encoding="utf-8")
    assert escape("a_b") == "a\\_b"

    compiler = detect_compiler("xelatex", get_settings().tex_compiler)
    if not compiler:
        return  # compile step only runs where a TeX distribution exists
    started = client.post(f"/api/projects/{pid}/builds")
    assert started.status_code == 202, started.text
    build = client.get(f"/api/projects/{pid}/builds/{started.json()['id']}").json()
    assert build["status"] in ("done", "failed"), build
    assert build["status"] == "done", build["error"]
    assert client.get(build["pdf_url"]).headers["content-type"] == "application/pdf"
