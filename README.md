# 🎙️ Meeting Intelligence — AI-Powered Meeting Analysis System

A complete end-to-end AI application that converts meeting recordings into structured intelligence: transcripts, summaries, action items, and deadline detection.

---

## 📁 Project Structure

```
meeting-intelligence/
│
├── app.py                    # Main entry point (FastAPI server + frontend)
├── setup.py                  # One-click installation script
├── requirements.txt          # Python dependencies
│
├── backend/
│   └── api.py                # All REST API endpoints (FastAPI)
│
├── models/
│   ├── transcriber.py        # Whisper speech-to-text + audio extraction
│   └── nlp_processor.py      # T5 summarization + task/deadline extraction
│
├── database/
│   ├── db.py                 # SQLite schema + all DB operations
│   └── meetings.db           # SQLite database (auto-created)
│
├── utils/
│   └── auth.py               # JWT authentication + password hashing
│
└── static/
    └── index.html            # Complete SPA frontend (HTML/CSS/JS)
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla HTML/CSS/JavaScript (SPA, no build step) |
| Backend | Python FastAPI + Uvicorn |
| Speech-to-Text | OpenAI Whisper (`openai-whisper`) |
| Summarization | DistilBART / T5 (`transformers` / HuggingFace) |
| NLP Extraction | Rule-based regex + keyword patterns |
| Database | SQLite (built-in Python, no server needed) |
| Authentication | JWT tokens + bcrypt password hashing |

---

## 🚀 Installation & Setup

### Prerequisites

- **Python 3.10+**
- **ffmpeg** (for audio/video conversion)

Install ffmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt update && sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html, add to PATH
```

### Option A: Automated Setup (Recommended)

```bash
cd meeting-intelligence
python setup.py
```

### Option B: Manual Setup

```bash
cd meeting-intelligence

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Download NLP model (optional)
python -m spacy download en_core_web_sm
```

---

## ▶️ Running the Application

```bash
python app.py
```

Then open your browser: **http://localhost:8000**

- **Frontend**: http://localhost:8000
- **API docs (Swagger)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔐 Authentication

1. Open http://localhost:8000
2. Click **"Create Account"** to register
3. Log in with your credentials
4. JWT token is stored in localStorage for session persistence

---

## 📥 How to Use

### 1. Upload
- Navigate to **Upload** in the sidebar
- Drag & drop or click to browse for your meeting file
- Supported: `.mp4`, `.mp3`, `.wav`, `.m4a`, `.avi`, `.mov`, `.ogg`, `.flac`

### 2. Processing
Watch the live step-by-step progress:
1. File upload
2. Audio transcription (Whisper)
3. Summary generation (T5/BART)
4. Action item extraction
5. Deadline detection
6. Database storage

### 3. Results
View the complete analysis:
- **Summary** — concise meeting overview
- **Action Items** — extracted tasks with keyword detection
- **Deadlines** — temporal expressions with highlighted time references
- **Full Transcript** — cleaned speech-to-text output

### 4. Dashboard
- Overview stats (total meetings, tasks, deadlines)
- Latest meeting banner
- Recent meetings list

### 5. History
- Full searchable meeting history
- Filter by keyword or date
- Click any meeting for detailed view

### 6. Export
Each meeting can be exported as:
- **JSON** — machine-readable structured data
- **TXT** — formatted human-readable report

---

## 🗄️ Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Meetings table
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    transcript TEXT,
    summary TEXT,
    tasks TEXT,           -- JSON array of task strings
    deadlines TEXT,       -- JSON array of {sentence, expressions} objects
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Register new user |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user info |
| POST | `/api/meetings/upload` | Upload & process file |
| GET | `/api/meetings` | List meetings (search, date filter) |
| GET | `/api/meetings/latest` | Latest meeting |
| GET | `/api/meetings/{id}` | Get meeting by ID |
| DELETE | `/api/meetings/{id}` | Delete meeting |
| GET | `/api/meetings/{id}/export/json` | Export as JSON |
| GET | `/api/meetings/{id}/export/txt` | Export as TXT |
| GET | `/api/health` | Health check |

All endpoints except auth require `Authorization: Bearer <token>` header.

---

## 🧠 AI Models

### Whisper (Speech-to-Text)
- Model: `base` (default) — good balance of speed/accuracy
- Upgrade to `small`, `medium`, or `large` for better accuracy
- Change in `models/transcriber.py` → `transcribe(file_path, model_size="small")`

### Summarization (T5/BART)
- Default: `sshleifer/distilbart-cnn-12-6` (fast, good quality)
- Falls back to extractive summarization if model fails to load
- First run downloads model (~1GB) from HuggingFace

### Task Extraction
- Keyword patterns: `will, should, must, need to, responsible for, follow up...`
- Filters out past-tense sentences (already completed)
- Deduplicates similar tasks

### Deadline Detection
- 30+ temporal patterns: `today, tomorrow, next week, by Friday, in 3 days, Q1...`
- Returns both the sentence context and the specific expressions found

---

## ⚡ Performance Notes

- **First run** downloads Whisper (~140MB) and BART (~1GB) models
- Subsequent runs use cached models
- GPU acceleration: Set `fp16=True` in transcriber.py and `device=0` in nlp_processor.py
- For CPU-only systems, use Whisper `tiny` or `base` model size

---

## 🔧 Configuration

Environment variables (create `.env` file):
```env
SECRET_KEY=your-secure-secret-key-here
```

---

## 📋 Requirements

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-multipart==0.0.9
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
openai-whisper==20231117
transformers==4.40.0
torch==2.2.2
sentencepiece==0.2.0
accelerate==0.29.3
ffmpeg-python==0.2.0
pydub==0.25.1
spacy==3.7.4
dateparser==1.2.0
python-dotenv==1.0.1
aiofiles==23.2.1
numpy==1.26.4
jinja2==3.1.4
```

---

## 🛠️ Troubleshooting

**"ffmpeg not found"**
→ Install ffmpeg and ensure it's in your system PATH

**"CUDA out of memory"**
→ Set `fp16=False` in transcriber.py and `device=-1` in nlp_processor.py

**Model download fails**
→ Check internet connection; models download from HuggingFace on first use

**Transcription is slow**
→ Use smaller Whisper model (`tiny` or `base`), or enable GPU

**Database errors**
→ Delete `database/meetings.db` and restart to reinitialize

---

## 📄 License

MIT License — free for personal and commercial use.
