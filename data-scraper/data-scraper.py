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


# Section codes from the screenshot


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

# HTTP headers for polite requests
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

min_keywords = 10
max_keywords = 15
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

def simplify_program_name(prog: str) -> str:
    if not prog:
        return prog
    parts = [p.strip() for p in prog.split(",")]
    if not parts:
        return prog
    base = parts[0]
    rest = " ".join(parts[1:])
    # Drop year-like tokens (4 digits with dash)
    rest = re.sub(r"\b\d{4}(?:-\d{4})?\b", "", rest).strip()
    # Replace Bachelor -> BA, Master -> MA
    rest = rest.replace("Bachelor", "BA").replace("Master", "MA")
    # Extract semester number if present
    m = re.search(r"semester\s*(\d+)", rest, flags=re.I)
    sem = f"{m.group(1)}" if m else ""
    if "BA" in rest or "MA" in rest:
        if sem:
            # Extract BA/MA abbreviation only
            abbrev_match = re.search(r"\b(BA|MA)\b", rest)
            abbrev = abbrev_match.group(1) if abbrev_match else rest.strip()
            return f"{base} {abbrev}{sem}"
        else:
            return f"{base} {rest.strip()}"
    else:
        return f"{base} {rest}".strip()
    
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
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                data = response.json()
                for course in data:
                    print(f"Adding {course.get('C_CODECOURS', '')}...")
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
                            page_resp = requests.get(course_url, headers=headers, timeout=15)
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
                            available_programs = [simplify_program_name(_fix_mojibake(x)) for x in available_programs]
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
                        except Exception as page_err:
                            print(f"  Could not read credits from {course_url}: {page_err}")
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
                    if str(credits).strip() != "0":
                        keywords = _normalize_kw_list(keywords)
                        row = [
                            course.get("C_CODECOURS", ""),
                            course.get("C_LANGUEENS", ""),
                            section_code,
                            course.get("C_SEMESTRE", ""),
                            course.get("X_LISTENOM", ""),
                            course.get("X_MATIERE", ""),
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
                        print("credits: ", credits)
                        print("workload: ", workload)
                        print("keywords: ", keywords)
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
            except Exception as e:
                print(f"Failed to fetch data for section {section}: {e}")
    finally:
        # Print unique simplified available programs (built during processing)
        print("Unique simplified available programs:", all_programs)
        if unknown_sections:
            print("Unmapped sections (please update mapping):", sorted(unknown_sections))

if __name__ == "__main__":
    main()