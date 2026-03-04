CREATE TABLE IF NOT EXISTS candidates (
    id          SERIAL PRIMARY KEY,
    name        TEXT,
    email       TEXT,
    phone       TEXT,
    linkedin    TEXT,
    github      TEXT,
    skills      JSONB DEFAULT '{}',
    all_skills  TEXT[] DEFAULT '{}',
    education   TEXT[] DEFAULT '{}',
    experience  TEXT[] DEFAULT '{}',
    years_of_experience INTEGER,
    raw_text_preview    TEXT,
    filename    TEXT,
    parsed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_candidates_email ON candidates(email);
CREATE INDEX idx_candidates_skills ON candidates USING gin(all_skills);
CREATE INDEX idx_candidates_name ON candidates(name);
