import requests
import os
from lxml import etree
import re
import json
import html
import csv
import sys
import time
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import hashlib
from sentence_transformers import SentenceTransformer
from keybert import KeyBERT

section_codes = [
    "AR", "CGC", "CDH", "CDM", "ED", "GC", "EL",
    "GM", "IN", "MX", "MA", "MT", "MTE", "NX", "PH", "SIE", "SIQ", "SV", "SHS", "SC",
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
    "management of technology and entrepreneurship": "MTE",
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

## Removed programs tree helpers and label formatter to keep the original simpler behavior

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

_KEYBERT_MODEL = None

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


def _ensure_keybert_model():
    global _KEYBERT_MODEL
    if KeyBERT is None:
        return None
    if _KEYBERT_MODEL is None:
        try:
            embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            _KEYBERT_MODEL = KeyBERT(model=embedding_model)
        except Exception as exc:  # pragma: no cover - defensive guard
            warn(f"KeyBERT initialization failed: {exc}")
            _KEYBERT_MODEL = None
    return _KEYBERT_MODEL


def _extract_keywords_from_text(text: str, *, top_n: int = 20) -> list[str]:
    if not text or not text.strip():
        return []
    model = _ensure_keybert_model()
    if model is None:
        return []
    try:
        results = model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            nr_candidates=100,
            top_n=top_n,
            use_mmr=False,
            use_maxsum=False,
        )
    except Exception as exc:  # pragma: no cover - model/runtime errors
        warn(f"KeyBERT keyword extraction failed: {exc}")
        return []
    extracted = []
    for kw, score in results:
        if isinstance(kw, str) and kw.strip():
            extracted.append(kw.strip().lower())
    return extracted


def _maybe_augment_keywords(existing: list[str] | None, text_sources: list[str]) -> list[str]:
    existing = existing or []
    if not isinstance(existing, list):
        existing = [str(existing)]
    # Normalize upfront for dedupe consistency
    keywords = _normalize_kw_list(existing)
    if len(keywords) >= min_keywords:
        return keywords[:max_keywords]
    combined_text = "\n\n".join(t for t in text_sources if isinstance(t, str) and t.strip())
    if not combined_text:
        return keywords
    supplemental = _extract_keywords_from_text(combined_text, top_n=max_keywords)
    for kw in supplemental:
        if kw not in keywords:
            keywords.append(kw)
        if len(keywords) >= max_keywords:
            break
    return keywords

def _canonicalize_prog_key(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9&+/\- ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _apply_program_renames(name: str, renames: dict) -> str:
    if not name:
        return name
    key = _canonicalize_prog_key(name)
    return renames.get(key) or renames.get(name) or name

def make_row_id(course_code: str, section_code: str, course_name: str) -> str:
    """Create a stable short hash ID to link rows across CSVs."""
    key = "||".join([
        (course_code or "").strip().lower(),
        (section_code or "").strip().lower(),
        (course_name or "").strip().lower(),
    ])
    # 8-byte blake2b hex (16 hex chars) is compact and collision-resistant enough here
    return hashlib.blake2b(key.encode("utf-8"), digest_size=8).hexdigest()

def force_english_course_url(url: str) -> str:
    """Ensure the course page URL uses English by setting ww_c_langue=en."""
    try:
        if not url:
            return url
        parts = urlparse(url)
        q = parse_qs(parts.query, keep_blank_values=True)
        q['ww_c_langue'] = ['en']
        new_query = urlencode(q, doseq=True)
        return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, new_query, parts.fragment))
    except Exception:
        return url

def main():
    # Ensure data directory exists
    data_dir = os.path.join(os.path.dirname(__file__), "data") if '__file__' in globals() else "data"
    os.makedirs(data_dir, exist_ok=True)
    output_csv = os.path.join(data_dir, "epfl_courses.csv")
    embedding_csv = os.path.join(data_dir, "courses_scores.csv")
    headers_list = [
        "row_id","course_code","lang","section","semester","prof_name","course_name",
        "credits","exam_form","workload","type","keywords","available_programs","course_url"
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers_list)
    # New CSV for embedding text (summary + content)
    with open(embedding_csv, "w", newline="", encoding="utf-8") as f:
        emb_writer = csv.writer(f)
        emb_writer.writerow(["row_id", "text"])  # combined resume+content
    unknown_sections = set()
    all_programs = set()
    # Load program renames mapping if present
    renames = {}
    try:
        with open(os.path.join(data_dir, "program_renames.json"), "r", encoding="utf-8") as rf:
            _r = json.load(rf)
            if isinstance(_r, dict):
                renames = _r
    except Exception:
        renames = {}
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
                    course_url = force_english_course_url(course.get("X_URL", ""))
                    if course_url:
                        try:
                            t1 = time.perf_counter()
                            page_resp = requests.get(course_url, headers=headers, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
                            dt1_ms = int((time.perf_counter() - t1) * 1000)
                            if dt1_ms > SLOW_REQ_MS:
                                warn(f"Slow course page fetch ({dt1_ms} ms): {course.get('C_CODECOURS', '')} -> {course_url}")
                            page_resp.raise_for_status()
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
                                    m = re.search(r"[\d.]+", quant or "")
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
                            # Normalize using mojibake fix, then map via renames
                            available_programs = [_fix_mojibake(x) for x in available_programs]
                            available_programs = [_apply_program_renames(x, renames) for x in available_programs]
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
                                keywords = _maybe_augment_keywords(keywords, [resume_text, content_text])
                            except Exception:
                                # Be resilient if page format changes
                                pass
                        except Exception as e_xml:
                            print(f"  [error] XML parsing failed for {course_url}: {e_xml}")
                        except requests.exceptions.Timeout:
                            warn(f"[TIMEOUT] Course page timed out: {course.get('C_CODECOURS', '')} -> {course_url}")
                        except Exception as page_err:
                            warn(f"Could not read course page {course_url}: {page_err}")
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
                        row_id = make_row_id(
                            course.get("C_CODECOURS", ""),
                            section_code,
                            course_name
                        )
                        row = [
                            row_id,
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
                            course_url,
                        ]
                        with open(output_csv, "a", newline="", encoding="utf-8") as f:
                            writer = csv.writer(f)
                            writer.writerow(row)
                        # Write embedding text if any
                        text_parts = []
                        if resume_text:
                            text_parts.append(resume_text)
                        if content_text:
                            text_parts.append(content_text)
                        combined_text = "\n\n".join([t for t in text_parts if t]).strip()
                        if combined_text:
                            with open(embedding_csv, "a", newline="", encoding="utf-8") as f:
                                emb_writer = csv.writer(f)
                                emb_writer.writerow([
                                    row_id,
                                    combined_text,
                                ])
                        print("credits: ", credits, flush=True)
                        print("workload: ", workload, flush=True)
                        print("keywords: ", keywords, flush=True)
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
