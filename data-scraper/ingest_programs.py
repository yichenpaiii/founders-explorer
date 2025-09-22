# ingest_programs.py
import json, re, ast, sys, os
from pathlib import Path

# Ensure data directory exists
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

JSON_PATH = DATA_DIR / "programs_tree.json"
# Ensure the JSON file exists and is at least an empty JSON object
if (not JSON_PATH.exists()) or JSON_PATH.stat().st_size == 0:
    JSON_PATH.write_text("{}\n", encoding="utf-8")

# Define a separate rename map file and ensure it exists
RENAMES_PATH = DATA_DIR / "program_renames.json"
# Ensure the renames file exists and is at least an empty JSON object
if (not RENAMES_PATH.exists()) or RENAMES_PATH.stat().st_size == 0:
    RENAMES_PATH.write_text("{}\n", encoding="utf-8")

# === Paste the whole set literal (including the braces) between the triple quotes ===
RAW_SET_LITERAL = ['Computational science and Engineering, 2025-2026, Master semester 2', 'Sustainable Construction minor, 2025-2026, Autumn semester', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 2', 'Physics, 2025-2026, Bachelor semester 3', 'Data and Internet of Things minor, 2025-2026, Autumn semester', 'Architecture, 2025-2026, Bachelor semester 6b', 'Neuroscience (edoc), 2025-2026', 'Communication Systems, 2025-2026, Bachelor semester 1', 'Minor in Imaging, 2025-2026, Spring semester', 'Quantum Science and Engineering, 2025-2026, Master semester 2', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 3', 'Microengineering minor, 2025-2026, Spring semester', 'Minor in Engineering for sustainability, 2025-2026, Autumn semester', 'Humanities and Social Sciences Program, 2025-2026, Bachelor semester 3', 'Nuclear engineering, 2025-2026, Master semester 2', 'Electrical and Electronics Engineering, 2025-2026, Master semester 3', 'Computational science and Engineering, 2025-2026, Master semester 1', 'Materials Science and Engineering, 2025-2026, Master semester 2', 'Quantum Science and Engineering, 2025-2026, Master Project autumn', 'Mechanical Engineering, 2025-2026, Bachelor semester 4', 'Data science minor, 2025-2026, Autumn semester', 'Biomedical technologies minor, 2025-2026, Spring semester', 'Applied Mathematics, 2025-2026, Master semester 1', 'Minor in life sciences engineering\n, 2025-2026, Spring semester', 'Applied Physics, 2025-2026, Master Project spring', 'Architecture, 2025-2026, Master semester 4', 'Architecture, 2025-2026, Master Project spring', 'Systems Engineering minor, 2025-2026, Autumn semester', 'Architecture and Sciences of the City (edoc), 2025-2026', 'Applied Mathematics, 2025-2026, Master semester 3', 'Microengineering, 2025-2026, Master semester 2', 'Mathematics, 2025-2026, Bachelor semester 1', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 1', 'Computer Science, 2025-2026, Bachelor semester 4', 'Data science minor, 2025-2026, Spring semester', 'Chemical Engineering and Biotechnology, 2025-2026, Master semester 3', 'Data Science, 2025-2026, Master semester 2', 'Passerelle HES - GC, 2025-2026, Autumn semester', 'Passerelle HES - CGC, 2025-2026, Autumn semester', 'Computer Science - Cybersecurity, 2025-2026, Master semester 3', 'Life Sciences Engineering, 2025-2026, Bachelor semester 5', 'AR Exchange, 2025-2026, Spring semester', 'Management, Technology and Entrepreneurship, 2025-2026, Master semester 2', 'Applied Physics, 2025-2026, Master semester 4', 'Computer and Communication Sciences (edoc), 2025-2026', 'Sustainable Management and Technology, 2026-2027, Autumn semester', 'Biotechnology and Bioengineering (edoc), 2025-2026', 'Neuro-X, 2025-2026, Master Project spring', 'Chemical Engineering and Biotechnology, 2025-2026, Master semester 2', 'Communication Systems - master program, 2025-2026, Master semester 3', 'Energy Science and Technology, 2025-2026, Master Project autumn', 'Molecular & Biological Chemistry, 2025-2026, Master semester 2', 'Mathematics (edoc), 2025-2026', 'AR Exchange, 2025-2026, Autumn semester', 'Civil Engineering, 2025-2026, Master Project spring', 'Chemical Engineering, 2025-2026, Bachelor semester 5', 'Chemical Engineering and Biotechnology, 2025-2026, Master Project spring', 'Computer Science - Cybersecurity, 2025-2026, Master semester 4', 'Mechanical Engineering, 2025-2026, Bachelor semester 5', 'Computer Science, 2025-2026, Master Project spring', 'Life Sciences Engineering, 2025-2026, Bachelor semester 1', 'Microengineering, 2025-2026, Master semester 1', 'Neuro-X minor, 2025-2026, Spring semester', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 1', 'Civil and Environmental Engineering (edoc), 2025-2026', 'Physics - master program, 2025-2026, Master Project autumn', 'Environmental Sciences and Engineering, 2025-2026, Master semester 4', 'Applied Physics, 2025-2026, Master semester 3', 'Robotics, Control and Intelligent Systems (edoc), 2025-2026', 'Civil Engineering, 2025-2026, Bachelor semester 1', 'Computer Science, 2025-2026, Master semester 3', 'Microengineering, 2025-2026, Bachelor semester 6', 'Mathematics, 2025-2026, Bachelor semester 4', 'Joint EPFL - ETH Zurich Doctoral Program in the Learning Sciences, 2025-2026', 'Mechanical Engineering, 2025-2026, Master semester 4', 'Communication Systems - master program, 2025-2026, Master semester 1', 'Financial engineering, 2025-2026, Master semester 4', 'Physics - master program, 2025-2026, Master semester 2', 'Management, Technology and Entrepreneurship minor, 2025-2026, Autumn semester', 'Mechanical engineering minor, 2025-2026, Autumn semester', 'Molecular & Biological Chemistry, 2025-2026, Master Project autumn', 'Applied Mathematics, 2025-2026, Master Project autumn', 'Urban systems, 2025-2026, Master semester 2', 'Energy minor, 2025-2026, Spring semester', 'Humanities and Social Sciences Program, 2025-2026, Bachelor semester 5', 'Financial engineering minor, 2025-2026, Autumn semester', 'Passerelle HES - GC, 2025-2026, Spring semester', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 6', 'Data Science, 2025-2026, Master Project autumn', 'Space technologies minor, 2025-2026, Autumn semester', 'Materials Science and Engineering, 2025-2026, Bachelor semester 3', 'Finance (edoc), 2025-2026', 'Financial engineering minor, 2025-2026, Spring semester', 'Mathematics - master program, 2025-2026, Master Project spring', 'Energy Science and Technology, 2025-2026, Admission autumn', 'Chemistry and Chemical Engineering, 2025-2026, Bachelor semester 4', 'Digital Humanities, 2025-2026, Master semester 4', 'Chemistry and Chemical Engineering (edoc), 2025-2026', 'Energy minor, 2025-2026, Autumn semester', 'Energy Science and Technology, 2025-2026, Master semester 2', 'Advanced Manufacturing (edoc), 2025-2026', 'Life Sciences Engineering, 2025-2026, Master Project autumn', 'Minor in Engineering for sustainability, 2025-2026, Spring semester', 'Statistics, 2025-2026, Master semester 2', 'Physics (edoc), 2025-2026', 'Microsystems and Microelectronics (edoc), 2025-2026', 'Architecture, 2025-2026, Bachelor semester 5b', 'Physics - master program, 2025-2026, Master semester 4', 'Humanities and Social Sciences Program, 2025-2026, Master semester 2', 'Passerelle HES - IC, 2025-2026, Spring semester', 'Computer Science - Cybersecurity, 2025-2026, Master semester 1', 'Physics - master program, 2025-2026, Master semester 1', 'Environmental Sciences and Engineering, 2025-2026, Master semester 3', 'Microengineering, 2025-2026, Bachelor semester 4', 'Territories in transformation and climate minor, 2025-2026, Spring semester', 'Minor in Integrated Design, Architecture and Sustainability, 2025-2026, Spring semester', 'Communication Systems, 2025-2026, Bachelor semester 3', 'Computer Science - Cybersecurity, 2025-2026, Master semester 2', 'Life Sciences Engineering, 2025-2026, Bachelor semester 6', 'Management, Technology and Entrepreneurship, 2025-2026, Master semester 3', 'Mathematics - master program, 2025-2026, Master semester 3', 'Materials Science and Engineering, 2025-2026, Bachelor semester 4', 'Chemistry, 2025-2026, Bachelor semester 6', 'Minor in Imaging, 2025-2026, Autumn semester', 'Applied Mathematics, 2025-2026, Master semester 4', 'Biotechnology minor, 2025-2026, Autumn semester', 'Photonics (edoc), 2025-2026', 'UNIL - Autres facultés, 2025-2026, Autumn semester', 'Mathematics - master program, 2025-2026, Master semester 1', 'Computer science minor, 2025-2026, Spring semester', 'Auditeurs en ligne, 2025-2026, Spring semester', 'Molecular & Biological Chemistry, 2025-2026, Master semester 3', 'Minor in statistics, 2025-2026, Autumn semester', 'Computational science and engineering minor, 2025-2026, Autumn semester', 'Applied Physics, 2025-2026, Master semester 1', 'UNIL - Sciences forensiques, 2025-2026, Autumn semester', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 3', 'Communication Systems, 2025-2026, Bachelor semester 4', 'Micro- and Nanotechnologies for Integrated Systems, 2025-2026, Master semester 4', 'Physics, 2025-2026, Bachelor semester 4', 'Civil Engineering, 2025-2026, Master semester 3', 'Computer science minor, 2025-2026, Autumn semester', 'Passerelle HES - AR, 2025-2026, Spring semester', 'Molecular & Biological Chemistry, 2025-2026, Master semester 1', 'Physics, 2025-2026, Bachelor semester 2', 'Passerelle HES - CGC, 2025-2026, Spring semester', 'Computer Science, 2025-2026, Master Project autumn', 'Mechanical Engineering, 2025-2026, Master semester 1', 'Minor in digital humanities, media and society, 2025-2026, Autumn semester', 'Financial engineering, 2025-2026, Master semester 1', 'Materials Science and Engineering, 2025-2026, Master Project autumn', 'Architecture, 2025-2026, Master semester 1', 'Humanities and Social Sciences Program, 2025-2026, Bachelor semester 6', 'Mechanical Engineering, 2025-2026, Master Project spring', 'Computer Science, 2025-2026, Master semester 4', 'Computer Science, 2025-2026, Master semester 2', 'Physics, 2025-2026, Bachelor semester 1', 'Nuclear engineering, 2025-2026, Master semester 4', 'Quantum Science and Engineering, 2025-2026, Master Project spring', 'Chemical Engineering and Biotechnology, 2025-2026, Master semester 4', 'Physics of living systems minor, 2025-2026, Spring semester', 'Civil Engineering, 2025-2026, Bachelor semester 2', 'Mechanical Engineering, 2025-2026, Bachelor semester 3', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 5', 'Civil Engineering, 2025-2026, Master semester 1', 'UNIL - HEC, 2025-2026, Autumn semester', 'Architecture, 2025-2026, Bachelor semester 6', 'Mechanical Engineering, 2025-2026, Bachelor semester 2', 'Neuro-X, 2025-2026, Master semester 3', 'Computer Science - Cybersecurity, 2025-2026, Master Project autumn', 'Materials Science and Engineering (edoc), 2025-2026', 'Chemistry and Chemical Engineering, 2025-2026, Bachelor semester 2', 'Life Sciences Engineering, 2025-2026, Bachelor semester 3', 'Quantum Science and Engineering, 2025-2026, Master semester 3', 'Civil Engineering, 2025-2026, Bachelor semester 4', 'Management of technology (edoc), 2025-2026', 'Neuro-X, 2025-2026, Master semester 1', 'Architecture, 2025-2026, Master semester 3', 'Nuclear engineering, 2025-2026, Master semester 1', 'Materials Science and Engineering, 2025-2026, Bachelor semester 6', 'Energy Science and Technology, 2025-2026, Admission spring', 'Physics - master program, 2025-2026, Master Project spring', 'Photonics minor, 2025-2026, Spring semester', 'Civil Engineering, 2025-2026, Bachelor semester 3', 'Financial engineering, 2025-2026, Master semester 3', 'Digital Humanities, 2025-2026, Master semester 3', 'Life Sciences Engineering, 2025-2026, Master semester 3', 'Environmental Sciences and Engineering, 2025-2026, Master semester 2', 'Microengineering, 2025-2026, Bachelor semester 2', 'Neuro-X minor, 2025-2026, Autumn semester', 'Minor in Integrated Design, Architecture and Sustainability, 2025-2026, Autumn semester', 'Passerelle HES - SIE, 2025-2026, Autumn semester', 'Statistics, 2025-2026, Master semester 4', 'Digital Humanities, 2025-2026, Master semester 1', 'Minor in life sciences engineering\n, 2025-2026, Autumn semester', 'UNIL - Autres facultés, 2025-2026, Spring semester', 'Environmental Sciences and Engineering, 2025-2026, Master Project spring', 'Architecture, 2025-2026, Bachelor semester 3', 'Environmental Sciences and Engineering, 2025-2026, Master Project autumn', 'Quantum Science and Engineering, 2025-2026, Master semester 4', 'Nuclear engineering, 2025-2026, Master Project autumn', 'Computer Science, 2025-2026, Bachelor semester 6', 'Management, Technology and Entrepreneurship minor, 2025-2026, Spring semester', 'Biomedical technologies minor, 2025-2026, Autumn semester', 'Computational science and Engineering, 2025-2026, Master semester 3', 'Electrical and Electronics Engineering, 2025-2026, Master semester 4', 'Sustainable Management and Technology, 2025-2026, Master semester 2', 'Digital humanities (edoc), 2025-2026', 'Territories in transformation and climate minor, 2025-2026, Autumn semester', 'Data Science, 2025-2026, Master semester 1', 'Materials Science and Engineering, 2025-2026, Bachelor semester 2', 'Mechanical Engineering, 2025-2026, Bachelor semester 1', 'Computational science and Engineering, 2025-2026, Master Project autumn', 'Computational science and engineering minor, 2025-2026, Spring semester', 'Applied Physics, 2025-2026, Master Project autumn', 'Molecular Life Sciences (edoc), 2025-2026', 'Urban systems, 2025-2026, Master semester 1', 'Computational biology minor, 2025-2026, Spring semester', 'Energy Science and Technology, 2025-2026, Master semester 3', 'Materials Science and Engineering, 2025-2026, Bachelor semester 5', 'Communication Systems, 2025-2026, Bachelor semester 5', 'Mathematics, 2025-2026, Bachelor semester 2', 'Robotics, 2025-2026, Master semester 2', 'Life Sciences Engineering, 2025-2026, Master semester 1', 'Robotics, 2025-2026, Master Project spring', 'Life Sciences Engineering, 2025-2026, Master semester 2', 'Microengineering, 2025-2026, Bachelor semester 5', 'Humanities and Social Sciences Program, 2025-2026, Master semester 1', 'Communication Systems, 2025-2026, Bachelor semester 2', 'Mathematics - master program, 2025-2026, Master semester 2', 'Cyber security minor, 2025-2026, Spring semester', 'Architecture, 2025-2026, Bachelor semester 4', 'Architecture, 2025-2026, Bachelor semester 2', 'Neuro-X, 2025-2026, Master Project autumn', 'Life Sciences Engineering, 2025-2026, Bachelor semester 2', 'Statistics, 2025-2026, Master semester 1', 'UNIL - Collège des sciences, 2025-2026, Autumn semester', 'Passerelle HES - AR, 2025-2026, Autumn semester', 'Financial engineering, 2025-2026, Master semester 2', 'Electrical Engineering (edoc), 2025-2026', 'Physics of living systems minor, 2025-2026, Autumn semester', 'Civil Engineering, 2025-2026, Bachelor semester 5', 'Architecture, 2025-2026, Bachelor semester 1', 'Microengineering, 2025-2026, Master semester 4', 'Mathematics, 2025-2026, Bachelor semester 5', 'Passerelle HES - MT, 2025-2026, Spring semester', 'Applied Mathematics, 2025-2026, Master semester 2', 'Electrical and electronic engineering minor, 2025-2026, Spring semester', 'Physics, 2025-2026, Bachelor semester 6', 'Civil Engineering, 2025-2026, Master semester 4', 'Passerelle HES - SIE, 2025-2026, Spring semester', 'Materials Science and Engineering, 2025-2026, Master Project spring', 'Microengineering minor, 2025-2026, Autumn semester', 'Minor in statistics, 2025-2026, Spring semester', 'Civil engineering minor, 2024-2025, Autumn semester', 'Quantum Science and Engineering, 2025-2026, Master semester 1', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 6', 'Mathematics, 2025-2026, Bachelor semester 3', 'Sustainable Management and Technology, 2025-2026, Master semester 1', 'Computer Science, 2025-2026, Bachelor semester 3', 'Communication Systems, 2025-2026, Bachelor semester 6', 'Sustainable Management and Technology, 2025-2026, Master semester 3', 'Space technologies minor, 2025-2026, Spring semester', 'Computer Science, 2025-2026, Bachelor semester 1', 'Materials Science and Engineering, 2025-2026, Master semester 4', 'Passerelle HES - EL, 2025-2026, Autumn semester', 'Civil Engineering, 2025-2026, Master Project autumn', 'Chemical Engineering and Biotechnology, 2025-2026, Master semester 1', 'Photonics minor, 2025-2026, Autumn semester', 'Communication Systems - master program, 2025-2026, Master Project autumn', 'Chemical Engineering and Biotechnology, 2025-2026, Master Project autumn', 'Humanities and Social Sciences Program, 2025-2026, Bachelor semester 4', 'Molecular & Biological Chemistry, 2025-2026, Master Project spring', 'Passerelle HES - GM, 2025-2026, Autumn semester', 'Computer Science - Cybersecurity, 2025-2026, Master Project spring', 'Passerelle HES - IC, 2025-2026, Autumn semester', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 5', 'Chemistry and Chemical Engineering, 2025-2026, Bachelor semester 1', 'Nuclear engineering, 2025-2026, Master semester 3', 'Life Sciences Engineering, 2025-2026, Master Project spring', 'Robotics, 2025-2026, Master semester 3', 'Chemical Engineering, 2025-2026, Bachelor semester 6', 'Energy Science and Technology, 2025-2026, Master semester 1', 'Computational biology minor, 2025-2026, Autumn semester', 'Data Science, 2025-2026, Master semester 4', 'Energy (edoc), 2025-2026', 'Passerelle HES - GM, 2025-2026, Spring semester', 'Electrical and Electronics Engineering, 2025-2026, Master semester 2', 'UNIL - Sciences forensiques, 2025-2026, Spring semester', 'Electrical and Electronics Engineering, 2025-2026, Master semester 1', 'Life Sciences Engineering, 2025-2026, Bachelor semester 4', 'Electrical and Electronics Engineering, 2025-2026, Master Project autumn', 'Auditeurs en ligne, 2025-2026, Autumn semester', 'Nuclear engineering, 2025-2026, Master Project spring', 'Electrical and electronic engineering minor, 2025-2026, Autumn semester', 'Molecular & Biological Chemistry, 2025-2026, Master semester 4', 'Minor in digital humanities, media and society, 2025-2026, Spring semester', 'Systems Engineering minor, 2025-2026, Spring semester', 'Passerelle HES - MT, 2025-2026, Autumn semester', 'Data Science, 2025-2026, Master semester 3', 'Communication systems minor, 2025-2026, Autumn semester', 'Applied Mathematics, 2025-2026, Master Project spring', 'Physics - master program, 2025-2026, Master semester 3', 'UNIL - HEC, 2025-2026, Spring semester', 'Humanities and Social Sciences Program, 2025-2026, Bachelor semester 2', 'Hors plans, 2025-2026, Autumn semester', 'Civil engineering minor, 2025-2026, Autumn semester', 'Civil engineering minor, 2025-2026, Spring semester', 'Mechanical Engineering, 2025-2026, Master Project autumn', 'Statistics, 2025-2026, Master Project autumn', 'Chemistry, 2025-2026, Bachelor semester 5', 'Mechanical Engineering, 2025-2026, Master semester 3', 'Management, Technology and Entrepreneurship, 2025-2026, Master semester 1', 'Architecture, 2025-2026, Master semester 2', 'Microengineering, 2025-2026, Bachelor semester 3', 'Statistics, 2025-2026, Master semester 3', 'Data Science, 2025-2026, Master Project spring', 'Mechanical engineering minor, 2025-2026, Spring semester', 'Life Sciences Engineering, 2025-2026, Master semester 4', 'Micro- and Nanotechnologies for Integrated Systems, 2025-2026, Master Project spring', 'Architecture, 2025-2026, Master Project autumn', 'Robotics, 2025-2026, Master semester 4', 'Civil Engineering, 2025-2026, Master semester 2', 'Minor in Quantum Science and Engineering, 2025-2026, Spring semester', 'Mechanical Engineering, 2025-2026, Master semester 2', 'Materials Science and Engineering, 2025-2026, Master semester 3', 'Biotechnology minor, 2025-2026, Spring semester', 'Computational and Quantitative Biology (edoc), 2025-2026', 'Computer Science, 2025-2026, Bachelor semester 2', 'Computational science and Engineering, 2025-2026, Master semester 4', 'Microengineering, 2025-2026, Master Project autumn', 'Mechanical Engineering, 2025-2026, Bachelor semester 6', 'Neuro-X, 2025-2026, Master semester 2', 'Materials Science and Engineering (edoc), 2024-2025', 'Management, Technology and Entrepreneurship, 2025-2026, Master semester 4', 'Sustainable Construction minor, 2025-2026, Spring semester', 'Mathematics, 2025-2026, Bachelor semester 6', 'Materials Science and Engineering, 2025-2026, Bachelor semester 1', 'Communication Systems - master program, 2025-2026, Master Project spring', 'Energy Science and Technology, 2025-2026, Master semester 4', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 2', 'Passerelle HES - EL, 2025-2026, Spring semester', 'Energy Science and Technology, 2025-2026, Master Project spring', 'Communication systems minor, 2025-2026, Spring semester', 'Environmental Sciences and Engineering, 2025-2026, Bachelor semester 4', 'Micro- and Nanotechnologies for Integrated Systems, 2025-2026, Master semester 3', 'Data and Internet of Things minor, 2025-2026, Spring semester', 'Electrical and Electronics Engineering, 2025-2026, Master Project spring', 'Electrical and Electronics Engineering, 2025-2026, Bachelor semester 4', 'Neuro-X, 2025-2026, Master semester 4', 'Microengineering, 2025-2026, Master semester 3', 'Architecture, 2025-2026, Bachelor semester 5', 'Digital Humanities, 2025-2026, Master semester 2', 'Microengineering, 2025-2026, Master Project spring', 'Environmental Sciences and Engineering, 2025-2026, Master semester 1', 'UNIL - Collège des sciences, 2025-2026, Spring semester', 'Applied Physics, 2025-2026, Master semester 2', 'Statistics, 2025-2026, Master Project spring', 'Microengineering, 2025-2026, Bachelor semester 1', 'Minor in Quantum Science and Engineering, 2025-2026, Autumn semester', 'Computer Science, 2025-2026, Bachelor semester 5', 'Communication Systems - master program, 2025-2026, Master semester 2', 'Communication Systems - master program, 2025-2026, Master semester 4', 'Computer Science, 2025-2026, Master semester 1', 'Architecture and Sciences of the City (edoc), 2024-2025', 'Physics, 2025-2026, Bachelor semester 5', 'Civil Engineering, 2025-2026, Bachelor semester 6', 'Chemistry and Chemical Engineering, 2025-2026, Bachelor semester 3', 'Robotics, 2025-2026, Master semester 1', 'Mathematics - master program, 2025-2026, Master Project autumn', 'Mechanics (edoc), 2025-2026', 'Materials Science and Engineering, 2025-2026, Master semester 1', 'Cyber security minor, 2025-2026, Autumn semester', 'Computational science and Engineering, 2025-2026, Master Project spring', 'Robotics, 2025-2026, Master Project autumn']
# --- helpers ---

BA_KEYS = [f"BA{i}" for i in range(1,7)]
MA_KEYS = [f"MA{i}" for i in range(1,5)]
MA_PROJECT_AUTUMN = "MA Project Autumn"
MA_PROJECT_SPRING = "MA Project Spring"
MINOR_AUTUMN = "Minor Autumn Semester"
MINOR_SPRING = "Minor Spring Semester"

MASTER_PROGRAM_PHRASE = re.compile(r"\s*-\s*master program\s*", re.IGNORECASE)

def clean_master_phrase(s: str) -> str:
    return MASTER_PROGRAM_PHRASE.sub(" ", s).strip()

def detect_bucket_and_name(item: str):
    s = re.sub(r"\s{2,}", " ", item.strip())
    s_no_mp = clean_master_phrase(s)

    # Normalize comma-separated EPFL labels like
    #   "Program, 2025-2026, Master semester 2"
    # into level/key + base name.
    parts = [p.strip() for p in s_no_mp.split(',') if p.strip()]
    # Drop year-like tokens (e.g., 2025-2026)
    parts = [p for p in parts if not re.search(r"\b\d{4}\s*-\s*\d{4}\b", p)]
    if len(parts) >= 2:
        base_name = parts[0]
        tail = parts[-1]
        # edoc programs e.g., "Advanced Manufacturing (edoc), 2025-2026"
        if re.search(r"(?i)\(edoc\)", base_name):
            clean_base = re.sub(r"(?i)\s*\(edoc\)\s*", " ", base_name).strip()
            return ("PhD", "edoc", clean_base)
        # 1) Master/Bachelor semester N → MA/BA keys
        m_ma_sem = re.search(r"(?i)\bmaster\s+semester\s*([1-4])\b", tail)
        if m_ma_sem:
            key = f"MA{m_ma_sem.group(1)}"
            return ("MA", key, base_name)
        m_ba_sem = re.search(r"(?i)\bbachelor\s+semester\s*([1-6])[a-b]?\b", tail)
        if m_ba_sem:
            key = f"BA{m_ba_sem.group(1)}"
            return ("BA", key, base_name)
        # 2) Master Project autumn/spring → special MA keys
        m_proj = re.search(r"(?i)\bmaster\s+project\s+(autumn|spring)\b", tail)
        if m_proj:
            season = m_proj.group(1).lower()
            return ("MA", MA_PROJECT_AUTUMN if season == 'autumn' else MA_PROJECT_SPRING, base_name)
        # 3) Minor Autumn/Spring semester → map to Minor buckets
        if (re.search(r"(?i)\bautumn\s+semester\b", tail) or re.search(r"(?i)\bspring\s+semester\b", tail)) and re.search(r"(?i)\bminor\b|^\s*Minor in\b", base_name):
            is_aut = bool(re.search(r"(?i)\bautumn\s+semester\b", tail))
            # Extract core name for variants like "Minor in X" or "X minor"
            nm = base_name
            m_in = re.search(r"(?i)^Minor in\s+(.*)$", nm)
            if m_in:
                nm = m_in.group(1).strip()
            else:
                m_tail = re.search(r"(?i)^(.*)\s+minor$", nm)
                if m_tail:
                    nm = m_tail.group(1).strip()
            return ("MA", MINOR_AUTUMN if is_aut else MINOR_SPRING, nm)

    # (1) edoc → PhD/edoc (fallback, robust to year and position)
    if re.search(r"\(edoc\)", s_no_mp, re.IGNORECASE):
        base = re.sub(r"\s*\(edoc\)\s*", " ", s_no_mp, flags=re.IGNORECASE)
        base = re.sub(r"\b\d{4}\s*-\s*\d{4}\b", "", base)
        base = re.sub(r"\s*,\s*$", "", base).strip()
        # If a comma remains after removing years, keep left-most as base
        if "," in base:
            base = base.split(",", 1)[0].strip()
        return ("PhD", "edoc", base)

    # (2) minor … semester → MA / Minor Autumn|Spring Semester
    minor_aut = re.search(r"\bminor\b.*\bautumn semester\b", s_no_mp, re.IGNORECASE)
    minor_spr = re.search(r"\bminor\b.*\bspring semester\b", s_no_mp, re.IGNORECASE)

    if minor_aut or minor_spr:
        # Patterns:
        # "Minor in X Autumn semester" -> capture X
        # "X minor Autumn semester"    -> capture X
        name = s_no_mp
        # Try "Minor in X …"
        m_in = re.search(r"^Minor in\s+(.*?)\s+(Autumn|Spring)\s+semester$", name, re.IGNORECASE)
        if m_in:
            name = m_in.group(1).strip()
        else:
            # Try "X minor …"
            m_tail = re.search(r"^(.*?)\s+minor\s+(Autumn|Spring)\s+semester$", name, re.IGNORECASE)
            if m_tail:
                name = m_tail.group(1).strip()
            else:
                # Fallback: strip trailing "minor ..." if present
                name = re.sub(r"\s+minor\s+(Autumn|Spring)\s+semester$", "", name, flags=re.IGNORECASE).strip()

        return ("MA", MINOR_AUTUMN if minor_aut else MINOR_SPRING, name)

    # (3) MA Project autumn/spring
    if re.search(r"\bMA\s+Project\s+autumn\b", s_no_mp, re.IGNORECASE):
        base = re.sub(r"\bMA\s+Project\s+autumn\b", "", s_no_mp, flags=re.IGNORECASE).strip()
        return ("MA", MA_PROJECT_AUTUMN, base)
    if re.search(r"\bMA\s+Project\s+spring\b", s_no_mp, re.IGNORECASE):
        base = re.sub(r"\bMA\s+Project\s+spring\b", "", s_no_mp, flags=re.IGNORECASE).strip()
        return ("MA", MA_PROJECT_SPRING, base)

    # (4) MA1..MA4
    m_ma = re.search(r"\b(MA[1-4])\b$", s_no_mp, re.IGNORECASE)
    if m_ma:
        key = m_ma.group(1).upper()
        base = re.sub(rf"\s*\b{key}\b\s*$", "", s_no_mp, flags=re.IGNORECASE).strip()
        return ("MA", key, base)

    # (5) BA1..BA6
    m_ba = re.search(r"\b(BA[1-6])\b$", s_no_mp, re.IGNORECASE)
    if m_ba:
        key = m_ba.group(1).upper()
        base = re.sub(rf"\s*\b{key}\b\s*$", "", s_no_mp, flags=re.IGNORECASE).strip()
        return ("BA", key, base)

    # Not matched → unknown
    return (None, None, s_no_mp)

def normalize_name(name: str) -> str:
    # compact whitespace
    name = re.sub(r"\s{2,}", " ", (name or "")).strip()
    if not name:
        return name
    # Smart title case: keep all-caps words (EPFL/ETH), lowercase small words except at start
    small = {"and","or","of","in","for","the","a","an","to","on","at","by","with"}
    def cap_word(w: str, is_first: bool) -> str:
        if not w:
            return w
        # Preserve all-caps words and words containing digits
        if (len(w) > 1 and w.isupper()) or re.search(r"\d", w):
            return w
        # Handle hyphenated words
        if '-' in w:
            parts = w.split('-')
            return '-'.join(cap_word(p, True) for p in parts)
        lw = w.lower()
        if not is_first and lw in small:
            return lw
        return lw[0:1].upper() + lw[1:]
    tokens = name.split()
    out = [cap_word(tokens[0], True)] + [cap_word(t, False) for t in tokens[1:]] if tokens else []
    return " ".join(out)


# --- Renaming helpers ---
def canonicalize_key(s: str) -> str:
    """Create a stable, case-insensitive key for name matching.
    Keeps letters, digits and a few separators; collapses whitespace.
    """
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    # Keep common separators but drop other punctuation to be forgiving
    s = re.sub(r"[^a-z0-9&+/\- ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def apply_renames(name: str, renames: dict) -> str:
    """Map many old names to one canonical new name using program_renames.json.
    The JSON should be a dict where KEYS are canonicalized old-name strings
    (we canonicalize user-provided keys the same way) and VALUES are the
    desired canonical display names.
    """
    key = canonicalize_key(name)
    # Try direct key; also allow raw key just in case the user stored it un-normalized
    return renames.get(key) or renames.get(name) or name

def format_program_label(level: str, key: str, base: str) -> str:
    """Build the canonical display label used in our JSON buckets.
    Examples:
      (MA, MA2, "Computational Science and Engineering") -> "MA2 Computational Science and Engineering"
      (BA, BA3, "Physics") -> "BA3 Physics"
      (MA, MA Project Spring, "Applied Physics") -> "MA Project Spring Applied Physics"
      (MA, Minor Autumn Semester, "Imaging") -> "Minor Autumn Semester Imaging"
      (PhD, edoc, "Advanced Manufacturing") -> "edoc Advanced Manufacturing"
    Returns empty string when level/key cannot be formatted.
    """
    base_n = normalize_name(base or "")
    if not base_n:
        return ""
    if level == "MA" and key and (key in MA_KEYS or key in (MA_PROJECT_AUTUMN, MA_PROJECT_SPRING, MINOR_AUTUMN, MINOR_SPRING)):
        return f"{key} {base_n}".strip()
    if level == "BA" and key and key in BA_KEYS:
        return f"{key} {base_n}".strip()
    if level == "PhD" and key == "edoc":
        return f"edoc {base_n}".strip()
    return base_n

def main():
    # Load existing data, tolerating an empty or invalid JSON file
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except json.JSONDecodeError:
            print("WARNING: JSON was empty or invalid; starting with a fresh structure.")
            data = {}

    # Load optional rename mapping for multi→one name consolidation
    with open(RENAMES_PATH, "r", encoding="utf-8") as f:
        try:
            renames = json.load(f)
            if not isinstance(renames, dict):
                renames = {}
        except json.JSONDecodeError:
            print("WARNING: program_renames.json was empty or invalid; ignoring renames.")
            renames = {}

    program_items = RAW_SET_LITERAL

    # Auto-generate raw→formatted mapping and merge into program_renames.json
    added_mappings = 0
    for raw in program_items:
        lvl, key, base = detect_bucket_and_name(raw)
        formatted = format_program_label(lvl, key, base)
        if not formatted:
            continue
        can_key = canonicalize_key(raw)
        # Only add if not already present to avoid clobbering manual curation
        if renames.get(can_key) != formatted:
            renames[can_key] = formatted
            added_mappings += 1
        # Also store exact raw key for convenience if absent
        if renames.get(raw) != formatted:
            renames[raw] = formatted
            added_mappings += 1

    # Build mutable sets from existing lists to dedupe
    buckets = {
        "BA": {k: set(v) for k, v in data.get("BA", {}).items()},
        "MA": {k: set(v) for k, v in data.get("MA", {}).items()},
        "PhD": {k: set(v) for k, v in data.get("PhD", {}).items()},
    }

    unknown = []
    renamed_count = 0

    for item in sorted(program_items):
        level, key, base = detect_bucket_and_name(item)
        base = normalize_name(base)
        original_base = base
        base = apply_renames(base, renames)
        renamed_count = renamed_count + (1 if base != original_base else 0)
        if level in ("BA", "MA", "PhD") and key:
            # ensure bucket exists
            if key not in buckets[level]:
                buckets[level][key] = set()
            buckets[level][key].add(base)
        else:
            unknown.append(item)

    # Write back to data (sorted lists)
    for lvl in ("BA", "MA", "PhD"):
        if lvl not in data:
            data[lvl] = {}
        for k, vset in buckets[lvl].items():
            data[lvl].setdefault(k, [])
            data[lvl][k] = sorted(vset)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Persist updated renames mapping
    with open(RENAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(renames, f, indent=2, ensure_ascii=False)

    # Summary
    print("=== Update complete ===")
    for lvl in ("BA", "MA", "PhD"):
        keys = sorted(buckets[lvl].keys())
        print(f"{lvl}: {', '.join(keys)}")
        for k in keys:
            print(f"  - {k}: {len(buckets[lvl][k])} entries")
    print(f"Renames applied: {renamed_count}")
    print(f"Raw→formatted mappings written: {added_mappings}")
    if unknown:
        print("\nUnclassified items (please review / map manually):")
        for u in unknown:
            print("  •", u)

if __name__ == "__main__":
    main()
