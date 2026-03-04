# 🎯 Automated Resume Parser

An intelligent resume parsing system that extracts and categorizes candidate information using NLP.

## Tech Stack
- **Backend**: Python, Flask
- **NLP**: spaCy (en_core_web_sm)
- **PDF Parsing**: pdfplumber
- **DOCX Parsing**: docx2txt
- **Database**: PostgreSQL (with in-memory fallback for dev)

## Features
- 📄 Upload PDF / DOCX resumes
- 👤 Extract: Name, Email, Phone, LinkedIn, GitHub
- ⚡ Categorize skills: Programming, Web, Data, Cloud, Databases, Tools
- 🎓 Detect education entries
- 💼 Extract work experience
- 🗄️ Store all candidates in searchable database
- 🔍 Search by name, skill, or education

## Quick Start

### Option 1: Docker (Recommended)
```bash
docker-compose up --build
```

### Option 2: Local
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python app.py
```

Visit: http://localhost:5000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/` | Web UI |
| POST | `/parse` | Upload & parse resume |
| GET  | `/candidates` | List all candidates |
| GET  | `/candidates/<id>` | Get candidate details |
| GET  | `/search?q=python` | Search candidates |

## Database Schema (PostgreSQL)
```sql
candidates (
  id, name, email, phone, linkedin, github,
  skills JSONB, all_skills TEXT[],
  education TEXT[], experience TEXT[],
  years_of_experience, raw_text_preview,
  filename, parsed_at
)
```
