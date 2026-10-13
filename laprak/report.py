from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from threading import Event

from jinja2 import Environment, StrictUndefined

from .storage import inside, uid

ESCAPES = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape(text):
    return "".join(ESCAPES.get(char, char) for char in str(text))


def paragraphs(text):
    return "\n\n".join(escape(part.strip()).replace("\n", " ") for part in text.split("\n\n"))


def body(text, generated):
    pieces = re.split(r"(```[^\n]*\n.*?```)", text, flags=re.DOTALL)
    result = []
    for piece in pieces:
        if piece.startswith("```") and piece.endswith("```"):
            code = piece.split("\n", 1)[1][:-3]
            filename = "cli-" + uid() + ".txt"
            (generated / filename).write_text(code, encoding="utf-8")
            result.append("\\lstinputlisting[basicstyle=\\ttfamily\\footnotesize,breaklines=true,columns=fullflexible]{../generated/" + filename + "}")
        else:
            result.append(paragraphs(piece))
    return "\n\n".join(result)


ENV = Environment(variable_start_string="((*", variable_end_string="*))", block_start_string="(%", block_end_string="%)",
                  comment_start_string="(#", comment_end_string="#)", undefined=StrictUndefined, autoescape=False)
ENV.filters["tex"] = escape

ITERA_FIELDS = {"namapeserta": "name", "nim": "nim", "kelas": "class", "judul": "title", "pertemuan": "meeting",
                "bulantahun": "month_year", "asistenA": "assistant_a", "asistenB": "assistant_b", "daftaranggota": "members"}


def detect_compiler(engine="xelatex", manual=""):
    if manual:
        path = Path(manual)
        return str(path.resolve()) if path.is_file() else ""
    standard = shutil.which(engine)
    if standard:
        return standard
    binary = {"xelatex": "miktex-xetex.exe", "lualatex": "miktex-luatex.exe", "pdflatex": "miktex-pdftex.exe"}[engine]
    roots = [Path("D:/Mixtex/miktex/bin/x64"), Path("C:/Program Files/MiKTeX/miktex/bin/x64"),
             Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MiKTeX/miktex/bin/x64"]
    roots += list(Path("C:/texlive").glob("*/bin/windows")) if Path("C:/texlive").exists() else []
    for root in roots:
        for name in (f"{engine}.exe", binary):
            if (root / name).is_file():
                return str(root / name)
    return ""


def run_process(args, cwd, cancel, timeout=90, extra_path=None):
    if cancel.is_set():
        raise RuntimeError("Build dibatalkan.")
    environment = dict(os.environ)
    # TeX distributions may reject PATH entries which point to files.
    paths = ([str(extra_path)] if extra_path else []) + [str(Path(args[0]).parent)] + [p for p in environment.get("PATH", "").split(os.pathsep) if Path(p).is_dir()]
    environment["PATH"] = os.pathsep.join(paths)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env=environment, creationflags=flags)
    started = time.monotonic()
    while True:
        try:
            output, _ = process.communicate(timeout=0.2)
            break
        except subprocess.TimeoutExpired:
            if cancel.is_set() or time.monotonic()-started > timeout:
                process.kill()
                process.communicate()
                raise RuntimeError("Build dibatalkan." if cancel.is_set() else "Compiler timeout. Periksa paket/font lalu coba ulang.")
    if cancel.is_set():
        raise RuntimeError("Build dibatalkan.")
    return process.returncode, output.decode("utf-8", errors="replace")


def engine_args(compiler, engine, output, main):
    args = [compiler]
    if Path(compiler).name.startswith("miktex-"):
        args += ["--disable-installer", f"--undump={engine}"]
    return args + ["-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
                   f"-output-directory={output}", str(main)]


def diagnosis(log):
    if "not found" in log and ("font" in log.lower() or "fontspec" in log):
        return "Font template tidak ditemukan. Pasang font yang disebutkan pada log."
    if re.search(r"File .+\.sty.+not found", log):
        return "Paket LaTeX hilang. Pasang paket melalui distribusi TeX, lalu Periksa Ulang."
    if "not found" in log:
        return "File/aset template tidak ditemukan. Periksa kelengkapan template."
    return "Kompilasi gagal. Periksa sintaks dan detail log."


def validate_template(source: Path):
    main = source / "main.tex"
    if not main.is_file():
        raise ValueError("Template harus memiliki main.tex.")
    manifest_path = source / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for key in ("main", "engine", "identity_fields", "slots"):
            if key not in manifest:
                raise ValueError(f"Manifest belum memiliki {key}.")
        inside(source, manifest["main"])
        for path in manifest["slots"].values():
            inside(source, path)
        if manifest["engine"] not in ("xelatex", "lualatex", "pdflatex"):
            raise ValueError("Engine template tidak didukung.")
        return manifest
    content = main.read_text(encoding="utf-8")
    if "\\input{data/identitas}" in content and "\\input{isi/dokumentasi}" in content and "ITERA" in content:
        return {"schema_version": 1, "name": "ITERA Jaringan Komputer B5", "main": "main.tex", "engine": "xelatex",
                "identity_fields": ITERA_FIELDS, "identity_inputs": ["data/identitas", "data/kelas", "data/asisten", "data/anggota-kelompok", "data/laporan"],
                "slots": {"documentation": "isi/dokumentasi.tex", "theory": "isi/dasar-teori.tex", "tools": "isi/alat-dan-bahan.tex",
                          "tasks": "isi/tugas.tex", "references": "isi/referensi.tex", "summary": "isi/rangkuman.tex"},
                "required_assets": ["aset/gambar/logo-itera.png", "aset/gambar/logo-fti.png", "aset/gambar/logo-if.png"]}
    raise ValueError("Template belum diadaptasi. Tambahkan manifest.json sesuai panduan README.")


def copy_template(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.is_relative_to(source):
        raise ValueError("Pilih template di luar folder salinan sesi.")
    manifest = validate_template(source)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Salinan template sesi sudah ada. Buat sesi baru untuk mengganti template.")
    ignore = shutil.ignore_patterns("build", ".vscode", ".git", "*.pdf", "*.log", "*.aux", "*.synctex.gz", "__pycache__")
    shutil.copytree(source, destination, dirs_exist_ok=True, ignore=ignore)
    for asset in manifest.get("required_assets", []):
        if not inside(destination, asset).is_file():
            raise ValueError(f"Aset wajib hilang: {asset}")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def check_environment(compiler, engine, template, build, cancel):
    if not compiler:
        raise ValueError("Executable compiler tidak ditemukan. Pilih lokasi manual atau pasang MiKTeX/TeX Live.")
    build = Path(build)
    build.mkdir(parents=True, exist_ok=True)
    code, version = run_process([compiler, "--version"], template, cancel, 30)
    if code:
        raise ValueError("Pemeriksaan versi compiler gagal.")
    probe = build / "probe.tex"
    probe.write_text("\\documentclass{article}\n\\begin{document}Laprak compiler check.\\end{document}", encoding="utf-8")
    code, log = run_process(engine_args(compiler, engine, build, probe), template, cancel)
    if code:
        raise RuntimeError(diagnosis(log) + "\n\n" + log[-6000:])
    manifest = validate_template(Path(template))
    code, log = run_process(engine_args(compiler, engine, build, inside(Path(template), manifest["main"])), template, cancel)
    (build / "check.log").write_text(log, encoding="utf-8")
    if code:
        raise RuntimeError(diagnosis(log) + "\n\n" + log[-6000:])
    return {"version": version.splitlines()[0], "compiler": compiler, "engine": engine}


def generate(root: Path, snapshot):
    """Build from a snapshot; never overwrite the source template or last successful PDF."""
    template = root / "template"
    manifest = validate_template(template)
    workspace = root / "build" / uid()
    workspace.mkdir(parents=True)
    shutil.copytree(template, workspace / "template")
    work_template = workspace / "template"
    generated = workspace / "generated"
    generated.mkdir()
    evidence_root = workspace / "screenshots"
    evidence_root.mkdir()
    identity = snapshot["identity"]
    fields = manifest["identity_fields"]
    lines = []
    for command, field in fields.items():
        if not re.fullmatch(r"[A-Za-z]+", command):
            raise ValueError("Nama command identitas harus berupa huruf.")
        value = identity.get(field, "")
        value = r"\\".join(escape(line) for line in value.splitlines()) if field == "members" else escape(value)
        lines.append(f"\\newcommand{{\\{command}}}{{{value}}}")
    (generated / "identity.tex").write_text("\n".join(lines), encoding="utf-8")
    main = inside(work_template, manifest["main"])
    content = main.read_text(encoding="utf-8")
    content = content.replace(r"\begin{document}", "\\usepackage{listings}\n\\begin{document}")
    inputs = manifest.get("identity_inputs", [])
    for index, value in enumerate(inputs):
        needle = "\\input{" + value + "}"
        content = content.replace(needle, "\\input{../generated/identity}" if index == 0 else "% identity generated")
    if not inputs:
        content = content.replace("% LAPRAK_IDENTITY", "\\input{../generated/identity}")
    main.write_text(content, encoding="utf-8")
    documentation = [r"\section{Dokumentasi Praktikum}"]
    for index, step in enumerate(snapshot["steps"], 1):
        documentation += [f"\\subsection{{{index}. {escape(step['title'])}}}"]
        if not step["reviewed"]:
            documentation += [r"\textbf{Draf: isi belum diperiksa.}\par"]
        if step.get("not_applicable"):
            documentation += ["Tidak berlaku: " + paragraphs(step["not_applicable"])]
        documentation += [body(step["narrative"], generated)]
        if step["notes"]:
            documentation += ["\\par\\textit{Catatan pengguna:} " + body(step["notes"], generated)]
        for evidence in [e for e in snapshot["evidence"] if e["step_id"] == step["id"]]:
            source = inside(root, evidence["path"])
            safe_name = evidence["id"] + source.suffix.lower()
            shutil.copy2(source, evidence_root / safe_name)
            documentation += [r"\begin{figure}[htbp]\centering",
                              f"\\includegraphics[width=\\linewidth,height=0.65\\textheight,keepaspectratio]{{../screenshots/{safe_name}}}",
                              f"\\caption{{{escape(evidence['name'])}}}", r"\end{figure}"]
            # Flush per image: TeX cannot queue 50 floats from one step without hitting dead cycles.
            documentation += [r"\clearpage"]
        documentation += [r"\clearpage"]
    documentation += [r"\section{Pembahasan}", body(snapshot.get("discussion", ""), generated),
                      r"\section{Kesimpulan}", body(snapshot.get("conclusion", ""), generated)]
    texts = {"documentation": "\n\n".join(documentation), "theory": "\\section{Dasar Teori}\n" + body(snapshot.get("theory", ""), generated),
             "tools": "\\section{Alat dan Bahan}\n" + body(snapshot.get("tools", ""), generated),
             "tasks": "\\section{Tugas}\n" + body(snapshot.get("tasks", ""), generated),
             "references": "\\section{Referensi}\n" + body(snapshot.get("references", ""), generated),
             "summary": "\\section{Rangkuman Praktikum}\n" + body(snapshot.get("summary", ""), generated)}
    for key, slot in manifest["slots"].items():
        if key not in texts:
            continue
        output = generated / f"{key}.tex"
        rendered = ENV.from_string("((* content *))").render(content=texts[key])
        output.write_text(rendered, encoding="utf-8")
        target = inside(work_template, slot)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"\\input{{../generated/{key}}}\n", encoding="utf-8")
    # Portable generated sources match copied template-relative paths in exports.
    shutil.copytree(generated, root / "generated", dirs_exist_ok=True)
    return workspace, main, manifest


def build_report(root, snapshot, compiler, cancel):
    workspace, main, manifest = generate(Path(root), snapshot)
    output = workspace / "pdf"
    output.mkdir()
    logs = []
    latexmk = shutil.which("latexmk")
    standard_engine = Path(compiler).name.lower() in (manifest["engine"], manifest["engine"] + ".exe")
    if latexmk and standard_engine:
        mode = {"xelatex": "-xelatex", "lualatex": "-lualatex", "pdflatex": "-pdf"}[manifest["engine"]]
        commands = [[latexmk, mode, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={output}", str(main)]]
    else:
        # Direct engine fallback for installations without latexmk/standard launchers.
        commands = [engine_args(compiler, manifest["engine"], output, main)] * 2
    for command in commands:
        code, log = run_process(command, main.parent, cancel, 120, Path(compiler).parent)
        logs.append(log)
        (workspace / "compiler.log").write_text("\n".join(logs), encoding="utf-8")
        if code:
            raise RuntimeError(diagnosis(log) + "\n\n" + log[-6000:])
    pdf = output / (main.stem + ".pdf")
    if not pdf.is_file():
        raise RuntimeError("Compiler selesai tanpa menghasilkan PDF.")
    return {"pdf": str(pdf), "revision": snapshot["revision"], "workspace": str(workspace)}
