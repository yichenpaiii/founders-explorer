# ingest_programs.py
import json, re, ast, sys
from pathlib import Path

JSON_PATH = Path("programs_tree.json")
# Ensure the JSON file exists and is at least an empty JSON object
if (not JSON_PATH.exists()) or JSON_PATH.stat().st_size == 0:
    JSON_PATH.write_text("{}\n", encoding="utf-8")

# === Paste the whole set literal (including the braces) between the triple quotes ===
RAW_SET_LITERAL = ['Materials Science and Engineering BA3', 'Microengineering MA Project autumn', 'Physics BA4', 'Passerelle HES - GM Spring semester', 'Mathematics - master program MA Project autumn', 'Materials Science and Engineering MA4', 'Minor in Quantum Science and Engineering Autumn semester', 'Molecular & Biological Chemistry MA3', 'Electrical and Electronics Engineering MA3', 'Electrical and Electronics Engineering BA3', 'Applied Physics MA Project spring', 'Computer science minor Spring semester', 'Electrical and Electronics Engineering BA2', 'Minor in Engineering for sustainability Autumn semester', 'Data Science MA3', 'Communication Systems BA5', 'Environmental Sciences and Engineering BA4', 'Electrical and Electronics Engineering MA2', 'Environmental Sciences and Engineering BA1', 'Financial engineering MA3', 'Microengineering BA6', 'Financial engineering MA2', 'Microengineering BA2', 'Energy Science and Technology Admission autumn', 'Civil Engineering BA1', 'Physics - master program MA3', 'Sustainable Construction minor Autumn semester', 'Electrical and Electronics Engineering MA4', 'Digital Humanities MA2', 'Photonics minor Spring semester', 'Photonics (edoc)', 'Physics - master program MA Project spring', 'Territories in transformation and climate minor Spring semester', 'Chemistry BA5', 'UNIL - HEC Autumn semester', 'Electrical and Electronics Engineering MA1', 'Computational science and Engineering MA4', 'Communication Systems - master program MA4', 'Computational science and Engineering MA Project autumn', 'Architecture MA4', 'Energy Science and Technology Admission spring', 'Humanities and Social Sciences Program BA2', 'Territories in transformation and climate minor Autumn semester', 'Environmental Sciences and Engineering BA2', 'Mathematics - master program MA3', 'Applied Mathematics MA3', 'Civil and Environmental Engineering (edoc)', 'Electrical and electronic engineering minor Autumn semester', 'Life Sciences Engineering BA2', 'Computer Science - Cybersecurity MA Project spring', 'Materials Science and Engineering BA4', 'Robotics MA4', 'Physics of living systems minor Spring semester', 'Architecture MA2', 'Minor in Imaging Autumn semester', 'Electrical and Electronics Engineering BA6', 'Architecture BA6', 'Mechanical Engineering MA1', 'Materials Science and Engineering MA2', 'Physics BA1', 'Computer Science - Cybersecurity MA3', 'Life Sciences Engineering BA5', 'Mathematics (edoc)', 'Molecular & Biological Chemistry MA2', 'Micro- and Nanotechnologies for Integrated Systems MA Project spring', 'Neuro-X minor Spring semester', 'Civil Engineering BA3', 'Minor in digital humanities media and society  Spring semester', 'Microengineering MA4', 'Urban systems MA2', 'Statistics MA Project spring', 'Mechanical engineering minor Spring semester', 'Minor in Integrated Design Architecture and Sustainability  Autumn semester', 'Photonics minor Autumn semester', 'Biotechnology minor Autumn semester', 'Robotics MA1', 'Financial engineering minor Spring semester', 'Sustainable Management and Technology MA2', 'Computer Science BA6', 'Civil Engineering MA4', 'Computational science and Engineering MA Project spring', 'Chemical Engineering BA5', 'Computational science and Engineering MA3', 'Life Sciences Engineering MA1', 'Molecular & Biological Chemistry MA4', 'UNIL - Collège des sciences Spring semester', 'Materials Science and Engineering BA1', 'Communication systems minor Autumn semester', 'Financial engineering MA4', 'Computer Science - Cybersecurity MA4', 'Robotics MA Project autumn', 'Chemistry BA6', 'Mathematics - master program MA2', 'Computer Science BA1', 'Sustainable Management and Technology MA1', 'Chemistry and Chemical Engineering BA1', 'Environmental Sciences and Engineering MA1', 'Microengineering BA4', 'Biotechnology minor Spring semester', 'Computer Science BA2', 'Nuclear engineering MA Project autumn', 'Minor in statistics Autumn semester', 'UNIL - Autres facultés Autumn semester', 'Computer Science - Cybersecurity MA Project autumn', 'Passerelle HES - GC Spring semester', 'Life Sciences Engineering BA3', 'UNIL - Sciences forensiques Autumn semester', 'Quantum Science and Engineering MA1', 'Physics BA6', 'Civil Engineering MA3', 'Management MA4', 'Mechanical Engineering MA Project autumn', 'Mathematics BA4', 'Communication systems minor Spring semester', 'Life Sciences Engineering MA Project spring', 'Applied Mathematics MA1', 'Mechanical Engineering MA2', 'Passerelle HES - SIE Autumn semester', 'Passerelle HES - GM Autumn semester', 'Materials Science and Engineering BA6', 'Mathematics BA2', 'Urban systems MA1', 'Physics BA5', 'Space technologies minor Autumn semester', 'Materials Science and Engineering MA3', 'Applied Mathematics MA Project spring', 'Passerelle HES - GC Autumn semester', 'UNIL - Collège des sciences Autumn semester', 'Civil engineering minor Autumn semester', 'Electrical and Electronics Engineering BA5', 'Auditeurs en ligne Autumn semester', 'Applied Mathematics MA Project autumn', 'Physics (edoc)', 'Nuclear engineering MA2', 'Chemical Engineering and Biotechnology MA3', 'Computational science and Engineering MA2', 'Energy (edoc)', 'Computer science minor Autumn semester', 'Digital humanities (edoc)', 'Communication Systems BA1', 'Mechanical Engineering MA4', 'Computer Science MA4', 'Civil Engineering MA Project autumn', 'Financial engineering minor Autumn semester', 'Humanities and Social Sciences Program MA1', 'Statistics MA3', 'Minor in life sciences engineering Spring semester', 'Statistics MA4', 'Mechanical Engineering BA4', 'Materials Science and Engineering MA1', 'Architecture BA2', 'Architecture MA Project autumn', 'Electrical Engineering (edoc)', 'Cyber security minor Spring semester', 'Neuro-X MA3', 'Space technologies minor Spring semester', 'Architecture BA3', 'Data and Internet of Things minor Spring semester', 'Advanced Manufacturing (edoc)', 'Passerelle HES - MT Spring semester', 'Computational biology minor Autumn semester', 'Microengineering BA1', 'Life Sciences Engineering BA4', 'Mathematics BA6', 'Communication Systems - master program MA Project autumn', 'Computational science and engineering minor Spring semester', 'Materials Science and Engineering (edoc)', 'Quantum Science and Engineering MA Project spring', 'Architecture MA Project spring', 'Humanities and Social Sciences Program BA3', 'Nuclear engineering MA Project spring', 'Data Science MA4', 'Statistics MA2', 'Nuclear engineering MA4', 'Physics - master program MA2', 'Computer Science BA3', 'Environmental Sciences and Engineering MA2', 'Minor in life sciences engineering Autumn semester', 'Data science minor Spring semester', 'Electrical and Electronics Engineering BA1', 'Statistics MA1', 'Data science minor Autumn semester', 'Electrical and Electronics Engineering BA4', 'Passerelle HES - AR Autumn semester', 'Passerelle HES - CGC Spring semester', 'Data Science MA Project autumn', 'Life Sciences Engineering MA2', 'Quantum Science and Engineering MA2', 'Chemical Engineering and Biotechnology MA Project spring', 'Mathematics - master program MA1', 'Applied Physics MA4', 'Civil Engineering MA1', 'Applied Physics MA2', 'Electrical and Electronics Engineering MA Project spring', 'Quantum Science and Engineering MA3', 'Sustainable Management and Technology Autumn semester', 'Environmental Sciences and Engineering BA6', 'Sustainable Management and Technology MA3', 'Mathematics BA3', 'Microengineering BA5', 'Environmental Sciences and Engineering MA Project autumn', 'Environmental Sciences and Engineering MA3', 'Management MA2', 'Passerelle HES - CGC Autumn semester', 'Mechanical Engineering BA6', 'Mechanical engineering minor Autumn semester', 'Energy minor Spring semester', 'Management of technology (edoc)', 'Communication Systems - master program MA2', 'Microengineering MA3', 'Micro- and Nanotechnologies for Integrated Systems MA4', 'Microsystems and Microelectronics (edoc)', 'Life Sciences Engineering MA4', 'Microengineering minor Autumn semester', 'Energy Science and Technology MA1', 'Mechanical Engineering BA1', 'Materials Science and Engineering BA2', 'Biomedical technologies minor Spring semester', 'Energy Science and Technology MA3', 'Finance (edoc)', 'Minor in Integrated Design Architecture and Sustainability  Spring semester', 'Chemical Engineering BA6', 'Neuro-X minor Autumn semester', 'Passerelle HES - IC Autumn semester', 'Environmental Sciences and Engineering BA3', 'AR Exchange Autumn semester', 'Environmental Sciences and Engineering MA4', 'Molecular & Biological Chemistry MA Project spring', 'Computational science and Engineering MA1', 'Physics BA3', 'Sustainable Construction minor Spring semester', 'Joint EPFL - ETH Zurich Doctoral Program in the Learning Sciences', 'Applied Mathematics MA2', 'Architecture BA4', 'Humanities and Social Sciences Program MA2', 'Energy Science and Technology MA Project spring', 'Computer Science MA Project autumn', 'Quantum Science and Engineering MA4', 'Neuroscience (edoc)', 'Data Science MA1', 'Architecture BA1', 'Civil Engineering BA4', 'Communication Systems - master program MA1', 'Systems Engineering minor Spring semester', 'UNIL - Autres facultés Spring semester', 'Chemical Engineering and Biotechnology MA1', 'Molecular & Biological Chemistry MA1', 'Computer and Communication Sciences (edoc)', 'Computer Science MA1', 'Materials Science and Engineering MA Project autumn', 'Humanities and Social Sciences Program BA5', 'Architecture MA1', 'Humanities and Social Sciences Program BA6', 'Computer Science MA Project spring', 'Management Technology and Entrepreneurship minor  Autumn semester', 'Mechanics (edoc)', 'Energy Science and Technology MA4', 'Communication Systems BA3', 'Mechanical Engineering BA3', 'Micro- and Nanotechnologies for Integrated Systems MA3', 'Microengineering MA1', 'Life Sciences Engineering BA6', 'Passerelle HES - EL Autumn semester', 'Management MA1', 'Statistics MA Project autumn', 'Digital Humanities MA1', 'Mathematics - master program MA Project spring', 'Minor in Engineering for sustainability Spring semester', 'Mathematics BA5', 'Quantum Science and Engineering MA Project autumn', 'Electrical and electronic engineering minor Spring semester', 'Digital Humanities MA4', 'Nuclear engineering MA3', 'Chemical Engineering and Biotechnology MA2', 'Passerelle HES - EL Spring semester', 'Neuro-X MA4', 'Life Sciences Engineering MA Project autumn', 'Civil Engineering BA2', 'UNIL - HEC Spring semester', 'Computer Science - Cybersecurity MA2', 'Communication Systems BA4', 'Chemistry and Chemical Engineering BA2', 'Communication Systems - master program MA3', 'Civil Engineering BA5', 'Electrical and Electronics Engineering MA Project autumn', 'Mechanical Engineering MA Project spring', 'Energy Science and Technology MA Project autumn', 'Civil Engineering MA Project spring', 'Physics - master program MA Project autumn', 'Applied Physics MA Project autumn', 'Civil Engineering MA2', 'Passerelle HES - SIE Spring semester', 'Robotics MA2', 'Neuro-X MA1', 'Materials Science and Engineering MA Project spring', 'Architecture BA5', 'Nuclear engineering MA1', 'Robotics MA3', 'Data Science MA Project spring', 'Physics BA2', 'Neuro-X MA Project autumn', 'Applied Physics MA3', 'Life Sciences Engineering BA1', 'Neuro-X MA Project spring', 'Mathematics BA1', 'Environmental Sciences and Engineering MA Project spring', 'Energy Science and Technology MA2', 'Minor in Imaging Spring semester', 'Passerelle HES - IC Spring semester', 'Systems Engineering minor Autumn semester', 'Passerelle HES - AR Spring semester', 'Computer Science BA5', 'Molecular & Biological Chemistry MA Project autumn', 'Computer Science - Cybersecurity MA1', 'Microengineering BA3', 'Computational science and engineering minor Autumn semester', 'Cyber security minor Autumn semester', 'Architecture MA3', 'Minor in statistics Spring semester', 'Hors plans Autumn semester', 'Minor in digital humanities media and society  Autumn semester', 'Mechanical Engineering BA2', 'Civil Engineering BA6', 'Mechanical Engineering MA3', 'Architecture and Sciences of the City (edoc)', 'Computer Science MA3', 'Digital Humanities MA3', 'Communication Systems BA2', 'Life Sciences Engineering MA3', 'Communication Systems - master program MA Project spring', 'Environmental Sciences and Engineering BA5', 'Computer Science BA4', 'Computational and Quantitative Biology (edoc)', 'Computer Science MA2', 'Applied Mathematics MA4', 'Communication Systems BA6', 'Mechanical Engineering BA5', 'Physics of living systems minor Autumn semester', 'Chemical Engineering and Biotechnology MA4', 'Biotechnology and Bioengineering (edoc)', 'Chemistry and Chemical Engineering (edoc)', 'Biomedical technologies minor Autumn semester', 'Physics - master program MA4', 'Minor in Quantum Science and Engineering Spring semester', 'Neuro-X MA2', 'Molecular Life Sciences (edoc)', 'Robotics Control and Intelligent Systems (edoc)', 'Microengineering MA Project spring', 'AR Exchange Spring semester', 'Microengineering minor Spring semester', 'Chemistry and Chemical Engineering BA3', 'Robotics MA Project spring', 'Management Technology and Entrepreneurship minor  Spring semester', 'Management MA3', 'Chemistry and Chemical Engineering BA4', 'Financial engineering MA1', 'Physics - master program MA1', 'Microengineering MA2', 'Humanities and Social Sciences Program BA4', 'Materials Science and Engineering BA5', 'Passerelle HES - MT Autumn semester', 'Civil engineering minor Spring semester', 'UNIL - Sciences forensiques Spring semester', 'Auditeurs en ligne Spring semester', 'Computational biology minor Spring semester', 'Applied Physics MA1', 'Chemical Engineering and Biotechnology MA Project autumn', 'Data Science MA2', 'Data and Internet of Things minor Autumn semester', 'Energy minor Autumn semester']

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

    # (1) edoc → PhD/edoc
    if re.search(r"\(edoc\)", s_no_mp, re.IGNORECASE):
        base = re.sub(r"\s*\(edoc\)\s*$", "", s_no_mp, flags=re.IGNORECASE).strip()
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
    # compact whitespace; title-case acronyms remain as-is
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name

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

    program_items = RAW_SET_LITERAL

    # Build mutable sets from existing lists to dedupe
    buckets = {
        "BA": {k: set(v) for k, v in data.get("BA", {}).items()},
        "MA": {k: set(v) for k, v in data.get("MA", {}).items()},
        "PhD": {k: set(v) for k, v in data.get("PhD", {}).items()},
    }

    unknown = []

    for item in sorted(program_items):
        level, key, base = detect_bucket_and_name(item)
        base = normalize_name(base)
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

    # Summary
    print("=== Update complete ===")
    for lvl in ("BA", "MA", "PhD"):
        keys = sorted(buckets[lvl].keys())
        print(f"{lvl}: {', '.join(keys)}")
        for k in keys:
            print(f"  - {k}: {len(buckets[lvl][k])} entries")
    if unknown:
        print("\nUnclassified items (please review / map manually):")
        for u in unknown:
            print("  •", u)

if __name__ == "__main__":
    main()