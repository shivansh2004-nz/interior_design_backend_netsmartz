# import os
# import sys
# import uuid
# import shutil
# import subprocess
# from pathlib import Path
# from typing import List, Tuple

# from .settings import settings


# def _ensure_dirs():
#     Path(settings.STORAGE_DIR, "uploads").mkdir(parents=True, exist_ok=True)
#     Path(settings.STORAGE_DIR, "runs").mkdir(parents=True, exist_ok=True)


# def new_run_dir() -> Path:
#     _ensure_dirs()
#     run_id = uuid.uuid4().hex
#     run_dir = Path(settings.STORAGE_DIR, "runs", run_id)
#     run_dir.mkdir(parents=True, exist_ok=True)
#     return run_dir


# def save_upload(file_bytes: bytes, filename: str, run_dir: Path) -> Path:
#     uploads = Path(settings.STORAGE_DIR, "uploads")
#     uploads.mkdir(parents=True, exist_ok=True)
#     safe_name = filename.replace("\\", "_").replace("/", "_")
#     dst = uploads / f"{uuid.uuid4().hex}_{safe_name}"
#     dst.write_bytes(file_bytes)
#     return dst


# # def _run_subprocess(cmd: list[str], cwd: Path, env: dict) -> str:
# #     """
# #     Run subprocess and return combined stdout+stderr.
# #     Useful because some of your pipeline modules print errors but exit 0.
# #     """
# #     print("\n[RUNNER] Using python:", sys.executable)
# #     print("[RUNNER] CWD:", str(cwd))
# #     print("[RUNNER] CMD:", " ".join(cmd))

# #     proc = subprocess.run(
# #         cmd,
# #         cwd=str(cwd),
# #         env=env,
# #         text=True,
# #         capture_output=True,
# #         encoding="utf-8",
# #         errors="replace",
# #     )

# #     combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
# #     # still raise if non-zero exit
# #     if proc.returncode != 0:
# #         raise RuntimeError(f"Pipeline crashed (exit={proc.returncode}). Output:\n{combined}")

# #     # print last part for debugging
# #     tail = combined[-2000:] if len(combined) > 2000 else combined
# #     print("[RUNNER] Pipeline output (tail):\n", tail)
# #     return combined

# def _run_subprocess(cmd: list[str], cwd: Path, env: dict) -> str:
#     """
#     Stream subprocess logs live to terminal AND return combined logs.
#     Works well on Windows (utf-8 decode with errors='replace').
#     """
#     print("\n[RUNNER] Using python:", sys.executable)
#     print("[RUNNER] CWD:", str(cwd))
#     print("[RUNNER] CMD:", " ".join(cmd))

#     # Start process
#     proc = subprocess.Popen(
#         cmd,
#         cwd=str(cwd),
#         env=env,
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,   # merge stderr into stdout
#         text=True,
#         encoding="utf-8",
#         errors="replace",
#         bufsize=1,                 # line-buffered
#         universal_newlines=True,
#     )

#     logs: list[str] = []

#     assert proc.stdout is not None
#     for line in proc.stdout:
#         logs.append(line)
#         # print live (no extra newline because `line` already has one)
#         print(line, end="")

#     rc = proc.wait()
#     combined = "".join(logs)

#     if rc != 0:
#         raise RuntimeError(f"Pipeline crashed (exit={rc}). Output:\n{combined}")

#     return combined

# def _pipeline_env() -> dict:
#     env = os.environ.copy()
#     if settings.COHERE_API_KEY:
#         env["COHERE_API_KEY"] = settings.COHERE_API_KEY
#     if settings.KIE_API_KEY:
#         env["KIE_API_KEY"] = settings.KIE_API_KEY
#     if settings.CLOUDINARY_CLOUD_NAME:
#         env["CLOUDINARY_CLOUD_NAME"] = settings.CLOUDINARY_CLOUD_NAME
#     if settings.CLOUDINARY_API_KEY:
#         env["CLOUDINARY_API_KEY"] = settings.CLOUDINARY_API_KEY
#     if settings.CLOUDINARY_API_SECRET:
#         env["CLOUDINARY_API_SECRET"] = settings.CLOUDINARY_API_SECRET
#     return env


# def run_pipeline1(
#     room_image_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     run_dir: Path,
# ) -> Path:
#     """
#     Runs Pipeline-1 and copies the newest generated_images/*.png to run_dir/result.png
#     """
#     env = _pipeline_env()
#     p1 = Path(settings.PIPELINE1_DIR).resolve()

#     room_abs = Path(room_image_path).resolve()  # ✅ IMPORTANT: absolute path
#     cmd = [
#         sys.executable,
#         "main.py",
#         "--room_image",
#         str(room_abs),
#         "--room_type",
#         room_type,
#         "--dimensions",
#         dimensions,
#         "--style",
#         style,
#         "--budget",
#         budget,
#     ]

#     output = _run_subprocess(cmd, cwd=p1, env=env)

#     # If your pipeline prints an explicit error but exits 0, treat as failure.
#     if "[ERROR]" in output or "Upload failed" in output:
#         raise RuntimeError(f"Pipeline-1 reported an error in logs:\n{output}")

#     gen_dir = p1 / "generated_images"
#     candidates = sorted(gen_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
#     if not candidates:
#         raise RuntimeError("Pipeline-1 finished but no output png found in generated_images/")

#     out = candidates[0]
#     dst = run_dir / "result.png"
#     shutil.copy2(out, dst)
#     return dst


# def run_pipeline2(room_image_path: Path, items: List[Tuple[str, Path]], run_dir: Path) -> Path:
#     """
#     Runs Pipeline-2 and copies the newest generated_images/*.png to run_dir/result.png
#     """
#     env = _pipeline_env()
#     p2 = Path(settings.PIPELINE2_DIR).resolve()

#     room_abs = Path(room_image_path).resolve()  # ✅ IMPORTANT: absolute path
#     items_args = [f"{name}={str(Path(path).resolve())}" for name, path in items]  # ✅ absolute paths

#     cmd = [
#         sys.executable,
#         "main_user_assets.py",
#         "--room_image",
#         str(room_abs),
#         "--items",
#         *items_args,
#     ]

#     output = _run_subprocess(cmd, cwd=p2, env=env)

#     if "[ERROR]" in output or "Upload failed" in output:
#         raise RuntimeError(f"Pipeline-2 reported an error in logs:\n{output}")

#     gen_dir = p2 / "generated_images"
#     candidates = sorted(gen_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
#     if not candidates:
#         raise RuntimeError("Pipeline-2 finished but no output png found in generated_images/")

#     out = candidates[0]
#     dst = run_dir / "result.png"
#     shutil.copy2(out, dst)
#     return dst

import os
import sys
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from .settings import settings


def _ensure_dirs():
    Path(settings.STORAGE_DIR, "uploads").mkdir(parents=True, exist_ok=True)
    Path(settings.STORAGE_DIR, "runs").mkdir(parents=True, exist_ok=True)


def new_run_dir() -> Path:
    _ensure_dirs()
    run_id = uuid.uuid4().hex
    run_dir = Path(settings.STORAGE_DIR, "runs", run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_upload(file_bytes: bytes, filename: str, run_dir: Path) -> Path:
    uploads = Path(settings.STORAGE_DIR, "uploads")
    uploads.mkdir(parents=True, exist_ok=True)
    safe_name = filename.replace("\\", "_").replace("/", "_")
    dst = uploads / f"{uuid.uuid4().hex}_{safe_name}"
    dst.write_bytes(file_bytes)
    return dst


def _pipeline_env() -> dict:
    env = os.environ.copy()

    # ✅ Force unbuffered output from child Python scripts
    env["PYTHONUNBUFFERED"] = "1"

    if settings.COHERE_API_KEY:
        env["COHERE_API_KEY"] = settings.COHERE_API_KEY
    if settings.KIE_API_KEY:
        env["KIE_API_KEY"] = settings.KIE_API_KEY
    if settings.CLOUDINARY_CLOUD_NAME:
        env["CLOUDINARY_CLOUD_NAME"] = settings.CLOUDINARY_CLOUD_NAME
    if settings.CLOUDINARY_API_KEY:
        env["CLOUDINARY_API_KEY"] = settings.CLOUDINARY_API_KEY
    if settings.CLOUDINARY_API_SECRET:
        env["CLOUDINARY_API_SECRET"] = settings.CLOUDINARY_API_SECRET

    return env


def _run_subprocess(cmd: list[str], cwd: Path, env: dict) -> str:
    """
    Stream logs live to terminal AND return combined output.
    Works on Windows by forcing UTF-8 decode with errors='replace'.
    """
    print("\n[RUNNER] Using python:", sys.executable, flush=True)
    print("[RUNNER] CWD:", str(cwd), flush=True)
    print("[RUNNER] CMD:", " ".join(cmd), flush=True)

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # merge stderr into stdout
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,  # line-buffered
    )

    logs: list[str] = []
    assert proc.stdout is not None

    for line in iter(proc.stdout.readline, ""):
        if not line:
            break
        logs.append(line)
        print(line, end="", flush=True)  # ✅ live streaming

    proc.stdout.close()
    rc = proc.wait()

    combined = "".join(logs)

    if rc != 0:
        raise RuntimeError(f"Pipeline crashed (exit={rc}). Output:\n{combined}")

    return combined


def run_pipeline1(
    room_image_path: Path,
    room_type: str,
    dimensions: str,
    style: str,
    budget: str,
    run_dir: Path,
) -> Path:
    env = _pipeline_env()
    p1 = Path(settings.PIPELINE1_DIR).resolve()

    room_abs = Path(room_image_path).resolve()

    # ✅ -u forces unbuffered stdout/stderr from Python child process
    cmd = [
        sys.executable,
        "-u",
        "main.py",
        "--room_image",
        str(room_abs),
        "--room_type",
        room_type,
        "--dimensions",
        dimensions,
        "--style",
        style,
        "--budget",
        budget,
    ]

    output = _run_subprocess(cmd, cwd=p1, env=env)

    # If your pipeline prints an explicit error but exits 0, treat as failure.
    if "[ERROR]" in output or "Upload failed" in output:
        raise RuntimeError(f"Pipeline-1 reported an error in logs:\n{output}")

    gen_dir = p1 / "generated_images"
    candidates = sorted(gen_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("Pipeline-1 finished but no output png found in generated_images/")

    out = candidates[0]
    dst = run_dir / "result.png"
    shutil.copy2(out, dst)
    return dst


def run_pipeline1_custom(
    room_image_path: Path,
    room_type: str,
    dimensions: str,
    style: str,
    budget: str,
    furnitures: list[str],
    run_dir: Path,
) -> Path:
    env = _pipeline_env()
    p1c = Path(settings.PIPELINE1_CUSTOM_DIR).resolve()

    room_abs = Path(room_image_path).resolve()
    cmd = [
        sys.executable,
        "-u",
        "main.py",
        "--room_image",
        str(room_abs),
        "--room_type",
        room_type,
        "--dimensions",
        dimensions,
        "--style",
        style,
        "--budget",
        budget,
        "--user_furnitures",
        ",".join(furnitures),
    ]

    output = _run_subprocess(cmd, cwd=p1c, env=env)

    # If your pipeline prints an explicit error but exits 0, treat as failure.
    if "[ERROR]" in output or "Upload failed" in output:
        raise RuntimeError(f"Pipeline-1-Custom reported an error in logs:\n{output}")

    gen_dir = p1c / "generated_images"
    candidates = sorted(gen_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("Pipeline-1-Custom finished but no output png found in generated_images/")

    out = candidates[0]
    dst = run_dir / "result.png"
    shutil.copy2(out, dst)
    return dst


def run_pipeline2(room_image_path: Path, items: List[Tuple[str, Path]], run_dir: Path) -> Path:
    env = _pipeline_env()
    p2 = Path(settings.PIPELINE2_DIR).resolve()

    room_abs = Path(room_image_path).resolve()
    items_args = [f"{name}={str(Path(path).resolve())}" for name, path in items]

    cmd = [
        sys.executable,
        "-u",
        "main_user_assets.py",
        "--room_image",
        str(room_abs),
        "--items",
        *items_args,
    ]

    output = _run_subprocess(cmd, cwd=p2, env=env)

    if "[ERROR]" in output or "Upload failed" in output:
        raise RuntimeError(f"Pipeline-2 reported an error in logs:\n{output}")

    gen_dir = p2 / "generated_images"
    candidates = sorted(gen_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError("Pipeline-2 finished but no output png found in generated_images/")

    out = candidates[0]
    dst = run_dir / "result.png"
    shutil.copy2(out, dst)
    return dst