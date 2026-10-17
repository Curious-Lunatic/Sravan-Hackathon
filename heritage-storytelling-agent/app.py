from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import sarvam_service as sarvam

ROOT = Path(__file__).parent
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
AUDIO = DATA / "audio"
STATIC = ROOT / "static"

UPLOADS.mkdir(parents=True, exist_ok=True)
AUDIO.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Heritage Storytelling Agent")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.mount("/audio", StaticFiles(directory=AUDIO), name="audio")

JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()

STEPS = ["ingest", "translate", "compose", "narrate"]


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/languages")
def languages() -> dict[str, str]:
    return sarvam.LANGUAGES


@app.post("/api/projects")
async def create_project(
    target_language: str = Form(...),
    source_text: str = Form(""),
    manuscript: UploadFile | None = File(None),
    oral_archive: UploadFile | None = File(None),
) -> dict[str, Any]:
    if target_language not in sarvam.LANGUAGES:
        raise HTTPException(400, "Unsupported target language")
    text = (source_text or "").strip()
    if not text and not manuscript and not oral_archive:
        raise HTTPException(400, "Add a manuscript, an oral archive, or pasted source text")

    project_id = uuid.uuid4().hex[:12]
    project_dir = UPLOADS / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, str]] = []
    for upload, kind in ((manuscript, "manuscript"), (oral_archive, "oral_archive")):
        if not upload or not upload.filename:
            continue
        saved = project_dir / Path(upload.filename).name
        saved.write_bytes(await upload.read())
        files.append({"kind": kind, "path": str(saved), "name": saved.name})

    job = {
        "id": project_id,
        "status": "queued",
        "step": "ingest",
        "steps": {name: "pending" for name in STEPS},
        "error": None,
        "target_language": target_language,
        "pasted_text": text,
        "files": files,
        "source_language": None,
        "source_text": "",
        "translated_text": "",
        "experiences": None,
        "audio": {},
        "log": [],
    }
    with LOCK:
        JOBS[project_id] = job
    threading.Thread(target=_run_pipeline, args=(project_id,), daemon=True).start()
    return {"id": project_id}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    job = _job(project_id)
    return _public(job)


@app.post("/api/projects/{project_id}/ask")
def ask_project(project_id: str, payload: dict[str, str]) -> dict[str, str]:
    job = _job(project_id)
    if job["status"] != "ready":
        raise HTTPException(409, "The archive is still being prepared")
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Ask a question")
    try:
        answer = sarvam.ask_archive(
            question,
            job["source_text"],
            job["experiences"],
            job["target_language"],
        )
    except Exception as error:
        raise HTTPException(502, _safe_error(error)) from error
    return {"answer": answer}


@app.post("/api/projects/{project_id}/narrate")
def narrate_piece(project_id: str, payload: dict[str, Any]) -> dict[str, str]:
    job = _job(project_id)
    if job["status"] != "ready":
        raise HTTPException(409, "The archive is still being prepared")
    kind = payload.get("kind")
    index = int(payload.get("index") or 0)
    try:
        url = _narrate(job, kind, index)
    except Exception as error:
        raise HTTPException(502, _safe_error(error)) from error
    return {"url": url}


def _run_pipeline(project_id: str) -> None:
    job = JOBS[project_id]
    try:
        _set(job, status="running", step="ingest", steps=_mark(job, "ingest", "running"))
        _log(job, "Reading manuscripts and oral archives")
        source_parts: list[str] = []
        detected = None
        if job["pasted_text"]:
            source_parts.append(job["pasted_text"])
        for item in job["files"]:
            path = Path(item["path"])
            if item["kind"] == "manuscript":
                _log(job, f"Digitising {item['name']} with Sarvam Vision")
                source_parts.append(sarvam.digitise_document(path))
            else:
                _log(job, f"Transcribing {item['name']} with Saaras")
                transcript, language = sarvam.transcribe_audio(path)
                detected = detected or language
                source_parts.append(transcript)
        source_text = "\n\n".join(part.strip() for part in source_parts if part and part.strip())
        if not source_text:
            raise RuntimeError("No text could be recovered from the archive")
        source_language = detected or sarvam.identify_language(source_text)
        job["source_text"] = source_text
        job["source_language"] = source_language
        _set(job, steps=_mark(job, "ingest", "done"), step="translate")

        _set(job, steps=_mark(job, "translate", "running"))
        _log(job, f"Translating into {sarvam.LANGUAGES[job['target_language']]}")
        translated = sarvam.translate_text(source_text, job["target_language"], source_language)
        job["translated_text"] = translated
        _set(job, steps=_mark(job, "translate", "done"), step="compose")

        _set(job, steps=_mark(job, "compose", "running"))
        _log(job, "Composing story, guided tour, and podcast")
        experiences = sarvam.generate_experiences(translated, job["target_language"])
        job["experiences"] = experiences
        _set(job, steps=_mark(job, "compose", "done"), step="narrate")

        _set(job, steps=_mark(job, "narrate", "running"))
        _log(job, "Recording opening narration")
        if experiences["story"]["chapters"]:
            _narrate(job, "story", 0)
        if experiences["tour"]["stops"]:
            _narrate(job, "tour", 0)
        for index in range(min(4, len(experiences["podcast"]["lines"]))):
            _narrate(job, "podcast", index)
        _set(job, steps=_mark(job, "narrate", "done"), status="ready", step="ready")
        _log(job, "The archive is ready")
    except Exception as error:
        job["error"] = _safe_error(error)
        job["status"] = "error"
        _log(job, job["error"])
        traceback.print_exc()


def _narrate(job: dict[str, Any], kind: str, index: int) -> str:
    experiences = job["experiences"] or {}
    key = f"{kind}:{index}"
    if key in job["audio"]:
        return job["audio"][key]
    if kind == "story":
        chapter = experiences["story"]["chapters"][index]
        text = f"{chapter['title']}. {chapter['body']}"
        role = "narrator"
    elif kind == "tour":
        stop = experiences["tour"]["stops"][index]
        text = f"{stop['title']}. {stop['narration']}"
        role = "narrator"
    elif kind == "podcast":
        line = experiences["podcast"]["lines"][index]
        text = line["text"]
        role = line["speaker"]
    else:
        raise ValueError("Unknown narration type")
    filename = f"{job['id']}_{kind}_{index}.wav"
    path = AUDIO / filename
    sarvam.synthesise_speech(text, job["target_language"], role, path)
    url = f"/audio/{filename}"
    job["audio"][key] = url
    return url


def _job(project_id: str) -> dict[str, Any]:
    with LOCK:
        job = JOBS.get(project_id)
    if not job:
        raise HTTPException(404, "Project not found")
    return job


def _public(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "status": job["status"],
        "step": job["step"],
        "steps": job["steps"],
        "error": job["error"],
        "log": job["log"][-8:],
        "source_language": job["source_language"],
        "target_language": job["target_language"],
        "source_text": job["source_text"],
        "translated_text": job["translated_text"],
        "experiences": job["experiences"],
        "audio": job["audio"],
    }


def _set(job: dict[str, Any], **fields: Any) -> None:
    job.update(fields)


def _mark(job: dict[str, Any], step: str, state: str) -> dict[str, str]:
    steps = dict(job["steps"])
    steps[step] = state
    return steps


def _log(job: dict[str, Any], message: str) -> None:
    job["log"].append(message)


def _safe_error(error: Exception) -> str:
    text = str(error)
    return text[:400] if text else error.__class__.__name__
