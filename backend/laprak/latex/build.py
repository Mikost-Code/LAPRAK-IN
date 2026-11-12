"""Sandboxed LaTeX compilation: separate argv, no shell escape, timeout, isolated output folder."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

WINDOWS_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/MiKTeX/miktex/bin/x64",
    Path("C:/Program Files/MiKTeX/miktex/bin/x64"),
    Path("D:/Mixtex/miktex/bin/x64"),
    Path("C:/texlive/2025/bin/windows"),
    Path("C:/texlive/2024/bin/windows"),
]


def detect_compiler(engine: str = "xelatex", manual: str = "") -> str:
    if manual:
        path = Path(manual)
        return str(path.resolve()) if path.is_file() else ""
    found = shutil.which(engine)
    if found:
        return found
    for folder in WINDOWS_CANDIDATES:
        for name in (f"{engine}.exe", f"miktex-{engine.replace('latex', 'tex')}.exe"):
            candidate = folder / name
            if candidate.is_file():
                return str(candidate)
    return ""


def run_process(args: list[str], cwd: Path, timeout: int = 120, extra_path: Path | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    # MiKTeX aborts when any PATH entry is not a directory; keep only real folders.
    entries = [p for p in env.get("PATH", "").split(os.pathsep) if p and Path(p).is_dir()]
    if extra_path:
        entries.insert(0, str(extra_path))
    env["PATH"] = os.pathsep.join(dict.fromkeys(entries))
    env["max_print_line"] = "1000"
    try:
        completed = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=timeout, env=env, shell=False, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, f"Kompilasi melebihi batas waktu {timeout} detik."
    except OSError as error:
        return 127, f"Compiler tidak dapat dijalankan: {error}"
    return completed.returncode, completed.stdout + completed.stderr


def engine_args(compiler: str, engine: str, output: Path, main: Path) -> list[str]:
    args = [compiler]
    if Path(compiler).name.lower().startswith("miktex-"):
        fmt = {"xelatex": "xelatex", "lualatex": "lualatex", "pdflatex": "pdflatex"}[engine]
        args += [f"--undump={fmt}"]
    return args + ["-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", f"-output-directory={output}", str(main)]


def diagnosis(log: str) -> str:
    low = log.lower()
    if "not found" in low and ("font" in low or "fontspec" in low):
        return "Font template tidak ditemukan di server. Periksa peta font atau pakai font pengganti."
    if re.search(r"file .+\.sty.+not found", low):
        return "Paket LaTeX yang dibutuhkan template belum terpasang di server."
    if "not found" in low:
        return "Berkas/aset template tidak ditemukan. Periksa kelengkapan template."
    if "undefined control sequence" in low:
        return "Perintah LaTeX tidak dikenal. Periksa slot identitas dan isi template."
    if "melebihi batas waktu" in low:
        return "Kompilasi terlalu lama dan dihentikan."
    return "Kompilasi gagal. Periksa detail log."


def compile_workspace(main: Path, engine: str, compiler: str, timeout: int = 180) -> tuple[Path, str]:
    if not compiler:
        raise RuntimeError("Compiler LaTeX tidak ditemukan di server. Atur LAPRAK_TEX_COMPILER.")
    output = main.parent.parent / "pdf"
    output.mkdir(exist_ok=True)
    latexmk = shutil.which("latexmk")
    standard = Path(compiler).name.lower() in (engine, engine + ".exe")
    if latexmk and standard:
        mode = {"xelatex": "-xelatex", "lualatex": "-lualatex", "pdflatex": "-pdf"}[engine]
        commands = [[latexmk, mode, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", f"-outdir={output}", str(main)]]
    else:
        commands = [engine_args(compiler, engine, output, main)] * 2
    logs = []
    for command in commands:
        code, log = run_process(command, main.parent, timeout, Path(compiler).parent)
        logs.append(log)
        if code:
            raise RuntimeError(diagnosis(log) + "\n\n" + log[-8000:])
    pdf = output / (main.stem + ".pdf")
    if not pdf.is_file():
        raise RuntimeError("Compiler selesai tanpa menghasilkan PDF.\n\n" + logs[-1][-4000:])
    return pdf, "\n".join(logs)


def check_environment(compiler: str, engine: str, scratch: Path) -> dict:
    if not compiler:
        raise RuntimeError("Compiler LaTeX tidak ditemukan.")
    scratch.mkdir(parents=True, exist_ok=True)
    code, version = run_process([compiler, "--version"], scratch, 30)
    if code:
        raise RuntimeError("Pemeriksaan versi compiler gagal.")
    probe = scratch / "probe.tex"
    probe.write_text("\\documentclass{article}\n\\begin{document}Laprak compiler check.\\end{document}\n", encoding="utf-8")
    code, log = run_process(engine_args(compiler, engine, scratch, probe), scratch, 90, Path(compiler).parent)
    if code:
        raise RuntimeError(diagnosis(log) + "\n\n" + log[-4000:])
    return {"compiler": compiler, "engine": engine, "version": version.splitlines()[0] if version else ""}
