# Heritage Storytelling Agent

> **Bring history to life.** Digitise manuscripts, transcribe oral archives, and transform historical content into interactive stories, guided tours, and multilingual voice podcasts — powered by [Sarvam AI](https://sarvam.ai).

---

## ✨ What it does

The Heritage Storytelling Agent is an end-to-end AI pipeline that ingests raw historical material — a scanned leaf, a crumbling PDF, a field recording of an elder's voice — and transforms it into three distinct interactive experiences:

| Experience | What it produces |
|---|---|
| **📖 Interactive Story** | Four immersive narrative chapters with reflection prompts, narrated by an AI voice |
| **🗺️ Guided Tour** | Five location-anchored stops with sensory "look for" cues, spoken by a virtual guide |
| **🎙️ Podcast** | A 8–10 turn dialogue between a host and a guest scholar, fully voiced |

Every output is generated in any of **11 Indian languages** with natural-sounding, speaker-matched voices.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Browser (SPA)                      │
│  Sidebar form → Pipeline indicator → Tab workspace  │
└────────────────────┬────────────────────────────────┘
                     │  FastAPI (app.py)
          ┌──────────▼──────────────────────────────┐
          │           Pipeline (background thread)   │
          │                                          │
          │  1. INGEST                               │
          │     ├─ PDF/image → Sarvam Doc AI (OCR)   │
          │     └─ Audio     → Saaras v4 (STT)       │
          │                                          │
          │  2. TRANSLATE                            │
          │     └─ Mayura v1 (11 language pairs)     │
          │                                          │
          │  3. COMPOSE                              │
          │     └─ Sarvam-105B (story/tour/podcast)  │
          │                                          │
          │  4. NARRATE                              │
          │     └─ Bulbul v4-flash / v3 (TTS)        │
          └─────────────────────────────────────────┘
```

---

## 🚀 Quick start

### Prerequisites

- Python **3.10+**
- A [Sarvam AI](https://sarvam.ai) API key

### Install & run

```bash
# 1. Clone the repo
git clone https://github.com/your-org/Sravan-Hackathon.git
cd Sravan-Hackathon/heritage-storytelling-agent

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set your API key
#    Edit .env and add your Sarvam key:
echo "SARVAM_API_KEY=your_key_here" > .env

# 5. Launch the server
uvicorn app:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## 🔑 Configuration

The app reads a single environment variable from `.env`:

| Variable | Required | Description |
|---|---|---|
| `SARVAM_API_KEY` | ✅ | Your Sarvam AI API subscription key |

---

## 📁 Project structure

```
heritage-storytelling-agent/
├── app.py               # FastAPI server + pipeline orchestration
├── sarvam_service.py    # All Sarvam AI API calls (OCR, STT, translate, LLM, TTS)
├── env_loader.py        # .env loader and key validation
├── requirements.txt     # Python dependencies
├── .env                 # API key (never commit this)
├── data/
│   ├── uploads/         # Uploaded manuscripts and audio files (per-project)
│   └── audio/           # Generated .wav narration files
└── static/
    ├── index.html        # Single-page app shell
    ├── app.js            # Frontend — form, polling, rendering, narration
    └── styles.css        # Design system — dark editorial theme
```

---

## 🌐 Supported languages

| Code | Language |
|---|---|
| `en-IN` | English |
| `hi-IN` | Hindi |
| `bn-IN` | Bengali |
| `ta-IN` | Tamil |
| `te-IN` | Telugu |
| `mr-IN` | Marathi |
| `gu-IN` | Gujarati |
| `kn-IN` | Kannada |
| `ml-IN` | Malayalam |
| `pa-IN` | Punjabi |
| `od-IN` | Odia |

---

## 🔌 API reference

All endpoints are served under `/api`.

### `GET /api/languages`
Returns a map of supported language codes → display names.

---

### `POST /api/projects`
Create a new project and start the pipeline.

**Form fields:**

| Field | Type | Description |
|---|---|---|
| `target_language` | `string` | Required. Target language code (e.g. `hi-IN`) |
| `source_text` | `string` | Optional. Pasted historical text |
| `manuscript` | `file` | Optional. PDF, PNG, or JPG scan |
| `oral_archive` | `file` | Optional. Audio file (WAV, MP3, M4A, OGG, FLAC, WebM) |

> At least one of `source_text`, `manuscript`, or `oral_archive` is required.

**Response:** `{ "id": "<project_id>" }`

---

### `GET /api/projects/{project_id}`
Poll the pipeline status.

**Response shape:**
```json
{
  "id": "abc123",
  "status": "ready",
  "step": "ready",
  "steps": { "ingest": "done", "translate": "done", "compose": "done", "narrate": "done" },
  "error": null,
  "log": ["Reading manuscripts…", "Translating into Hindi", "…"],
  "source_language": "en-IN",
  "target_language": "hi-IN",
  "source_text": "…",
  "translated_text": "…",
  "experiences": { "archive": {…}, "story": {…}, "tour": {…}, "podcast": {…} },
  "audio": { "story:0": "/audio/abc123_story_0.wav", … }
}
```

---

### `POST /api/projects/{project_id}/ask`
Ask the archivist AI a question about the source material.

**Body:** `{ "question": "Who commissioned the Vitthala mandapa?" }`

**Response:** `{ "answer": "…" }`

---

### `POST /api/projects/{project_id}/narrate`
Generate (or retrieve cached) narration audio for a specific piece.

**Body:**
```json
{ "kind": "story",   "index": 0 }
{ "kind": "tour",    "index": 2 }
{ "kind": "podcast", "index": 4 }
```

**Response:** `{ "url": "/audio/<filename>.wav" }`

---

## 🧠 AI models used

| Task | Model |
|---|---|
| Document OCR | Sarvam Doc AI |
| Speech-to-text | Saaras v4 (batch for large files) |
| Language detection | Sarvam Language ID |
| Translation | Mayura v1 (`classic-colloquial` mode) |
| Story / tour / podcast generation | Sarvam-105B |
| Q&A | Sarvam-105B-Conversations |
| Text-to-speech | Bulbul v4-flash (Bulbul v3 fallback) |

---

## 🎙️ Voice characters

The agent selects different TTS speakers based on role:

| Role | Description |
|---|---|
| **Narrator** | Documentary-style voice for story chapters and tour stops |
| **Host** | Conversational host voice for podcast |
| **Guest** | Scholar guest voice for podcast |

Each role maps to a language-specific speaker (e.g., `girish_en_documentary` for English narrator, `anand_hi_documentary` for Hindi).

---

## 💡 Usage tips

- **Best results** come from rich source texts: court records, temple inscriptions, biographical accounts, travel diaries, oral testimonies.
- The **"Load Hampi sample"** button seeds a 16th-century court memorandum from the Vijayanagara empire — a good way to demo the full pipeline.
- Audio for all chapters/stops is generated on demand. Click **"Hear this"** on any card to generate that specific narration.
- The **"Ask the Archive"** tab lets visitors query the AI archivist — it stays faithful to the source and says so when it doesn't know.

---

## 📦 Dependencies

```
fastapi          — async web framework
uvicorn          — ASGI server
python-multipart — form / file upload parsing
sarvamai         — Sarvam AI Python SDK
```

---

## 🔒 Security note

Never commit your `.env` file. The `.gitignore` already excludes it. For production, set `SARVAM_API_KEY` as an environment variable in your deployment platform rather than using a file.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">Made with ❤️ for India's heritage · Powered by <strong>Sarvam AI</strong></p>