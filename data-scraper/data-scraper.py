import requests
import pandas as pd
import os
from lxml import etree
import importlib
import re
import json
import html
import os
import csv
from openai import OpenAI
import sys
import time

section_codes = [
    "AR", "CGC", "CDH", "CDM", "ED", "GC", "EL",
    "GM", "IN", "MX", "MA", "MT", "NX", "PH", "SIE", "SIQ", "SV", "SHS", "SC",
    "EDAM", "EDAR", "EDBB", "EDCB", "EDCE", "EDCH", "EDDH", "EDEE", "EDEY", "EDFI",
    "EDIC", "EDMA", "EDME", "EDMI", "EDMS", "EDMT", "EDMX", "EDNE", "EDPO", "EDPY", "EDRS", "EDLS"
]

# Mapping from full section names to abbreviations (case-insensitive)
SECTION_ABBREV = {
    "section of architecture": "AR",
    "section of chemistry and chemical engineering": "CGC",
    "special mathematics courses": "CMS",
    "section of civil engineering": "GC",
    # spelling varies between Electronic/Electronical in some pages
    "section of electrical and electronical engineering": "EL",
    "section of electrical and electronic engineering": "EL",
    "section of mechanical engineering": "GM",
    "section of computer science": "IN",
    "section of materials science and engineering": "MX",
    "section of mathematics": "MA",
    "section of microtechnics": "MT",
    "neuro-x section": "NX",
    "section of physics": "PH",
    "section of environmental sciences and engineering": "SIE",
    "quantum science and engineering section": "SIQ",
    "section of life sciences engineering": "SV",
    "humanities and social sciences program": "SHS",
    "section of communication systems": "SC",
    # Doctoral programs
    "doctoral program digital humanities": "EDDH",
    "doctoral program in architecture and sciences of the city": "EDAR",
    "doctoral program in biotechnology and bioengineering": "EDBB",
    "doctoral program in chemistry and chemical engineering": "EDCH",
    "doctoral program in civil and environmental engineering": "EDCE",
    "doctoral program in computational and quantitative biology": "EDCB",
    "doctoral program in electrical engineering": "EDEE",
    "doctoral program in energy": "EDEY",
    "doctoral program in finance": "EDFI",
    "doctoral program in learning sciences": "EDLS",
    "doctoral program in materials science and engineering": "EDMX",
    "doctoral program in mathematics": "EDMA",
    "doctoral program in mechanics": "EDME",
    "doctoral program in microsystems and microelectronics": "EDMI",
    "doctoral program in molecular life sciences": "EDMS",
    "doctoral program in neuroscience": "EDNE",
    "doctoral program in photonics": "EDPO",
    "doctoral program in physics": "EDPY",
    "doctoral program in technology management": "EDMT",
    "doctoral program in advanced manufacturing": "EDAM",
    "doctoral program in computer and communication sciences": "EDIC",
    "doctoral program in robotics, control, and intelligent systems": "EDRS",
}

# Valid codes set (existing codes plus mapped values)
# VALID_SECTION_CODES = set(section_codes) | set(SECTION_ABBREV.values())
VALID_SECTION_CODES = set(SECTION_ABBREV.values())

# Normalize a raw section string for matching
_def_ws_re = re.compile(r"\s+")

def _norm(s: str) -> str:
    s = (s or "").strip()
    s = _def_ws_re.sub(" ", s)
    return s

# --- Programs tree helpers (for canonical minor names) ---
_PTREE = None
_MINOR_CANON = {  # season_bucket -> {normalized_name: Canonical Name}
    "Minor Autumn Semester": {},
    "Minor Spring Semester": {},
}
_MA_CANON = {}   # e.g., 'MA1' -> {normalized_name: Canonical}
_BA_CANON = {}   # e.g., 'BA3' -> {normalized_name: Canonical}
_EDOC_CANON = {} # 'edoc' -> {normalized_name: Canonical}

def _normalize_for_match(name: str) -> str:
    """Normalize strings to improve matching across spelling/case variants.
    - lowercase
    - replace '&' with 'and'
    - replace hyphens and slashes with spaces
    - remove non-alphanumeric characters except spaces
    - collapse whitespace
    """
    if not isinstance(name, str):
        return ""
    s = name.lower()
    s = s.replace("&", " and ")
    s = s.replace("/", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    # drop common function words to ignore minor spelling variants
    stop = {"in", "of", "the", "and", "for"}
    s = " ".join(w for w in s.split() if w not in stop)
    s = _def_ws_re.sub(" ", s).strip()
    return s

def _load_programs_tree():
    global _PTREE, _MINOR_CANON, _MA_CANON, _BA_CANON, _EDOC_CANON
    if _PTREE is not None:
        return
    try:
        here = os.path.dirname(__file__)
        path = os.path.join(here, "programs_tree.json")
        with open(path, "r", encoding="utf-8") as f:
            _PTREE = json.load(f)
        # Build canonical maps for minors by season
        ma = _PTREE.get("MA", {}) if isinstance(_PTREE, dict) else {}
        for season in ("Minor Autumn Semester", "Minor Spring Semester"):
            names = ma.get(season, []) or []
            bucket = {}
            for nm in names:
                if isinstance(nm, str) and nm.strip():
                    bucket[_normalize_for_match(nm)] = nm.strip()
            _MINOR_CANON[season] = bucket
        # Build MA level buckets MA1..MA4 and MA Project buckets if present
        for key, names in (ma or {}).items():
            if key.startswith("MA"):
                # keep only MA1..MA4 and MA Project ... buckets
                b = {}
                for nm in (names or []):
                    if isinstance(nm, str) and nm.strip():
                        b[_normalize_for_match(nm)] = nm.strip()
                _MA_CANON[key] = b
        # Build BA buckets
        ba = _PTREE.get("BA", {}) if isinstance(_PTREE, dict) else {}
        for key, names in (ba or {}).items():
            if key.startswith("BA"):
                b = {}
                for nm in (names or []):
                    if isinstance(nm, str) and nm.strip():
                        b[_normalize_for_match(nm)] = nm.strip()
                _BA_CANON[key] = b
        # Build edoc bucket
        phd = _PTREE.get("PhD", {}) if isinstance(_PTREE, dict) else {}
        edoc_list = phd.get("edoc", []) or []
        _EDOC_CANON = { _normalize_for_match(nm): nm.strip() for nm in edoc_list if isinstance(nm, str) and nm.strip() }
    except Exception as e:
        warn(f"Failed to load programs_tree.json for minor mapping: {e}")
        _PTREE = {}
        _MINOR_CANON = {"Minor Autumn Semester": {}, "Minor Spring Semester": {}}
        _MA_CANON, _BA_CANON, _EDOC_CANON = {}, {}, {}

def _extract_minor_name_and_season(raw: str):
    """From a raw available_programs label, extract (candidate_minor_name, season_bucket).
    Returns (name_str, season_str|None). Name string is raw substring without trailing season words.
    """
    if not isinstance(raw, str):
        return "", None
    s = raw.strip()
    sl = s.lower()
    season_bucket = None
    if "autumn" in sl or "fall" in sl:
        season_bucket = "Minor Autumn Semester"
    elif "spring" in sl:
        season_bucket = "Minor Spring Semester"

    # Common patterns:
    # "Minor in X Autumn semester", "Minor of X Spring semester", "X minor Spring semester"
    # Try to capture the 'X' portion.
    patterns = [
        r"minor\s+(?:in|of)\s+(.+?)(?:\s+(?:autumn|fall|spring)\s+semester\b|$)",
        r"^\s*(.+?)\s+minor(?:\s+(?:autumn|fall|spring)\s+semester\b|$)",
        r"minor\s+(?:autumn|fall|spring)\s+semester\s+(.+?)(?:\s*,?\s*\d{4}\s*-\s*\d{4}\s*,?\s*|$)",
    ]
    for pat in patterns:
        m = re.search(pat, sl, flags=re.I)
        if m:
            # Extract the original-cased substring using the span on the lowercased string length
            # Simpler: slice from original using the matched group boundaries on the lowercase; acceptable for our use.
            name_part = m.group(1) or ""
            # Remove excess punctuation/spaces
            name_part = name_part.strip(" -:/,\u2022\u2027·•")
            return name_part.strip(), season_bucket
    # Fallback: remove keywords and keep remainder
    tmp = sl
    tmp = re.sub(r"\b(minor|in|of|semester|autumn|fall|spring)\b", " ", tmp)
    tmp = _def_ws_re.sub(" ", tmp).strip()
    return tmp, season_bucket

def _strip_year_tokens(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # Remove patterns like ", 2025-2026," or "2025 - 2026"
    s2 = re.sub(r"\s*,?\s*\b\d{4}\s*(?:-\s*\d{4})\b\s*,?\s*", " ", s)
    s2 = _def_ws_re.sub(" ", s2).strip(" ,")
    return s2

def format_available_program_label(raw: str) -> str:
    """Format a single available program label.
    - For minors: map to canonical name from programs_tree using case-insensitive, spelling-normalized match,
      and return "Minor Autumn/Spring Semester <Canonical Name>".
    - Otherwise: fallback to generic formatter.
    """
    _load_programs_tree()
    txt = _fix_mojibake(raw or "").strip()
    txt = _strip_year_tokens(txt)
    if not txt:
        return ""
    low = txt.lower()
    if "minor" in low:
        cand, season = _extract_minor_name_and_season(txt)
        if not cand:
            try:
                UNMAPPED_PROGRAMS.add(txt)
            except Exception:
                pass
            return txt
        norm = _normalize_for_match(cand)
        if season:
            canon = _MINOR_CANON.get(season, {}).get(norm)
            if canon:
                return f"{season} {canon}"
        else:
            # If season missing, try both buckets to find a canonical name
            for season_guess in ("Minor Autumn Semester", "Minor Spring Semester"):
                canon = _MINOR_CANON.get(season_guess, {}).get(norm)
                if canon:
                    return f"{season_guess} {canon}"
        # If we couldn't match canonically, record and keep original text
        try:
            UNMAPPED_PROGRAMS.add(txt)
        except Exception:
            pass
        # Preserve some structure if season exists
        if season:
            return f"{season} {cand.strip()}".strip()
        return txt
    # Not a minor: use existing formatter
    return format_program_name(txt)

# HTTP headers for polite requests
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# ---- Networking & diagnostics knobs ----
CONNECT_TIMEOUT = 5  # seconds
READ_TIMEOUT = 25    # seconds
SLOW_REQ_MS = 1500   # warn if a single HTTP request exceeds this many ms
MIN_FIELDS_TO_CONSIDER_OK = 1  # if fewer than this many core fields are non-empty, warn

def warn(msg: str):
    """Print a warning to stderr immediately and flush, so it shows up in the terminal right away."""
    try:
        sys.stderr.write(f"[WARN] {msg}\n")
        sys.stderr.flush()
    except Exception:
        print(f"[WARN] {msg}")

def info(msg: str):
    try:
        sys.stderr.write(f"[INFO] {msg}\n")
        sys.stderr.flush()
    except Exception:
        print(f"[INFO] {msg}")

def _count_nonempty(*vals) -> int:
    cnt = 0
    for v in vals:
        if isinstance(v, (list, tuple, set)):
            if len(v) > 0:
                cnt += 1
        else:
            if str(v or "").strip():
                cnt += 1
    return cnt

min_keywords = 10
max_keywords = 15

# Collect program labels we cannot confidently map (for diagnostics)
UNMAPPED_PROGRAMS = set()
def _et_text(elem, path):
    try:
        # Prefer XPath when available
        nodes = elem.xpath(path) if hasattr(elem, 'xpath') else []
        if nodes:
            node = nodes[0]
            text = node if isinstance(node, str) else (node.text or "")
            return text.strip()
        # Fallback to ElementTree-style find for simple paths
        node = elem.find(path)
        return (node.text or "").strip() if node is not None else ""
    except Exception:
        return ""

# Heuristic fix for common mojibake (UTF-8 read as Latin-1/CP1252/MacRoman)
def _fix_mojibake(s: str) -> str:
    if not isinstance(s, str) or not s:
        return s
    # Fast path: if it doesn't look broken, return
    if 'Ã' not in s and '√' not in s and '\ufffd' not in s:
        return s
    candidates = []
    for enc in ('latin1', 'cp1252', 'mac_roman'):
        try:
            candidates.append(s.encode(enc, errors='ignore').decode('utf-8', errors='ignore'))
        except Exception:
            pass
    # Choose the candidate with the most accented Latin letters and fewest replacement chars
    def score(txt: str) -> int:
        if not txt:
            return -10**6
        accents = sum(ch in 'àáâäæãåāèéêëēėęîïíīįìôöòóœøōõûüùúūÿçčćñÀÁÂÄÆÃÅĀÈÉÊËĒĖĘÎÏÍĪĮÌÔÖÒÓŒØŌÕÛÜÙÚŪŸÇČĆÑ' for ch in txt)
        bad = txt.count('\ufffd') + txt.count('Ã') + txt.count('√')
        return accents - bad
    best = max(candidates + [s], key=score)
    return best or s

# --- Keyword helper functions ---
def _normalize_kw_list(kws):
    """Lowercase, strip, dedupe while preserving order"""
    seen = set()
    out = []
    for k in kws:
        kl = k.strip().lower()
        if kl and kl not in seen:
            seen.add(kl)
            out.append(kl)
    return out

# Robustly split a raw keyword string into individual keywords
# Handles JSON arrays, comma/semicolon/newline, and slash-delimited lists
def _split_keywords(raw: str):
    if not isinstance(raw, str) or not raw.strip():
        return []
    s = raw.strip()
    # Try to parse JSON array first
    try:
        data = json.loads(s)
        if isinstance(data, list):
            items = []
            for itm in data:
                if isinstance(itm, str):
                    items.append(itm)
                else:
                    items.append(str(itm))
            s = ", ".join(items)
    except Exception:
        # If it's a Python-like repr list, strip outer brackets/quotes
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
    # Split on commas, semicolons, bullets, slashes, or spaced hyphens (" - ").
    parts = re.split(r"(?:\n|,|;|\||\u2022|\u2027|•|·|/|\s+/\s+|\s-\s)", s)
    # Clean up quotes and whitespace
    cleaned = []
    for p in parts:
        t = p.strip().strip("'\"")
        if t:
            cleaned.append(t)
    return cleaned

def parse_keywords_field(raw):
    parts = _split_keywords(raw)
    parts = [_fix_mojibake(p).rstrip('.\n') for p in parts]
    return _normalize_kw_list(parts)

def format_program_name(prog: str) -> str:
    """Normalize and canonicalize a program label (non-minor) using programs_tree.
    Examples:
      - "Computer Science, 2025-2026, Master semester 1" -> "MA1 Computer Science"
      - "Architecture Master semester 2" -> "MA2 Architecture"
      - Doctoral programs -> "edoc <Canonical>"
    """
    _load_programs_tree()
    if not prog:
        return ""
    s = _strip_year_tokens(_fix_mojibake(str(prog))).strip()
    sl = s.lower()

    # Doctoral
    if any(k in sl for k in ("edoc", "phd", "doctoral")):
        # Try to find a canonical edoc program name in the string
        raw_norm = _normalize_for_match(s)
        cand = None
        best_len = -1
        for norm, canon in _EDOC_CANON.items():
            if f" {norm} " in f" {raw_norm} " or raw_norm == norm:
                if len(norm) > best_len:
                    cand = canon
                    best_len = len(norm)
        return f"edoc {cand}".strip() if cand else f"edoc {s}".strip()

    # Detect level and semester/project
    level = None
    sem = None
    project_season = None  # "MA Project Autumn" or "MA Project Spring"

    if re.search(r"\bmaster\b", sl) or re.search(r"\bma\b", sl):
        level = "MA"
    elif re.search(r"\bbachelor\b", sl) or re.search(r"\bba\b", sl):
        level = "BA"

    # MA/BA + explicit semester number
    m = re.search(r"semester\s*(\d)", sl)
    if m:
        sem = m.group(1)

    # Short forms like "MA2" or "BA3"
    if sem is None:
        m2 = re.search(r"\b(ma|ba)\s*(\d)\b", sl, flags=re.I)
        if m2:
            level = m2.group(1).upper()
            sem = m2.group(2)

    # MA Project autumn/spring
    if re.search(r"\bproject\b", sl) and ("autumn" in sl or "fall" in sl or "spring" in sl):
        if "autumn" in sl or "fall" in sl:
            project_season = "MA Project Autumn"
        elif "spring" in sl:
            project_season = "MA Project Spring"
        level = "MA"

    # Extract candidate program name by removing level/semester tokens
    tmp = s
    tmp = re.sub(r"(?i)\b(master|bachelor)\b\s*", " ", tmp)
    tmp = re.sub(r"(?i)\bsemester\s*\d\b", " ", tmp)
    tmp = re.sub(r"(?i)\b(ma|ba)\s*\d\b", " ", tmp)
    tmp = re.sub(r"(?i)\bproject\b\s*(autumn|fall|spring)?", " ", tmp)
    tmp = re.sub(r"(?i)\bprogram\b", " ", tmp)
    base_guess = _def_ws_re.sub(" ", tmp).strip(" -,/")

    # Try canonical mapping using programs_tree
    raw_norm = _normalize_for_match(base_guess or s)

    if level == "MA":
        # Decide bucket key
        if project_season:
            bucket = _MA_CANON.get(project_season, {})
            # If project season bucket lacks entries (unlikely), fall back to MA buckets
            if not bucket:
                for key in ("MA1", "MA2", "MA3", "MA4"):
                    bucket.update(_MA_CANON.get(key, {}))
        elif sem:
            bucket = _MA_CANON.get(f"MA{sem}", {})
        else:
            # If semester not found, search across MA1..MA4
            bucket = {}
            for key in ("MA1", "MA2", "MA3", "MA4"):
                bucket.update(_MA_CANON.get(key, {}))
        cand = None
        best_len = -1
        for norm, canon in bucket.items():
            if f" {norm} " in f" {raw_norm} " or raw_norm == norm:
                if len(norm) > best_len:
                    cand = canon
                    best_len = len(norm)
        if cand and sem:
            return f"MA{sem} {cand}".strip()
        if cand and project_season:
            return f"{project_season} {cand}".strip()
        if cand:
            return f"MA {cand}".strip()

    if level == "BA":
        bucket = {}
        if sem:
            bucket = _BA_CANON.get(f"BA{sem}", {})
        if not bucket:
            for key in ("BA1", "BA2", "BA3", "BA4", "BA5", "BA6"):
                bucket.update(_BA_CANON.get(key, {}))
        cand = None
        best_len = -1
        for norm, canon in bucket.items():
            if f" {norm} " in f" {raw_norm} " or raw_norm == norm:
                if len(norm) > best_len:
                    cand = canon
                    best_len = len(norm)
        if cand and sem:
            return f"BA{sem} {cand}".strip()
        if cand:
            return f"BA {cand}".strip()

    # Fallback: if we got here, either level or canonical name was unclear
    if level and (sem or project_season):
        prefix = project_season if project_season else f"{level}{sem}"
        return f"{prefix} {base_guess or s}".strip()
    if level:
        return f"{level} {base_guess or s}".strip()
    # Give up and return cleaned input
    try:
        UNMAPPED_PROGRAMS.add(s)
    except Exception:
        pass
    return base_guess or s
    
def generate_keywords_llm(text, n_min=min_keywords, n_max=max_keywords):
    """Generate keywords using OpenAI API if OPENAI_API_KEY is set"""
    try:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY environment variable is missing. Please set it before running keyword generation.")
        client = OpenAI(api_key=key)
        prompt = (
            "You are extracting concise topic keywords for a university course. "
            f"Return ONLY a JSON array of {n_min} to {n_max} lowercase English keyword strings (no explanations). "
            "Each keyword should be short (1-4 words) in English. Translate if the course text is in another language.\n\n"
            "TEXT:\n" + text + "\n\nOUTPUT:"
        )
        resp = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        content = resp.choices[0].message["content"].strip()
        kws = parse_keywords_field(content)
        return kws[:n_max]
    except Exception as e:
        print("[warn] LLM keyword generation failed:", e)
        return []

def main():
    output_csv = "epfl_courses.csv"
    headers_list = ["course_code","lang","section","semester","prof_name","course_name","credits","exam_form","workload","type","keywords","available_programs","course_url"]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers_list)
    unknown_sections = set()
    all_programs = set()
    try:
        # Loop through each section and fetch data
        for section in section_codes:
            url = f"https://people.epfl.ch/cgi-bin/getCours?section={section}&format=json"
            try:
                t0 = time.perf_counter()
                response = requests.get(url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
                dt_ms = int((time.perf_counter() - t0) * 1000)
                if dt_ms > SLOW_REQ_MS:
                    warn(f"Slow section JSON fetch ({dt_ms} ms) for {section}: {url}")
                response.raise_for_status()
                data = response.json()
                for course in data:
                    print(f"Adding {course.get('C_CODECOURS', '')}...", flush=True)
                    # Try to fetch course page and extract credits
                    credits = ""
                    exam_form = ""
                    workload = ""
                    course_type = ""
                    keywords = []
                    available_programs = []
                    resume_text = ""
                    content_text = ""
                    course_url = course.get("X_URL", "")
                    if course_url:
                        try:
                            t1 = time.perf_counter()
                            page_resp = requests.get(course_url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
                            dt1_ms = int((time.perf_counter() - t1) * 1000)
                            if dt1_ms > SLOW_REQ_MS:
                                warn(f"Slow course page fetch ({dt1_ms} ms): {course.get('C_CODECOURS', '')} -> {course_url}")
                            page_resp.raise_for_status()
                            # print(f"[debug] Content-Type: {page_resp.headers.get('Content-Type', '')}")
                            # with open("body_preview.txt", "w") as file:
                            #     file.write(page_resp.text)
                            # exit()
                            # Parse using bytes; let lxml auto-detect encoding from declarations/meta
                            content_type = page_resp.headers.get('Content-Type', '').lower()
                            content_bytes = page_resp.content
                            root = None
                            if 'xml' in content_type:
                                try:
                                    parser = etree.XMLParser(recover=True)
                                    root = etree.fromstring(content_bytes, parser=parser)
                                except Exception:
                                    parser = etree.HTMLParser()
                                    root = etree.fromstring(content_bytes, parser=parser)
                            else:
                                try:
                                    parser = etree.HTMLParser()
                                    root = etree.fromstring(content_bytes, parser=parser)
                                except Exception:
                                    parser = etree.XMLParser(recover=True)
                                    root = etree.fromstring(content_bytes, parser=parser)
                            # Credits
                            credits = _et_text(root, "//examen/n_credits") or _et_text(root, "//examen/details/detail/coeff/n_valeur")
                            # Exam form (prefer EN, fallback FR)
                            exam_form = _et_text(root, "//examen/details/detail/code[@langue='en']") or \
                                        _et_text(root, "//examen/details/detail/code[@langue='fr']")
                            # Type (prefer EN, fallback FR)
                            course_type = _et_text(root, "//enseignement/typecourss/code[@langue='en']") or \
                                        _et_text(root, "//enseignement/typecourss/code[@langue='fr']") or course_type
                            # Times under a single <gps> -> compute a single workload
                            # Only consider the first <gps> under <gpss> to avoid duplicates across programs
                            weekly_total = 0.0
                            semester_total = 0.0
                            # Choose context: first <gps> if present, else fall back to the whole document
                            gps_nodes = root.xpath("//gpss/gps") if hasattr(root, 'xpath') else []
                            ctx = gps_nodes[0] if gps_nodes else root
                            for det in ctx.findall(".//enseignement/details/detail"):
                                # only consider course/exercise/project entries (EN or FR)
                                label_en = (_et_text(det, "code[@langue='en']") or "").lower()
                                label_fr = (_et_text(det, "code[@langue='fr']") or "").lower()
                                label = label_en or label_fr
                                if label not in {"courses", "cours", "exercises", "exercices", "project", "projet"}:
                                    continue
                                quant = _et_text(det, "quantite")
                                freq = _et_text(det, "frequences/code[@langue='en']") or _et_text(det, "frequences/code[@langue='fr']")
                                # extract numeric quantity from quant
                                num = 0.0
                                try:
                                    import re as _re
                                    m = _re.search(r"[\d.]+", quant or "")
                                    if m:
                                        num = float(m.group(0))
                                except Exception:
                                    num = 0.0
                                freq_l = (freq or "").lower()
                                if "per week" in freq_l or "hebdo" in freq_l:
                                    weekly_total += num
                                else:
                                    # default to per semester if not explicitly per week
                                    semester_total += num
                            # finalize workload string
                            if weekly_total > 0:
                                # prefer weekly if any part is weekly
                                workload = f"{int(weekly_total) if weekly_total.is_integer() else weekly_total}hrs/week"
                            elif semester_total > 0:
                                workload = f"{int(semester_total) if semester_total.is_integer() else semester_total}hrs/semester"
                            else:
                                workload = ""
                            kw_block_nodes = root.xpath("//texte[@var='RUBRIQUE_MOTS_CLES']")
                            if kw_block_nodes:
                                kw_block = kw_block_nodes[0]
                                paras = [("".join(p.itertext())).strip() for p in kw_block.xpath(".//p")]
                                raw = " ".join([p for p in paras if p])
                                keywords = parse_keywords_field(raw)
                            available_programs = [node.text.strip() for node in root.xpath("//gps/x_gps[@langue='en']")]
                            credits = _fix_mojibake(credits)
                            exam_form = _fix_mojibake(exam_form)
                            course_type = _fix_mojibake(course_type)
                            # Normalize available programs, with special canonical handling for minors via programs_tree
                            available_programs = [format_available_program_label(x) for x in available_programs]
                            for _p in available_programs:
                                all_programs.add(_p)
                            # Extract resume/summary and content blocks
                            try:
                                resume_nodes = root.xpath("//texte[@var='RUBRIQUE_RESUME']") or []
                                if resume_nodes:
                                    resume_text = " ".join(("".join(n.itertext())).strip() for n in resume_nodes if n is not None).strip()
                                content_nodes = root.xpath("//texte[@var='RUBRIQUE_CONTENU']") or []
                                if content_nodes:
                                    content_text = " ".join(("".join(n.itertext())).strip() for n in content_nodes if n is not None).strip()
                                # Unescape common HTML entities and fix mojibake
                                if resume_text:
                                    resume_text = _fix_mojibake(html.unescape(resume_text))
                                if content_text:
                                    content_text = _fix_mojibake(html.unescape(content_text))
                            except Exception:
                                # Be resilient if page format changes
                                pass
                        except Exception as e_xml:
                            print(f"  [error] XML parsing failed for {course_url}: {e_xml}")
                        except requests.exceptions.Timeout:
                            warn(f"[TIMEOUT] Course page timed out: {course.get('C_CODECOURS', '')} -> {course_url}")
                        except Exception as page_err:
                            warn(f"Could not read course page {course_url}: {page_err}")
                    # If no keywords or not enough, try to supplement with LLM
                    # keywords_method = "original"
                    # if len(keywords) < 5:
                    #     course_text = " ".join([
                    #         course.get("X_MATIERE", ""),
                    #         resume_text or "",
                    #         content_text or "",
                    #     ])
                    #     print(course_text)
                    #     original_keywords = list(keywords)  # preserve current
                    #     kws_llm = generate_keywords_llm(course_text, n_min=min_keywords, n_max=max_keywords)
                    #     if kws_llm:
                    #         # merge while preserving order and avoiding duplicates
                    #         merged = []
                    #         seen = set()
                    #         for k in _normalize_kw_list(original_keywords):
                    #             if k not in seen:
                    #                 merged.append(k)
                    #                 seen.add(k)
                    #         for k in _normalize_kw_list(kws_llm):
                    #             if k not in seen:
                    #                 merged.append(k)
                    #                 seen.add(k)
                    #             if len(merged) >= max_keywords:
                    #                 break
                    #         keywords = merged
                    #         keywords_method = "original+LLM" if original_keywords else "LLM"
                    # --- Diagnostics: immediate terminal warnings for suspiciously empty rows ---
                    nonempty_core = _count_nonempty(credits, exam_form, workload, course_type, keywords, available_programs)
                    if nonempty_core < MIN_FIELDS_TO_CONSIDER_OK:
                        warn(
                            f"Sparse parse for course {course.get('C_CODECOURS', '')} | name='{_fix_mojibake(course.get('X_MATIERE', ''))}' | section='{section}' | url={course_url}"
                        )
                    # Additional hint if the page looked like HTML but XML-style XPaths yielded nothing
                    try:
                        ctype_hdr = page_resp.headers.get('Content-Type', '').lower() if course_url else ''
                        if nonempty_core < MIN_FIELDS_TO_CONSIDER_OK and 'text/html' in ctype_hdr:
                            warn("Likely HTML layout; XML XPaths may not match. Consider HTML fallback paths.")
                    except Exception:
                        pass
                    # Warn if keywords is a bare string or obviously malformed (not a list)
                    if isinstance(keywords, str) or (isinstance(keywords, list) and len(keywords) == 1 and isinstance(keywords[0], str) and ',' in keywords[0]):
                        warn(f"Suspicious keywords parse for {course.get('C_CODECOURS', '')}: {keywords}")
                    # --- Section abbreviation mapping ---
                    sec_raw = course.get("C_SECTION", "")
                    sec_norm = _norm(str(sec_raw))
                    # If already a known code, keep it; otherwise try to map from full name
                    if sec_norm.upper() in VALID_SECTION_CODES:
                        section_code = sec_norm.upper()
                    else:
                        section_code = SECTION_ABBREV.get(sec_norm.lower())
                        if not section_code:
                            unknown_sections.add(sec_norm)
                            section_code = sec_norm  # keep original for CSV so we can spot it
                    if str(credits).strip() and str(credits).strip() != "0":
                        keywords = _normalize_kw_list(keywords)
                        # Sanitize course name before writing row
                        course_name_raw = course.get("X_MATIERE", "")
                        course_name = _fix_mojibake(course_name_raw).rstrip()
                        row = [
                            course.get("C_CODECOURS", ""),
                            course.get("C_LANGUEENS", ""),
                            section_code,
                            course.get("C_SEMESTRE", ""),
                            course.get("X_LISTENOM", ""),
                            course_name,
                            credits,
                            exam_form,
                            workload,
                            course_type,
                            keywords,
                            available_programs,
                            course.get("X_URL", "")
                        ]
                        with open(output_csv, "a", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            writer.writerow(row)
                        print("credits: ", credits, flush=True)
                        print("workload: ", workload, flush=True)
                        print("keywords: ", keywords, flush=True)
                        # count += 1
                        # if count >= 5:
                        #     break
                    # print("exam_form: ", exam_form)
                    # print("courses_time: ", courses_time)
                    # print("exercises_time: ", exercises_time)
                    # print("project_time: ", project_time)
                    # print("type: ", course_type)
                    # print("keywords: ", keywords)
                    # print("available_programs: ", available_programs)
                # if count >= 5:
                #     break
            except requests.exceptions.Timeout:
                warn(f"[TIMEOUT] Section fetch timed out for {section}: {url}")
            except Exception as e:
                warn(f"Failed to fetch data for section {section}: {e}")
    finally:
        # Print unique simplified available programs (built during processing)
        print("Unique simplified available programs:", all_programs, flush=True)
        if unknown_sections:
            print("Unmapped sections (please update mapping):", sorted(unknown_sections), flush=True)
        if UNMAPPED_PROGRAMS:
            print("Unmapped program labels (kept as-is):", sorted(UNMAPPED_PROGRAMS), flush=True)

if __name__ == "__main__":
    main()
