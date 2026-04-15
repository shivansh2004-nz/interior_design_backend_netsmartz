# from __future__ import annotations

# import json
# import threading
# import traceback
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from starlette.middleware.sessions import SessionMiddleware

# from .auth import router as auth_router
# from .pipeline_runner import (
#     new_run_dir,
#     save_upload,
#     run_pipeline1,
#     run_pipeline2,
#     run_pipeline1_custom,
# )
# from .settings import settings
# from .mongodb import get_user_by_email, update_user_credits


# app = FastAPI(title="Interior Design Web API")

# ALLOWED_ORIGINS = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173",
#     "http://localhost:5174",
#     "http://127.0.0.1:5174",
#     "http://192.168.18.222:5173",
#     "http://192.168.18.222:5174",
#     "https://interior-design-frontend-ten.vercel.app",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=ALLOWED_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET)

# app.include_router(auth_router)

# runs_dir = Path(settings.STORAGE_DIR) / "runs"
# runs_dir.mkdir(parents=True, exist_ok=True)

# jobs_dir = Path(settings.STORAGE_DIR) / "jobs"
# jobs_dir.mkdir(parents=True, exist_ok=True)

# app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")


# # -------------------------
# # Job store helpers
# # -------------------------
# jobs: dict[str, dict[str, Any]] = {}
# jobs_lock = threading.Lock()


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()


# def job_file_path(job_id: str) -> Path:
#     return jobs_dir / f"{job_id}.json"


# def persist_job(job_id: str) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         snapshot = dict(job)

#     job_file_path(job_id).write_text(
#         json.dumps(snapshot, indent=2, ensure_ascii=False),
#         encoding="utf-8",
#     )


# def create_job(job_type: str, email: str | None = None) -> str:
#     job_id = uuid.uuid4().hex
#     job = {
#         "job_id": job_id,
#         "job_type": job_type,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#         "result_url": None,
#         "run_id": None,
#         "error": None,
#         "email": email,
#         "created_at": utc_now_iso(),
#         "updated_at": utc_now_iso(),
#     }

#     with jobs_lock:
#         jobs[job_id] = job

#     persist_job(job_id)
#     return job_id


# def update_job(job_id: str, **fields: Any) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         job.update(fields)
#         job["updated_at"] = utc_now_iso()

#     persist_job(job_id)


# def load_job_from_disk(job_id: str) -> dict[str, Any] | None:
#     p = job_file_path(job_id)
#     if not p.exists():
#         return None
#     try:
#         return json.loads(p.read_text(encoding="utf-8"))
#     except Exception:
#         return None


# def get_job(job_id: str) -> dict[str, Any] | None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if job:
#             return dict(job)

#     disk_job = load_job_from_disk(job_id)
#     if disk_job:
#         with jobs_lock:
#             jobs[job_id] = disk_job
#         return dict(disk_job)

#     return None


# # -------------------------
# # Background workers
# # -------------------------
# def pipeline1_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting pipeline 1...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline1_custom_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     furnitures: list[str],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting custom pipeline 1...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1_custom(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Custom pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Custom pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline2_worker(
#     job_id: str,
#     room_path: Path,
#     items: list[tuple[str, Path]],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting pipeline 2...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline2(Path(room_path), items, run_dir)

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 2 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 2 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# # -------------------------
# # Routes
# # -------------------------
# @app.get("/health")
# def health():
#     return {
#         "ok": True,
#         "allowed_origins": ALLOWED_ORIGINS,
#     }


# @app.get("/jobs/{job_id}")
# def api_get_job(job_id: str):
#     job = get_job(job_id)
#     if not job:
#         raise HTTPException(status_code=404, detail="Job not found")

#     return {
#         "job_id": job["job_id"],
#         "status": job["status"],
#         "message": job.get("message"),
#         "result_url": job.get("result_url"),
#         "run_id": job.get("run_id"),
#         "error": job.get("error"),
#         "created_at": job.get("created_at"),
#         "updated_at": job.get("updated_at"),
#     }


# @app.post("/run/pipeline1")
# async def api_run_pipeline1(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1", email=email)

#     thread = threading.Thread(
#         target=pipeline1_worker,
#         args=(job_id, room_path, room_type, dimensions, style, budget, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }


# @app.post("/run/pipeline1-custom")
# async def api_run_pipeline1_custom(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     furnitures = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if not furnitures:
#         raise HTTPException(status_code=400, detail="furniture_names cannot be empty")
#     if len(furnitures) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture items allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1_custom", email=email)

#     thread = threading.Thread(
#         target=pipeline1_custom_worker,
#         args=(
#             job_id,
#             room_path,
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#             email,
#         ),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for custom pipeline to start...",
#     }


# @app.post("/run/pipeline2")
# async def api_run_pipeline2(
#     room_image: UploadFile = File(...),
#     furniture_images: list[UploadFile] = File(...),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     names = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if len(names) != len(furniture_images):
#         raise HTTPException(
#             status_code=400,
#             detail="furniture_names count must match furniture_images count",
#         )
#     if len(names) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture images allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     items: list[tuple[str, Path]] = []
#     for file, name in zip(furniture_images, names):
#         p = Path(save_upload(await file.read(), file.filename, run_dir))
#         items.append((name, p))

#     job_id = create_job("pipeline2", email=email)

#     thread = threading.Thread(
#         target=pipeline2_worker,
#         args=(job_id, room_path, items, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }

# from __future__ import annotations

# import json
# import threading
# import traceback
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from starlette.middleware.sessions import SessionMiddleware

# from .auth import router as auth_router
# from .pipeline_runner import (
#     new_run_dir,
#     save_upload,
#     run_pipeline1,
#     run_pipeline2,
#     run_pipeline1_custom,
# )
# from .settings import settings
# from .mongodb import get_user_by_email, update_user_credits


# app = FastAPI(title="Interior Design Web API")

# ALLOWED_ORIGINS = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173",
#     "http://localhost:5174",
#     "http://127.0.0.1:5174",
#     "http://192.168.18.222:5173",
#     "http://192.168.18.222:5174",
#     "https://interior-design-frontend-ten.vercel.app",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=ALLOWED_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET)

# app.include_router(auth_router)

# runs_dir = Path(settings.STORAGE_DIR) / "runs"
# runs_dir.mkdir(parents=True, exist_ok=True)

# jobs_dir = Path(settings.STORAGE_DIR) / "jobs"
# jobs_dir.mkdir(parents=True, exist_ok=True)

# app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")


# # -------------------------
# # Job store helpers
# # -------------------------
# jobs: dict[str, dict[str, Any]] = {}
# jobs_lock = threading.Lock()


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()


# def job_file_path(job_id: str) -> Path:
#     return jobs_dir / f"{job_id}.json"


# def persist_job(job_id: str) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         snapshot = dict(job)

#     job_file_path(job_id).write_text(
#         json.dumps(snapshot, indent=2, ensure_ascii=False),
#         encoding="utf-8",
#     )


# def create_job(job_type: str, email: str | None = None) -> str:
#     job_id = uuid.uuid4().hex
#     job = {
#         "job_id": job_id,
#         "job_type": job_type,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#         "result_url": None,
#         "run_id": None,
#         "error": None,
#         "email": email,
#         "created_at": utc_now_iso(),
#         "updated_at": utc_now_iso(),
#     }

#     with jobs_lock:
#         jobs[job_id] = job

#     persist_job(job_id)
#     return job_id


# def update_job(job_id: str, **fields: Any) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         job.update(fields)
#         job["updated_at"] = utc_now_iso()

#     persist_job(job_id)


# def load_job_from_disk(job_id: str) -> dict[str, Any] | None:
#     p = job_file_path(job_id)
#     if not p.exists():
#         return None
#     try:
#         return json.loads(p.read_text(encoding="utf-8"))
#     except Exception:
#         return None


# def get_job(job_id: str) -> dict[str, Any] | None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if job:
#             return dict(job)

#     disk_job = load_job_from_disk(job_id)
#     if disk_job:
#         with jobs_lock:
#             jobs[job_id] = disk_job
#         return dict(disk_job)

#     return None


# # -------------------------
# # Background workers
# # -------------------------
# def pipeline1_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting pipeline 1...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline1_custom_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     furnitures: list[str],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting custom pipeline 1...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1_custom(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Custom pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Custom pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline2_worker(
#     job_id: str,
#     room_path: Path,
#     items: list[tuple[str, Path]],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Starting pipeline 2...",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline2(Path(room_path), items, run_dir)

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         if email:
#             awaitable = update_user_credits(email, -1)
#             try:
#                 import asyncio

#                 asyncio.run(awaitable)
#             except RuntimeError:
#                 loop = asyncio.new_event_loop()
#                 try:
#                     loop.run_until_complete(awaitable)
#                 finally:
#                     loop.close()

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 2 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 2 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# # -------------------------
# # Routes
# # -------------------------
# @app.get("/health")
# def health():
#     return {
#         "ok": True,
#         "allowed_origins": ALLOWED_ORIGINS,
#     }


# @app.get("/jobs/{job_id}")
# def api_get_job(job_id: str):
#     job = get_job(job_id)
#     if not job:
#         raise HTTPException(status_code=404, detail="Job not found")

#     return {
#         "job_id": job["job_id"],
#         "status": job["status"],
#         "message": job.get("message"),
#         "result_url": job.get("result_url"),
#         "run_id": job.get("run_id"),
#         "error": job.get("error"),
#         "created_at": job.get("created_at"),
#         "updated_at": job.get("updated_at"),
#     }


# @app.post("/run/pipeline1")
# async def api_run_pipeline1(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1", email=email)

#     thread = threading.Thread(
#         target=pipeline1_worker,
#         args=(job_id, room_path, room_type, dimensions, style, budget, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }


# @app.post("/run/pipeline1-custom")
# async def api_run_pipeline1_custom(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     furnitures = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if not furnitures:
#         raise HTTPException(status_code=400, detail="furniture_names cannot be empty")
#     if len(furnitures) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture items allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1_custom", email=email)

#     thread = threading.Thread(
#         target=pipeline1_custom_worker,
#         args=(
#             job_id,
#             room_path,
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#             email,
#         ),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for custom pipeline to start...",
#     }


# @app.post("/run/pipeline2")
# async def api_run_pipeline2(
#     room_image: UploadFile = File(...),
#     furniture_images: list[UploadFile] = File(...),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     names = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if len(names) != len(furniture_images):
#         raise HTTPException(
#             status_code=400,
#             detail="furniture_names count must match furniture_images count",
#         )
#     if len(names) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture images allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     items: list[tuple[str, Path]] = []
#     for file, name in zip(furniture_images, names):
#         p = Path(save_upload(await file.read(), file.filename, run_dir))
#         items.append((name, p))

#     job_id = create_job("pipeline2", email=email)

#     thread = threading.Thread(
#         target=pipeline2_worker,
#         args=(job_id, room_path, items, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }

# from __future__ import annotations

# import asyncio
# import json
# import threading
# import traceback
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any

# from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from starlette.middleware.sessions import SessionMiddleware

# from .auth import router as auth_router
# from .pipeline_runner import (
#     new_run_dir,
#     save_upload,
#     run_pipeline1,
#     run_pipeline2,
#     run_pipeline1_custom,
# )
# from .settings import settings
# from .mongodb import get_user_by_email, update_user_credits


# app = FastAPI(title="Interior Design Web API")

# ALLOWED_ORIGINS = [
#     "http://localhost:5173",
#     "http://127.0.0.1:5173",
#     "http://localhost:5174",
#     "http://127.0.0.1:5174",
#     "http://192.168.18.222:5173",
#     "http://192.168.18.222:5174",
#     "https://interior-design-frontend-ten.vercel.app",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=ALLOWED_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET)

# app.include_router(auth_router)

# runs_dir = Path(settings.STORAGE_DIR) / "runs"
# runs_dir.mkdir(parents=True, exist_ok=True)

# jobs_dir = Path(settings.STORAGE_DIR) / "jobs"
# jobs_dir.mkdir(parents=True, exist_ok=True)

# app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")


# # -------------------------
# # Job store helpers
# # -------------------------
# jobs: dict[str, dict[str, Any]] = {}
# jobs_lock = threading.Lock()


# def utc_now_iso() -> str:
#     return datetime.now(timezone.utc).isoformat()


# def job_file_path(job_id: str) -> Path:
#     return jobs_dir / f"{job_id}.json"


# def persist_job(job_id: str) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         snapshot = dict(job)

#     job_file_path(job_id).write_text(
#         json.dumps(snapshot, indent=2, ensure_ascii=False),
#         encoding="utf-8",
#     )


# def create_job(job_type: str, email: str | None = None) -> str:
#     job_id = uuid.uuid4().hex
#     job = {
#         "job_id": job_id,
#         "job_type": job_type,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#         "result_url": None,
#         "run_id": None,
#         "error": None,
#         "email": email,
#         "created_at": utc_now_iso(),
#         "updated_at": utc_now_iso(),
#     }

#     with jobs_lock:
#         jobs[job_id] = job

#     persist_job(job_id)
#     return job_id


# def update_job(job_id: str, **fields: Any) -> None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if not job:
#             return
#         job.update(fields)
#         job["updated_at"] = utc_now_iso()

#     persist_job(job_id)


# def load_job_from_disk(job_id: str) -> dict[str, Any] | None:
#     p = job_file_path(job_id)
#     if not p.exists():
#         return None
#     try:
#         return json.loads(p.read_text(encoding="utf-8"))
#     except Exception:
#         return None


# def get_job(job_id: str) -> dict[str, Any] | None:
#     with jobs_lock:
#         job = jobs.get(job_id)
#         if job:
#             return dict(job)

#     disk_job = load_job_from_disk(job_id)
#     if disk_job:
#         with jobs_lock:
#             jobs[job_id] = disk_job
#         return dict(disk_job)

#     return None


# def deduct_credit_if_needed(email: str | None) -> None:
#     if not email:
#         return

#     # Create and run a fresh coroutine exactly once.
#     asyncio.run(update_user_credits(email, -1))


# # -------------------------
# # Background workers
# # -------------------------
# def pipeline1_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Pipeline 1 started.",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         deduct_credit_if_needed(email)

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline1_custom_worker(
#     job_id: str,
#     room_path: Path,
#     room_type: str,
#     dimensions: str,
#     style: str,
#     budget: str,
#     furnitures: list[str],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Custom pipeline 1 started.",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline1_custom(
#             Path(room_path),
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#         )

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         deduct_credit_if_needed(email)

#         update_job(
#             job_id,
#             status="completed",
#             message="Custom pipeline 1 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Custom pipeline 1 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# def pipeline2_worker(
#     job_id: str,
#     room_path: Path,
#     items: list[tuple[str, Path]],
#     run_dir: Path,
#     email: str | None,
# ) -> None:
#     try:
#         update_job(
#             job_id,
#             status="running",
#             message="Pipeline 2 started.",
#             run_id=run_dir.name,
#         )

#         out_path = run_pipeline2(Path(room_path), items, run_dir)

#         if not out_path.exists():
#             raise RuntimeError("Pipeline returned success but result.png not found.")

#         result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

#         deduct_credit_if_needed(email)

#         update_job(
#             job_id,
#             status="completed",
#             message="Pipeline 2 completed successfully.",
#             result_url=result_url,
#             error=None,
#         )

#     except Exception as e:
#         update_job(
#             job_id,
#             status="failed",
#             message="Pipeline 2 failed.",
#             error=str(e),
#             traceback=traceback.format_exc(),
#         )


# # -------------------------
# # Routes
# # -------------------------
# @app.get("/health")
# def health():
#     return {
#         "ok": True,
#         "allowed_origins": ALLOWED_ORIGINS,
#     }


# @app.get("/jobs/{job_id}")
# def api_get_job(job_id: str):
#     job = get_job(job_id)
#     if not job:
#         raise HTTPException(status_code=404, detail="Job not found")

#     return {
#         "job_id": job["job_id"],
#         "status": job["status"],
#         "message": job.get("message"),
#         "result_url": job.get("result_url"),
#         "run_id": job.get("run_id"),
#         "error": job.get("error"),
#         "created_at": job.get("created_at"),
#         "updated_at": job.get("updated_at"),
#     }


# @app.post("/run/pipeline1")
# async def api_run_pipeline1(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1", email=email)

#     thread = threading.Thread(
#         target=pipeline1_worker,
#         args=(job_id, room_path, room_type, dimensions, style, budget, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }


# @app.post("/run/pipeline1-custom")
# async def api_run_pipeline1_custom(
#     room_image: UploadFile = File(...),
#     room_type: str = Form(...),
#     dimensions: str = Form(...),
#     style: str = Form("minimal"),
#     budget: str = Form("medium"),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     furnitures = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if not furnitures:
#         raise HTTPException(status_code=400, detail="furniture_names cannot be empty")
#     if len(furnitures) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture items allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     job_id = create_job("pipeline1_custom", email=email)

#     thread = threading.Thread(
#         target=pipeline1_custom_worker,
#         args=(
#             job_id,
#             room_path,
#             room_type,
#             dimensions,
#             style,
#             budget,
#             furnitures,
#             run_dir,
#             email,
#         ),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for custom pipeline to start...",
#     }


# @app.post("/run/pipeline2")
# async def api_run_pipeline2(
#     room_image: UploadFile = File(...),
#     furniture_images: list[UploadFile] = File(...),
#     furniture_names: str = Form(...),
#     email: str = Form(None),
# ):
#     if email:
#         user = await get_user_by_email(email)
#         if not user or user.get("credits", 0) <= 0:
#             raise HTTPException(status_code=403, detail="Insufficient credits")

#     names = [x.strip() for x in furniture_names.split(",") if x.strip()]
#     if len(names) != len(furniture_images):
#         raise HTTPException(
#             status_code=400,
#             detail="furniture_names count must match furniture_images count",
#         )
#     if len(names) > 7:
#         raise HTTPException(status_code=400, detail="Max 7 furniture images allowed")

#     run_dir = new_run_dir()
#     room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

#     items: list[tuple[str, Path]] = []
#     for file, name in zip(furniture_images, names):
#         p = Path(save_upload(await file.read(), file.filename, run_dir))
#         items.append((name, p))

#     job_id = create_job("pipeline2", email=email)

#     thread = threading.Thread(
#         target=pipeline2_worker,
#         args=(job_id, room_path, items, run_dir, email),
#         daemon=True,
#     )
#     thread.start()

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Job queued. Waiting for pipeline to start...",
#     }

from __future__ import annotations

import asyncio
import json
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router
from .pipeline_runner import (
    new_run_dir,
    save_upload,
    run_pipeline1,
    run_pipeline2,
    run_pipeline1_custom,
)
from .settings import settings
from .mongodb import get_user_by_email, update_user_credits


app = FastAPI(title="Interior Design Web API")

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://192.168.18.222:5173",
    "http://192.168.18.222:5174",
    "https://interior-design-frontend-ten.vercel.app",
    "http://192.168.19.236:3000",
    "http://192.168.19.236:5000",
]

app.add_middleware(
    CORSMiddleware,
    # allow_origins=ALLOWED_ORIGINS,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=settings.APP_SECRET)

app.include_router(auth_router)

runs_dir = Path(settings.STORAGE_DIR) / "runs"
runs_dir.mkdir(parents=True, exist_ok=True)

jobs_dir = Path(settings.STORAGE_DIR) / "jobs"
jobs_dir.mkdir(parents=True, exist_ok=True)

app.mount("/runs", StaticFiles(directory=str(runs_dir)), name="runs")


# -------------------------
# Global app loop reference
# -------------------------
APP_EVENT_LOOP: asyncio.AbstractEventLoop | None = None


@app.on_event("startup")
async def capture_main_loop():
    global APP_EVENT_LOOP
    APP_EVENT_LOOP = asyncio.get_running_loop()


# -------------------------
# Job store helpers
# -------------------------
jobs: dict[str, dict[str, Any]] = {}
jobs_lock = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_file_path(job_id: str) -> Path:
    return jobs_dir / f"{job_id}.json"


def persist_job(job_id: str) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        snapshot = dict(job)

    job_file_path(job_id).write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def create_job(job_type: str, email: str | None = None) -> str:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "job_type": job_type,
        "status": "queued",
        "message": "Job queued. Waiting for pipeline to start...",
        "result_url": None,
        "run_id": None,
        "error": None,
        "email": email,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
    }

    with jobs_lock:
        jobs[job_id] = job

    persist_job(job_id)
    return job_id


def update_job(job_id: str, **fields: Any) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = utc_now_iso()

    persist_job(job_id)


def load_job_from_disk(job_id: str) -> dict[str, Any] | None:
    p = job_file_path(job_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_job(job_id: str) -> dict[str, Any] | None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job:
            return dict(job)

    disk_job = load_job_from_disk(job_id)
    if disk_job:
        with jobs_lock:
            jobs[job_id] = disk_job
        return dict(disk_job)

    return None


# -------------------------
# Async-from-thread helper
# -------------------------
def run_coro_on_app_loop(coro):
    if APP_EVENT_LOOP is None:
        raise RuntimeError("Application event loop is not available yet.")
    future = asyncio.run_coroutine_threadsafe(coro, APP_EVENT_LOOP)
    return future.result()


def deduct_credit_if_needed(email: str | None) -> None:
    if not email:
        return

    # Run Mongo async update on FastAPI's main loop, not a new thread-local loop.
    run_coro_on_app_loop(update_user_credits(email, -1))


# -------------------------
# Background workers
# -------------------------
def pipeline1_worker(
    job_id: str,
    room_path: Path,
    room_type: str,
    dimensions: str,
    style: str,
    budget: str,
    run_dir: Path,
    email: str | None,
) -> None:
    try:
        update_job(
            job_id,
            status="running",
            message="Pipeline 1 started.",
            run_id=run_dir.name,
        )

        out_path = run_pipeline1(
            Path(room_path),
            room_type,
            dimensions,
            style,
            budget,
            run_dir,
        )

        if not out_path.exists():
            raise RuntimeError("Pipeline returned success but result.png not found.")

        result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

        deduct_credit_if_needed(email)

        update_job(
            job_id,
            status="completed",
            message="Pipeline 1 completed successfully.",
            result_url=result_url,
            error=None,
        )

    except Exception as e:
        update_job(
            job_id,
            status="failed",
            message="Pipeline 1 failed.",
            error=str(e),
            traceback=traceback.format_exc(),
        )


def pipeline1_custom_worker(
    job_id: str,
    room_path: Path,
    room_type: str,
    dimensions: str,
    style: str,
    budget: str,
    furnitures: list[str],
    run_dir: Path,
    email: str | None,
) -> None:
    try:
        update_job(
            job_id,
            status="running",
            message="Custom pipeline 1 started.",
            run_id=run_dir.name,
        )

        out_path = run_pipeline1_custom(
            Path(room_path),
            room_type,
            dimensions,
            style,
            budget,
            furnitures,
            run_dir,
        )

        if not out_path.exists():
            raise RuntimeError("Pipeline returned success but result.png not found.")

        result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

        deduct_credit_if_needed(email)

        update_job(
            job_id,
            status="completed",
            message="Custom pipeline 1 completed successfully.",
            result_url=result_url,
            error=None,
        )

    except Exception as e:
        update_job(
            job_id,
            status="failed",
            message="Custom pipeline 1 failed.",
            error=str(e),
            traceback=traceback.format_exc(),
        )


def pipeline2_worker(
    job_id: str,
    room_path: Path,
    items: list[tuple[str, Path]],
    run_dir: Path,
    email: str | None,
) -> None:
    try:
        update_job(
            job_id,
            status="running",
            message="Pipeline 2 started.",
            run_id=run_dir.name,
        )

        out_path = run_pipeline2(Path(room_path), items, run_dir)

        if not out_path.exists():
            raise RuntimeError("Pipeline returned success but result.png not found.")

        result_url = f"{settings.BACKEND_BASE_URL}/runs/{run_dir.name}/result.png"

        deduct_credit_if_needed(email)

        update_job(
            job_id,
            status="completed",
            message="Pipeline 2 completed successfully.",
            result_url=result_url,
            error=None,
        )

    except Exception as e:
        update_job(
            job_id,
            status="failed",
            message="Pipeline 2 failed.",
            error=str(e),
            traceback=traceback.format_exc(),
        )


# -------------------------
# Routes
# -------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "allowed_origins": ALLOWED_ORIGINS,
    }


@app.get("/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "message": job.get("message"),
        "result_url": job.get("result_url"),
        "run_id": job.get("run_id"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


@app.post("/run/pipeline1")
async def api_run_pipeline1(
    room_image: UploadFile = File(...),
    room_type: str = Form(...),
    dimensions: str = Form(...),
    style: str = Form("minimal"),
    budget: str = Form("medium"),
    email: str = Form(None),
):
    if email:
        user = await get_user_by_email(email)
        if not user or user.get("credits", 0) <= 0:
            raise HTTPException(status_code=403, detail="Insufficient credits")

    run_dir = new_run_dir()
    room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

    job_id = create_job("pipeline1", email=email)

    thread = threading.Thread(
        target=pipeline1_worker,
        args=(job_id, room_path, room_type, dimensions, style, budget, run_dir, email),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued. Waiting for pipeline to start...",
    }


@app.post("/run/pipeline1-custom")
async def api_run_pipeline1_custom(
    room_image: UploadFile = File(...),
    room_type: str = Form(...),
    dimensions: str = Form(...),
    style: str = Form("minimal"),
    budget: str = Form("medium"),
    furniture_names: str = Form(...),
    email: str = Form(None),
):
    if email:
        user = await get_user_by_email(email)
        if not user or user.get("credits", 0) <= 0:
            raise HTTPException(status_code=403, detail="Insufficient credits")

    furnitures = [x.strip() for x in furniture_names.split(",") if x.strip()]
    if not furnitures:
        raise HTTPException(status_code=400, detail="furniture_names cannot be empty")
    if len(furnitures) > 7:
        raise HTTPException(status_code=400, detail="Max 7 furniture items allowed")

    run_dir = new_run_dir()
    room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

    job_id = create_job("pipeline1_custom", email=email)

    thread = threading.Thread(
        target=pipeline1_custom_worker,
        args=(
            job_id,
            room_path,
            room_type,
            dimensions,
            style,
            budget,
            furnitures,
            run_dir,
            email,
        ),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued. Waiting for custom pipeline to start...",
    }


@app.post("/run/pipeline2")
async def api_run_pipeline2(
    room_image: UploadFile = File(...),
    furniture_images: list[UploadFile] = File(...),
    furniture_names: str = Form(...),
    email: str = Form(None),
):
    if email:
        user = await get_user_by_email(email)
        if not user or user.get("credits", 0) <= 0:
            raise HTTPException(status_code=403, detail="Insufficient credits")

    names = [x.strip() for x in furniture_names.split(",") if x.strip()]
    if len(names) != len(furniture_images):
        raise HTTPException(
            status_code=400,
            detail="furniture_names count must match furniture_images count",
        )
    if len(names) > 7:
        raise HTTPException(status_code=400, detail="Max 7 furniture images allowed")

    run_dir = new_run_dir()
    room_path = Path(save_upload(await room_image.read(), room_image.filename, run_dir))

    items: list[tuple[str, Path]] = []
    for file, name in zip(furniture_images, names):
        p = Path(save_upload(await file.read(), file.filename, run_dir))
        items.append((name, p))

    job_id = create_job("pipeline2", email=email)

    thread = threading.Thread(
        target=pipeline2_worker,
        args=(job_id, room_path, items, run_dir, email),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued. Waiting for pipeline to start...",
    }