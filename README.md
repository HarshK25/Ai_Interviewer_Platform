# 🤖 AI Interviewer Platform

> A voice-powered mock interview platform that tailors questions to a candidate's resume, scores answers with an LLM, and generates adaptive follow-ups and PDF scorecards.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Resume Parsing** | Upload PDF/DOCX → LLM extracts skills, experience, education → stored in ChromaDB |
| **RAG Question Generation** | LLM generates **fresh, unique questions** every session based on resume + job role |
| **Voice Interview Loop** | WebSocket loop: TTS questions → candidate speaks → Whisper STT → LLM scores |
| **Adaptive Follow-ups** | If score < 6/10, LLM generates a targeted follow-up question automatically |
| **LLM Scoring** | 4-dimension rubric: Accuracy · Clarity · Depth · Relevance (0–10 each) |
| **PDF Scorecards** | ReportLab PDF with scores, recommendation, and LLM-written assessment |
| **Email Delivery** | Scorecard PDF emailed to candidate via SendGrid |
| **Live Camera** | Browser webcam preview during the interview (local only, not recorded) |
| **Dashboard** | Session history, average scores, hire recommendations |

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + WebSocket |
| LLM | Google Gemini 1.5 Pro / OpenAI GPT-4o |
| RAG | LangChain + ChromaDB |
| STT | OpenAI Whisper (local) |
| TTS | ElevenLabs / gTTS |
| Database | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Cache/Queue | Redis + Celery |
| Storage | MinIO (local) / AWS S3 (prod) |
| PDF | ReportLab |
| Email | SendGrid |

---

## 🚀 Quickstart (Local)

### Prerequisites
- Python 3.11+
- Docker Desktop
- FFmpeg (`winget install ffmpeg` on Windows)

### Step 1 — Clone & configure
```bash
git clone <your-repo>
cd Ai_Interviewer_AntiGravity
copy .env.example .env
# Edit .env and set at minimum:
#   GOOGLE_API_KEY=your-gemini-key  (or OPENAI_API_KEY)
#   LLM_PROVIDER=gemini
```

### Step 2 — Start infrastructure
```bash
docker-compose up postgres redis minio -d
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Run DB migrations
```bash
alembic upgrade head
```

### Step 5 — Seed question bank into ChromaDB
```bash
python scripts/seed_question_bank.py
```

### Step 6 — Start the API
```bash
uvicorn app.main:app --reload --port 8000
```

### Step 7 — Start Celery worker (separate terminal)
```bash
celery -A app.tasks.celery_app worker --loglevel=info -Q scoring,pdf,email
```

---

## 📡 API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/auth/register` | Register candidate |
| POST | `/auth/login` | Login → JWT tokens |
| GET | `/auth/me` | Current user profile |
| POST | `/resume/upload` | Upload PDF/DOCX resume |
| GET | `/resume/{id}` | Get parsed resume |
| POST | `/interview/sessions` | Create session + generate questions |
| POST | `/interview/sessions/{id}/start` | Start session |
| WS | `/voice/interview/{session_id}` | WebSocket interview loop |
| POST | `/voice/transcribe` | Standalone STT |
| POST | `/voice/synthesize` | Standalone TTS |
| GET | `/scoring/session/{id}` | Get all scores |
| GET | `/scorecard/{session_id}` | Get scorecard |
| GET | `/scorecard/{session_id}/pdf` | Download PDF |
| GET | `/dashboard/stats` | Aggregate stats |
| GET | `/dashboard/sessions` | Session history |

**Swagger UI:** http://localhost:8000/docs

---

## 🔄 Interview Flow

```
Candidate uploads resume
        ↓
POST /interview/sessions  →  LLM generates 5 fresh questions (RAG)
                          →  TTS converts questions to audio
        ↓
WebSocket /voice/interview/{session_id}
        ↓ (for each question)
Server sends: question text + audio URL
        ↓
Candidate speaks answer (audio streamed to server)
        ↓
Whisper STT  →  transcript
        ↓
LLM scores: Accuracy · Clarity · Depth · Relevance
        ↓
If score < 6  →  LLM generates follow-up question
        ↓
Session complete  →  Celery generates PDF + sends email
```

---

## 🖥️ Service URLs

| Service | URL |
|---------|-----|
| API + Swagger | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 (minioadmin/minioadmin123) |
| Celery Flower | http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 🧪 Running Tests

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## 📁 Project Structure

```
app/
├── main.py              # FastAPI app factory
├── config.py            # All settings (pydantic-settings)
├── database.py          # SQLAlchemy async engine
├── dependencies.py      # JWT auth dependency
├── models/              # SQLAlchemy ORM (6 tables)
├── schemas/             # Pydantic request/response
├── routers/             # API route handlers
├── services/            # Business logic
│   ├── resume_parser.py
│   ├── question_generator.py   ← LLM, fresh questions every session
│   ├── voice_engine.py         ← Whisper STT + gTTS/ElevenLabs TTS
│   ├── scoring_engine.py       ← LLM 4-dimension scorer
│   ├── scorecard_service.py    ← PDF generation
│   └── email_service.py
├── vector_store/        # ChromaDB client (3 collections)
├── llm/                 # LLM client + all prompt templates
└── tasks/               # Celery background jobs
```

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes* | Gemini API key |
| `OPENAI_API_KEY` | Yes* | OpenAI API key (*one of these required) |
| `LLM_PROVIDER` | Yes | `gemini` or `openai` |
| `DATABASE_URL` | Yes | PostgreSQL async URL |
| `REDIS_URL` | Yes | Redis connection URL |
| `SECRET_KEY` | Yes | JWT signing secret |
| `WHISPER_MODEL_SIZE` | No | `tiny/base/small/medium/large` (default: base) |
| `ELEVENLABS_API_KEY` | No | Premium TTS (falls back to gTTS if empty) |
| `SENDGRID_API_KEY` | No | Email delivery (logs to console if empty) |

---

## 📝 License

MIT
