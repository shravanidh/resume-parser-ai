from flask import Flask, request, jsonify, render_template_string
import pdfplumber
import spacy
import re
import json
import os
from datetime import datetime
import docx2txt

app = Flask(__name__)

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# In-memory database (simulating PostgreSQL)
candidates_db = []
candidate_id_counter = 1

# ─── Skill Keywords ────────────────────────────────────────────────────────────
SKILL_KEYWORDS = {
    "programming": ["python", "java", "javascript", "typescript", "c++", "c#", "ruby", "go", "rust", "swift", "kotlin", "php", "scala", "r", "matlab"],
    "web": ["react", "angular", "vue", "node.js", "django", "flask", "fastapi", "spring", "express", "html", "css", "sass", "tailwind", "bootstrap"],
    "data": ["pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras", "spark", "hadoop", "tableau", "power bi", "sql", "nosql"],
    "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "jenkins", "github actions"],
    "databases": ["postgresql", "mysql", "mongodb", "redis", "elasticsearch", "sqlite", "oracle", "dynamodb"],
    "tools": ["git", "linux", "agile", "scrum", "jira", "confluence", "figma", "postman", "rest api", "graphql"],
}

# ─── Text Extraction ───────────────────────────────────────────────────────────
def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    return text

def extract_text_from_docx(file_path):
    return docx2txt.process(file_path)

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    return ""

# ─── Information Extraction ────────────────────────────────────────────────────
def extract_email(text):
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None

def extract_phone(text):
    pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    matches = re.findall(pattern, text)
    return ''.join(matches[0]).strip() if matches else None

def extract_name(text, doc):
    lines = text.strip().split('\n')
    for line in lines[:5]:
        line = line.strip()
        if len(line.split()) >= 2 and len(line) < 50:
            # Check if it looks like a name (no special chars, no email/phone)
            if not re.search(r'[@|/\\|0-9]', line) and not re.search(r'resume|cv|curriculum', line, re.I):
                return line
    # Fallback: spaCy NER
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return "Unknown"

def extract_skills(text):
    text_lower = text.lower()
    found_skills = {}
    for category, skills in SKILL_KEYWORDS.items():
        matched = [skill for skill in skills if re.search(r'\b' + re.escape(skill) + r'\b', text_lower)]
        if matched:
            found_skills[category] = matched
    return found_skills

def extract_education(text, doc):
    education = []
    edu_keywords = ["bachelor", "master", "phd", "b.sc", "m.sc", "b.tech", "m.tech", "mba", "b.e", "m.e",
                    "university", "college", "institute", "school", "degree"]
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in edu_keywords):
            entry = line.strip()
            if i + 1 < len(lines) and lines[i+1].strip():
                entry += " | " + lines[i+1].strip()
            if entry and len(entry) > 5:
                education.append(entry[:200])
    # Deduplicate
    seen = set()
    unique_edu = []
    for e in education:
        if e not in seen:
            seen.add(e)
            unique_edu.append(e)
    return unique_edu[:5]

def extract_experience(text):
    experience = []
    exp_keywords = ["experience", "work history", "employment", "career", "position", "worked at"]
    job_title_keywords = ["engineer", "developer", "manager", "analyst", "designer", "scientist",
                          "intern", "consultant", "lead", "architect", "director", "coordinator"]
    lines = text.split('\n')
    in_experience_section = False
    for line in lines:
        line_lower = line.lower().strip()
        if any(kw in line_lower for kw in exp_keywords):
            in_experience_section = True
        if in_experience_section and any(kw in line_lower for kw in job_title_keywords):
            if len(line.strip()) > 5:
                experience.append(line.strip()[:200])
        if len(experience) >= 5:
            break
    return experience

def extract_years_of_experience(text):
    patterns = [
        r'(\d+)\+?\s*years?\s*of\s*experience',
        r'(\d+)\+?\s*years?\s*experience',
        r'experience\s*of\s*(\d+)\+?\s*years?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1))
    return None

def extract_linkedin(text):
    pattern = r'linkedin\.com/in/[\w-]+'
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else None

def extract_github(text):
    pattern = r'github\.com/[\w-]+'
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else None

def parse_resume(file_path):
    text = extract_text(file_path)
    if not text:
        return None
    doc = nlp(text[:100000])  # Limit to avoid memory issues
    
    skills = extract_skills(text)
    all_skills = [skill for skills_list in skills.values() for skill in skills_list]
    
    return {
        "name": extract_name(text, doc),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "linkedin": extract_linkedin(text),
        "github": extract_github(text),
        "skills": skills,
        "all_skills": all_skills,
        "education": extract_education(text, doc),
        "experience": extract_experience(text),
        "years_of_experience": extract_years_of_experience(text),
        "raw_text_preview": text[:500],
        "parsed_at": datetime.now().isoformat(),
    }

# ─── Routes ────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Resume Parser</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0f0f13; color: #e2e8f0; min-height: 100vh; }
  
  .header { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e1b4b 100%); padding: 40px 20px; text-align: center; border-bottom: 1px solid #4c1d95; }
  .header h1 { font-size: 2.4rem; font-weight: 800; background: linear-gradient(135deg, #a78bfa, #818cf8, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
  .header p { color: #a5b4fc; font-size: 1rem; }
  
  .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
  
  .upload-section { background: #1a1a2e; border: 2px dashed #4c1d95; border-radius: 16px; padding: 50px 30px; text-align: center; margin-bottom: 30px; transition: all 0.3s; cursor: pointer; }
  .upload-section:hover { border-color: #7c3aed; background: #1e1b4b; }
  .upload-section.dragover { border-color: #a78bfa; background: #1e1b4b; transform: scale(1.01); }
  .upload-icon { font-size: 3rem; margin-bottom: 15px; }
  .upload-section h2 { font-size: 1.3rem; color: #c4b5fd; margin-bottom: 8px; }
  .upload-section p { color: #6b7280; font-size: 0.9rem; margin-bottom: 20px; }
  
  .file-input { display: none; }
  .btn { padding: 12px 28px; border: none; border-radius: 10px; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
  .btn-primary { background: linear-gradient(135deg, #7c3aed, #6366f1); color: white; }
  .btn-primary:hover { background: linear-gradient(135deg, #6d28d9, #4f46e5); transform: translateY(-1px); box-shadow: 0 8px 25px rgba(124,58,237,0.4); }
  .btn-secondary { background: #1e1b4b; color: #a78bfa; border: 1px solid #4c1d95; }
  .btn-secondary:hover { background: #2d2a5e; }
  
  .selected-file { margin-top: 15px; padding: 10px 16px; background: #1e1b4b; border-radius: 8px; display: inline-block; color: #a78bfa; font-size: 0.9rem; }
  
  .progress-bar { height: 4px; background: #1e1b4b; border-radius: 2px; margin: 20px 0; overflow: hidden; display: none; }
  .progress-fill { height: 100%; background: linear-gradient(90deg, #7c3aed, #6366f1, #a78bfa); border-radius: 2px; animation: loading 1.5s ease infinite; }
  @keyframes loading { 0% { width: 0%; } 50% { width: 70%; } 100% { width: 100%; } }
  
  .result-card { background: #1a1a2e; border: 1px solid #2d2a5e; border-radius: 16px; padding: 28px; margin-bottom: 20px; }
  .result-card h3 { font-size: 1.1rem; color: #a78bfa; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  
  .info-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
  .info-item { background: #0f0f1a; border: 1px solid #2d2a5e; border-radius: 10px; padding: 14px; }
  .info-label { font-size: 0.75rem; color: #6366f1; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .info-value { color: #e2e8f0; font-size: 0.95rem; word-break: break-word; }
  .info-value.empty { color: #4b5563; font-style: italic; }
  
  .skill-categories { display: flex; flex-direction: column; gap: 12px; }
  .skill-category { }
  .category-label { font-size: 0.75rem; color: #7c3aed; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .skill-tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .skill-tag { padding: 5px 12px; background: #1e1b4b; border: 1px solid #4c1d95; border-radius: 20px; font-size: 0.82rem; color: #a78bfa; }
  .skill-tag.highlight { background: linear-gradient(135deg, #4c1d95, #3730a3); border-color: #7c3aed; color: #e0d9ff; }
  
  .list-items { display: flex; flex-direction: column; gap: 8px; }
  .list-item { padding: 10px 14px; background: #0f0f1a; border-left: 3px solid #4c1d95; border-radius: 0 8px 8px 0; font-size: 0.88rem; color: #cbd5e1; line-height: 1.4; }
  
  .candidates-section { margin-top: 40px; }
  .candidates-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
  .candidates-header h2 { font-size: 1.4rem; color: #c4b5fd; }
  .badge { background: linear-gradient(135deg, #7c3aed, #6366f1); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; }
  
  .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
  .search-input { flex: 1; padding: 10px 16px; background: #1a1a2e; border: 1px solid #2d2a5e; border-radius: 10px; color: #e2e8f0; font-size: 0.95rem; outline: none; }
  .search-input:focus { border-color: #7c3aed; }
  
  .candidate-card { background: #1a1a2e; border: 1px solid #2d2a5e; border-radius: 12px; padding: 20px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: flex-start; gap: 15px; transition: all 0.2s; }
  .candidate-card:hover { border-color: #4c1d95; background: #1e1b4b; }
  .candidate-info h4 { color: #c4b5fd; font-size: 1rem; margin-bottom: 4px; }
  .candidate-info p { color: #6b7280; font-size: 0.85rem; }
  .candidate-skills { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
  .mini-tag { padding: 3px 8px; background: #1e1b4b; border: 1px solid #3730a3; border-radius: 12px; font-size: 0.75rem; color: #818cf8; }
  
  .score { text-align: center; min-width: 60px; }
  .score-number { font-size: 1.6rem; font-weight: 800; background: linear-gradient(135deg, #a78bfa, #6366f1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .score-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; }
  
  .error-msg { background: #1a0a0a; border: 1px solid #7f1d1d; color: #fca5a5; padding: 14px 18px; border-radius: 10px; margin-top: 15px; }
  .success-msg { background: #0a1a0a; border: 1px solid #14532d; color: #86efac; padding: 14px 18px; border-radius: 10px; margin-top: 15px; }
  
  .tabs { display: flex; gap: 4px; margin-bottom: 20px; background: #0f0f13; padding: 4px; border-radius: 10px; width: fit-content; }
  .tab { padding: 8px 20px; border-radius: 8px; cursor: pointer; font-size: 0.9rem; color: #6b7280; transition: all 0.2s; }
  .tab.active { background: #1e1b4b; color: #a78bfa; font-weight: 600; }
  
  .empty-state { text-align: center; padding: 60px 20px; color: #4b5563; }
  .empty-state .icon { font-size: 3rem; margin-bottom: 12px; }
  
  #resultsArea { display: none; }
</style>
</head>
<body>

<div class="header">
  <h1>🎯 Resume Parser AI</h1>
  <p>Extract and categorize candidate information with NLP intelligence</p>
</div>

<div class="container">

  <!-- Upload Section -->
  <div class="upload-section" id="dropZone">
    <div class="upload-icon">📄</div>
    <h2>Drop your resume here</h2>
    <p>Supports PDF and DOCX files · Powered by spaCy NLP</p>
    <input type="file" id="fileInput" class="file-input" accept=".pdf,.docx,.doc">
    <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">Choose File</button>
    <div id="selectedFile"></div>
  </div>

  <div class="progress-bar" id="progressBar">
    <div class="progress-fill"></div>
  </div>

  <div id="statusMsg"></div>

  <!-- Results Section -->
  <div id="resultsArea">
    <h2 style="font-size:1.3rem; color:#c4b5fd; margin-bottom:20px;">✨ Parsed Results</h2>
    
    <div class="result-card">
      <h3>👤 Personal Information</h3>
      <div class="info-grid" id="personalInfo"></div>
    </div>

    <div class="result-card">
      <h3>⚡ Skills Detected</h3>
      <div class="skill-categories" id="skillsInfo"></div>
    </div>

    <div class="result-card">
      <h3>🎓 Education</h3>
      <div class="list-items" id="educationInfo"></div>
    </div>

    <div class="result-card">
      <h3>💼 Work Experience</h3>
      <div class="list-items" id="experienceInfo"></div>
    </div>
  </div>

  <!-- Candidates Database -->
  <div class="candidates-section">
    <div class="candidates-header">
      <h2>🗄️ Candidates Database</h2>
      <span class="badge" id="candidateCount">0 candidates</span>
    </div>
    
    <div class="search-box">
      <input type="text" class="search-input" id="searchInput" placeholder="Search by name, skill, or education..." oninput="filterCandidates()">
      <button class="btn btn-secondary" onclick="loadCandidates()">Refresh</button>
    </div>
    
    <div id="candidatesList">
      <div class="empty-state">
        <div class="icon">📭</div>
        <p>No candidates yet. Upload a resume to get started!</p>
      </div>
    </div>
  </div>

</div>

<script>
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
let allCandidates = [];

// Drag and Drop
dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener('change', (e) => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

function handleFile(file) {
  const validTypes = ['.pdf', '.docx', '.doc'];
  const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
  if (!validTypes.includes(ext)) {
    showStatus('Please upload a PDF or DOCX file.', 'error');
    return;
  }
  document.getElementById('selectedFile').innerHTML = `<div class="selected-file">📎 ${file.name}</div>`;
  uploadFile(file);
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append('resume', file);
  
  showProgress(true);
  showStatus('', '');
  document.getElementById('resultsArea').style.display = 'none';

  try {
    const res = await fetch('/parse', { method: 'POST', body: formData });
    const data = await res.json();
    showProgress(false);
    
    if (data.error) {
      showStatus('Error: ' + data.error, 'error');
    } else {
      showStatus('Resume parsed and saved successfully!', 'success');
      displayResults(data);
      loadCandidates();
    }
  } catch (err) {
    showProgress(false);
    showStatus('Upload failed. Please try again.', 'error');
  }
}

function displayResults(data) {
  document.getElementById('resultsArea').style.display = 'block';

  // Personal Info
  const personal = [
    { label: 'Full Name', value: data.name },
    { label: 'Email', value: data.email },
    { label: 'Phone', value: data.phone },
    { label: 'LinkedIn', value: data.linkedin },
    { label: 'GitHub', value: data.github },
    { label: 'Years of Experience', value: data.years_of_experience ? data.years_of_experience + ' years' : null },
  ];
  document.getElementById('personalInfo').innerHTML = personal.map(item => `
    <div class="info-item">
      <div class="info-label">${item.label}</div>
      <div class="info-value ${!item.value ? 'empty' : ''}">${item.value || 'Not found'}</div>
    </div>
  `).join('');

  // Skills
  const skills = data.skills;
  if (Object.keys(skills).length === 0) {
    document.getElementById('skillsInfo').innerHTML = '<p style="color:#6b7280">No skills detected</p>';
  } else {
    document.getElementById('skillsInfo').innerHTML = Object.entries(skills).map(([cat, items]) => `
      <div class="skill-category">
        <div class="category-label">${cat}</div>
        <div class="skill-tags">${items.map(s => `<span class="skill-tag highlight">${s}</span>`).join('')}</div>
      </div>
    `).join('');
  }

  // Education
  document.getElementById('educationInfo').innerHTML = data.education.length
    ? data.education.map(e => `<div class="list-item">${e}</div>`).join('')
    : '<div style="color:#6b7280">No education details found</div>';

  // Experience
  document.getElementById('experienceInfo').innerHTML = data.experience.length
    ? data.experience.map(e => `<div class="list-item">${e}</div>`).join('')
    : '<div style="color:#6b7280">No experience details found</div>';
}

async function loadCandidates() {
  const res = await fetch('/candidates');
  allCandidates = await res.json();
  renderCandidates(allCandidates);
}

function renderCandidates(candidates) {
  document.getElementById('candidateCount').textContent = candidates.length + ' candidate' + (candidates.length !== 1 ? 's' : '');
  if (!candidates.length) {
    document.getElementById('candidatesList').innerHTML = `<div class="empty-state"><div class="icon">📭</div><p>No candidates yet.</p></div>`;
    return;
  }
  document.getElementById('candidatesList').innerHTML = candidates.map(c => `
    <div class="candidate-card">
      <div class="candidate-info">
        <h4>${c.name}</h4>
        <p>${c.email || 'No email'} ${c.phone ? '· ' + c.phone : ''}</p>
        ${c.years_of_experience ? `<p style="color:#a78bfa; margin-top:3px">${c.years_of_experience} yrs experience</p>` : ''}
        <div class="candidate-skills">
          ${(c.all_skills || []).slice(0, 8).map(s => `<span class="mini-tag">${s}</span>`).join('')}
          ${(c.all_skills || []).length > 8 ? `<span class="mini-tag">+${c.all_skills.length - 8}</span>` : ''}
        </div>
      </div>
      <div class="score">
        <div class="score-number">${(c.all_skills || []).length}</div>
        <div class="score-label">skills</div>
      </div>
    </div>
  `).join('');
}

function filterCandidates() {
  const query = document.getElementById('searchInput').value.toLowerCase();
  if (!query) { renderCandidates(allCandidates); return; }
  const filtered = allCandidates.filter(c =>
    (c.name || '').toLowerCase().includes(query) ||
    (c.all_skills || []).some(s => s.toLowerCase().includes(query)) ||
    (c.education || []).some(e => e.toLowerCase().includes(query)) ||
    (c.email || '').toLowerCase().includes(query)
  );
  renderCandidates(filtered);
}

function showProgress(show) {
  document.getElementById('progressBar').style.display = show ? 'block' : 'none';
}

function showStatus(msg, type) {
  const el = document.getElementById('statusMsg');
  if (!msg) { el.innerHTML = ''; return; }
  el.innerHTML = `<div class="${type === 'error' ? 'error-msg' : 'success-msg'}">${msg}</div>`;
}

loadCandidates();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/parse", methods=["POST"])
def parse():
    global candidate_id_counter
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files["resume"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".doc"]:
        return jsonify({"error": "Unsupported file type"}), 400
    
    # Save temporarily
    tmp_path = os.path.join(os.getcwd(), f"resume_{candidate_id_counter}{ext}")
    file.save(tmp_path)
    
    result = parse_resume(tmp_path)
    os.remove(tmp_path)
    
    if not result:
        return jsonify({"error": "Could not extract text from file"}), 400
    
    result["id"] = candidate_id_counter
    result["filename"] = file.filename
    candidates_db.append(result)
    candidate_id_counter += 1
    
    return jsonify(result)

@app.route("/candidates")
def get_candidates():
    # Return sanitized list
    return jsonify([{
        "id": c["id"],
        "name": c["name"],
        "email": c["email"],
        "phone": c["phone"],
        "all_skills": c["all_skills"],
        "education": c["education"],
        "years_of_experience": c["years_of_experience"],
        "parsed_at": c["parsed_at"],
    } for c in candidates_db])

@app.route("/candidates/<int:cid>")
def get_candidate(cid):
    for c in candidates_db:
        if c["id"] == cid:
            return jsonify(c)
    return jsonify({"error": "Not found"}), 404

@app.route("/search")
def search():
    q = request.args.get("q", "").lower()
    if not q:
        return jsonify(candidates_db)
    results = [c for c in candidates_db if
        q in (c["name"] or "").lower() or
        any(q in s for s in c["all_skills"]) or
        any(q in e.lower() for e in c["education"])]
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
