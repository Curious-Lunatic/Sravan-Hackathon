from __future__ import annotations

import base64
import io
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from sarvamai import SarvamAI
from sarvamai.core.api_error import ApiError

from env_loader import require_api_key

LANGUAGES = {
    "en-IN": "English",
    "hi-IN": "Hindi",
    "bn-IN": "Bengali",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
    "mr-IN": "Marathi",
    "gu-IN": "Gujarati",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "pa-IN": "Punjabi",
    "od-IN": "Odia",
}

DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

AUDIO_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".mpeg": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}

NARRATOR = {
    "en-IN": ("bulbul:v4-flash", "girish_en_documentary"),
    "hi-IN": ("bulbul:v4-flash", "anand_hi_documentary"),
    "bn-IN": ("bulbul:v4-flash", "roopa_bn_conversational"),
    "ta-IN": ("bulbul:v4-flash", "gokul_ta_narration"),
    "te-IN": ("bulbul:v4-flash", "kavitha_te_narration"),
    "mr-IN": ("bulbul:v4-flash", "mrunal_mr_narration"),
    "gu-IN": ("bulbul:v4-flash", "pooja_gu_conversational"),
    "kn-IN": ("bulbul:v4-flash", "chaitra_kn_narration"),
    "pa-IN": ("bulbul:v4-flash", "harpreet_pa_narration"),
    "ml-IN": ("bulbul:v3", "shubh"),
    "od-IN": ("bulbul:v3", "shubh"),
}

HOST = {
    "en-IN": ("bulbul:v4-flash", "simran_en_conversation"),
    "hi-IN": ("bulbul:v4-flash", "simran_hi_conversation"),
    "bn-IN": ("bulbul:v4-flash", "roopa_bn_conversational"),
    "ta-IN": ("bulbul:v4-flash", "vijay_ta_narration"),
    "te-IN": ("bulbul:v4-flash", "pooja_te_conversation"),
    "mr-IN": ("bulbul:v4-flash", "ritu_mr_narration"),
    "gu-IN": ("bulbul:v4-flash", "pooja_gu_conversational"),
    "kn-IN": ("bulbul:v4-flash", "chaitra_kn_conversation"),
    "pa-IN": ("bulbul:v4-flash", "anand_pa_conversation"),
    "ml-IN": ("bulbul:v3", "priya"),
    "od-IN": ("bulbul:v3", "priya"),
}

GUEST = {
    "en-IN": ("bulbul:v4-flash", "shubh_en_audiobook"),
    "hi-IN": ("bulbul:v4-flash", "shubh_hi_stories_dramatic"),
    "bn-IN": ("bulbul:v4-flash", "bappa_bn_conversation"),
    "ta-IN": ("bulbul:v4-flash", "gokul_ta_narration"),
    "te-IN": ("bulbul:v4-flash", "tarun_te_narration"),
    "mr-IN": ("bulbul:v4-flash", "soham_mr_narration"),
    "gu-IN": ("bulbul:v4-flash", "bhavik_gu_conversation"),
    "kn-IN": ("bulbul:v4-flash", "chetan_kn_conversation"),
    "pa-IN": ("bulbul:v4-flash", "harpreet_pa_narration"),
    "ml-IN": ("bulbul:v3", "shubh"),
    "od-IN": ("bulbul:v3", "shubh"),
}

_CLIENT: SarvamAI | None = None


def client() -> SarvamAI:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = SarvamAI(api_subscription_key=require_api_key())
    return _CLIENT


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def classify_upload(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in DOCUMENT_TYPES:
        return "document"
    if suffix in AUDIO_TYPES:
        return "audio"
    raise ValueError(f"Unsupported file type: {suffix or filename}")


def identify_language(text: str) -> str:
    sample = text[:1000].strip() or text
    response = client().text.identify_language(input=sample)
    code = _attr(response, "language_code", "language") or "en-IN"
    if code not in LANGUAGES:
        return "en-IN"
    return code


def translate_text(text: str, target: str, source: str = "auto") -> str:
    if not text.strip():
        return text
    if source == target:
        return text
    chunks = _chunk(text, 900)
    translated: list[str] = []
    for chunk in chunks:
        response = client().text.translate(
            input=chunk,
            source_language_code=source if source in LANGUAGES else "auto",
            target_language_code=target,
            model="mayura:v1",
            mode="classic-colloquial",
            output_script="fully-native",
        )
        translated.append(_attr(response, "translated_text") or chunk)
        time.sleep(0.2)
    return "\n\n".join(translated)


def digitise_document(path: Path, language: str | None = None) -> str:
    mime = DOCUMENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    with path.open("rb") as handle:
        job = client().doc_ai.digitise(
            file=[(path.name, handle, mime)],
            language=language or None,
            content_type="mixed",
        )
    job_id = _attr(job, "job_id")
    status = _wait_doc_job(job_id)
    if status not in {"completed", "partially_completed"}:
        raise RuntimeError(f"Document digitisation ended with status {status}")
    download = client().doc_ai.get_download_url(job_id)
    url = _attr(download, "url")
    method = (_attr(download, "method") or "GET").upper()
    request = Request(url, method=method)
    with urlopen(request, timeout=120) as response:
        payload = response.read()
    return _text_from_archive(payload)


def transcribe_audio(path: Path) -> tuple[str, str | None]:
    try:
        with path.open("rb") as handle:
            response = client().speech_to_text.transcribe(
                file=(path.name, handle, AUDIO_TYPES.get(path.suffix.lower(), "audio/wav")),
                model="saaras:v4",
                mode="transcribe",
            )
        return (_attr(response, "transcript") or "").strip(), _attr(response, "language_code")
    except ApiError as error:
        if error.status_code not in {413, 422}:
            raise
    return _transcribe_batch(path)


def _transcribe_batch(path: Path) -> tuple[str, str | None]:
    job = client().speech_to_text_job.create_job(
        model="saaras:v4",
        mode="transcribe",
        with_diarization=True,
    )
    job.upload_files(file_paths=[str(path)])
    job.start()
    job.wait_until_complete()
    output_dir = path.parent / f"{path.stem}_stt"
    output_dir.mkdir(parents=True, exist_ok=True)
    job.download_outputs(output_dir=str(output_dir))
    texts: list[str] = []
    language = None
    for file in output_dir.rglob("*"):
        if file.suffix.lower() not in {".json", ".txt"}:
            continue
        raw = file.read_text(encoding="utf-8", errors="replace")
        if file.suffix.lower() == ".txt":
            texts.append(raw.strip())
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            texts.append(raw.strip())
            continue
        language = language or data.get("language_code")
        transcript = data.get("transcript") or data.get("text")
        if transcript:
            texts.append(str(transcript).strip())
            continue
        for entry in data.get("diarized_transcript") or data.get("segments") or []:
            speaker = entry.get("speaker") or entry.get("speaker_id") or "Speaker"
            piece = entry.get("transcript") or entry.get("text") or ""
            if piece:
                texts.append(f"{speaker}: {piece}".strip())
    return "\n".join(t for t in texts if t), language


def generate_experiences(source_text: str, target_language: str) -> dict[str, Any]:
    language_name = LANGUAGES.get(target_language, target_language)
    prompt = f"""You are a heritage storytelling director working from a historic manuscript or oral archive.

Write ALL output in {language_name} ({target_language}).
Stay faithful to the source. Do not invent dates, names, or events that are not implied by the source. If something is uncertain, say so in the story.

Return ONLY valid JSON with this shape:
{{
  "archive": {{
    "title": "short title",
    "period": "era or century if known, else unknown",
    "place": "place if known, else unknown",
    "people": ["names mentioned"],
    "summary": "2-3 sentence archival summary"
  }},
  "story": {{
    "title": "story title",
    "chapters": [
      {{"title": "chapter title", "body": "180-280 words of immersive narration", "prompt": "a question the visitor can ponder"}}
    ]
  }},
  "tour": {{
    "title": "guided tour title",
    "stops": [
      {{"title": "stop title", "place": "where we are standing", "narration": "90-140 words spoken by a guide", "look_for": "one physical or sensory detail"}}
    ]
  }},
  "podcast": {{
    "title": "episode title",
    "lines": [
      {{"speaker": "host", "text": "one spoken turn, 1-3 sentences"}},
      {{"speaker": "guest", "text": "one spoken turn, 1-3 sentences"}}
    ]
  }}
}}

Rules:
- story.chapters: exactly 4 chapters
- tour.stops: exactly 5 stops
- podcast.lines: 8 to 10 turns, alternating host and guest, host first
- Keep language natural and speakable for voice narration

SOURCE:
{source_text[:12000]}
"""
    content = _chat("sarvam-105b", prompt, temperature=0.55, max_tokens=4096)
    try:
        data = _parse_json(content)
    except ValueError:
        repair = _chat(
            "sarvam-105b",
            "Convert the following into the required heritage JSON only, no markdown:\n" + content[:8000],
            temperature=0.2,
            max_tokens=4096,
        )
        data = _parse_json(repair)
    return _normalise_experiences(data)


def ask_archive(question: str, source_text: str, experiences: dict[str, Any], language: str) -> str:
    language_name = LANGUAGES.get(language, language)
    context = json.dumps(
        {
            "archive": experiences.get("archive"),
            "story_title": (experiences.get("story") or {}).get("title"),
            "tour_title": (experiences.get("tour") or {}).get("title"),
        },
        ensure_ascii=False,
    )
    prompt = f"""Answer in {language_name}. You are a museum archivist. Use only the source and notes. If unknown, say so.

NOTES:
{context}

SOURCE:
{source_text[:8000]}

VISITOR QUESTION:
{question}
"""
    return _chat("sarvam-105b-conversations", prompt, temperature=0.4, max_tokens=700)


def synthesise_speech(text: str, language: str, role: str, output_path: Path) -> Path:
    model, speaker = _voice_for(language, role)
    chunks = _chunk(text, 1800)
    audio_parts: list[bytes] = []
    for chunk in chunks:
        try:
            response = client().text_to_speech.convert(
                text=chunk,
                language_code=language,
                model=model,
                speaker=speaker,
                pace=0.95,
                speech_sample_rate=24000,
                output_audio_codec="wav",
            )
        except ApiError:
            fallback_model, fallback_speaker = ("bulbul:v3", "priya" if role == "host" else "shubh")
            response = client().text_to_speech.convert(
                text=chunk,
                language_code=language,
                model=fallback_model,
                speaker=fallback_speaker,
                pace=0.95,
                speech_sample_rate=24000,
                output_audio_codec="wav",
            )
        encoded = "".join(_attr(response, "audios") or [])
        audio_parts.append(base64.b64decode(encoded))
        time.sleep(0.35)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_join_wav(audio_parts) if len(audio_parts) > 1 else audio_parts[0])
    return output_path


def _voice_for(language: str, role: str) -> tuple[str, str]:
    table = {"host": HOST, "guest": GUEST}.get(role, NARRATOR)
    return table.get(language, ("bulbul:v3", "shubh"))


def _chat(model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    response = client().chat.completions(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (response.choices[0].message.content or "").strip()


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model did not return JSON")
    return json.loads(cleaned[start : end + 1])


def _normalise_experiences(data: dict[str, Any]) -> dict[str, Any]:
    archive = data.get("archive") or {}
    story = data.get("story") or {}
    tour = data.get("tour") or {}
    podcast = data.get("podcast") or {}
    chapters = [
        {
            "title": item.get("title") or f"Chapter {index + 1}",
            "body": item.get("body") or "",
            "prompt": item.get("prompt") or "",
        }
        for index, item in enumerate(story.get("chapters") or [])
        if item.get("body")
    ][:6]
    stops = [
        {
            "title": item.get("title") or f"Stop {index + 1}",
            "place": item.get("place") or "",
            "narration": item.get("narration") or "",
            "look_for": item.get("look_for") or "",
        }
        for index, item in enumerate(tour.get("stops") or [])
        if item.get("narration")
    ][:6]
    lines = []
    for item in podcast.get("lines") or []:
        speaker = (item.get("speaker") or "host").lower()
        if speaker not in {"host", "guest"}:
            speaker = "host"
        text = item.get("text") or ""
        if text:
            lines.append({"speaker": speaker, "text": text})
    return {
        "archive": {
            "title": archive.get("title") or "Untitled archive",
            "period": archive.get("period") or "Unknown",
            "place": archive.get("place") or "Unknown",
            "people": archive.get("people") or [],
            "summary": archive.get("summary") or "",
        },
        "story": {"title": story.get("title") or "Story", "chapters": chapters},
        "tour": {"title": tour.get("title") or "Guided tour", "stops": stops},
        "podcast": {"title": podcast.get("title") or "Podcast", "lines": lines[:12]},
    }


def _wait_doc_job(job_id: str, timeout: int = 240) -> str:
    terminal = {"completed", "partially_completed", "failed", "rejected"}
    deadline = time.time() + timeout
    status = "pending"
    while time.time() < deadline:
        state = client().doc_ai.get_status(job_id)
        status = str(_attr(state, "status") or "").lower()
        if status in terminal:
            return status
        time.sleep(5)
    return status


def _text_from_archive(payload: bytes) -> str:
    if payload[:2] != b"PK":
        return payload.decode("utf-8", errors="replace")
    pieces: list[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            lower = name.lower()
            if not lower.endswith((".md", ".txt", ".html", ".htm", ".json")):
                continue
            raw = archive.read(name).decode("utf-8", errors="replace")
            if lower.endswith(".json"):
                pieces.append(_text_from_json(raw))
            elif lower.endswith((".html", ".htm")):
                pieces.append(_strip_html(raw))
            else:
                pieces.append(raw.strip())
    return "\n\n".join(p for p in pieces if p).strip()


def _text_from_json(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    collected: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str) and len(node.strip()) > 8:
            collected.append(node.strip())
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in {"text", "content", "markdown", "md", "html"} and isinstance(value, str):
                    collected.append(_strip_html(value) if "<" in value else value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return "\n".join(collected)


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def _chunk(text: str, limit: int) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        window = remaining[:limit]
        split_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("। "), window.rfind("\n"))
        if split_at < limit * 0.4:
            split_at = limit
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return [p for p in parts if p]


def _join_wav(parts: list[bytes]) -> bytes:
    frames: list[bytes] = []
    header = None
    for part in parts:
        if len(part) < 44 or part[:4] != b"RIFF":
            return b"".join(parts)
        if header is None:
            header = part[:44]
        frames.append(part[44:])
    body = b"".join(frames)
    size = len(body)
    header = bytearray(header)
    header[4:8] = (36 + size).to_bytes(4, "little")
    header[40:44] = size.to_bytes(4, "little")
    return bytes(header) + body
