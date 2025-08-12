# Import necessary libraries
import requests
import pandas as pd
import os
from lxml import etree
import importlib
import re
import json

# Section codes from the screenshot

section_codes = [
    "AR", "CGC", "CDH", "CDM", "CMS", "ED", "GC", "EL",
    "GM", "IN", "MX", "MA", "MT", "NX", "PH", "SIE", "SIQ", "SV", "SHS", "SC"
]

# HTTP headers for polite requests
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


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

def extract_keywords_local(text, top_n=12):
    """Try to extract keywords with KeyBERT if available"""
    try:
        if importlib.util.find_spec("keybert") is None:
            return []
        from keybert import KeyBERT
        if importlib.util.find_spec("sentence_transformers") is None:
            return []
        model = KeyBERT(model="all-MiniLM-L6-v2")
        kw_tuples = model.extract_keywords(text, top_n=top_n)
        kws = [kw for kw, _ in kw_tuples]
        return _normalize_kw_list(kws)
    except Exception as e:
        print("[warn] Local keyword extraction failed:", e)
        return []

def generate_keywords_llm(text, n_min=5, n_max=12, lang_hint="auto"):
    """Generate keywords using OpenAI API if OPENAI_API_KEY is set"""
    try:
        import openai, os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return []
        openai.api_key = api_key
        prompt = f"Generate {n_min} to {n_max} concise keywords for the following course description (lowercase, comma-separated). Language hint: {lang_hint}.\n\n{text}\n\nKeywords:"
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        content = resp.choices[0].message["content"]
        parts = re.split(r",|\\n|;", content)
        kws = [p.strip() for p in parts if p.strip()]
        return _normalize_kw_list(kws)[:n_max]
    except Exception as e:
        print("[warn] LLM keyword generation failed:", e)
        return []

# List to store all course data
all_courses = []

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
            courses_time = ""
            exercises_time = ""
            project_time = ""
            course_type = ""
            keywords = []
            available_programs = []
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
                    # Times under enseignement/details/detail
                    label_map = {
                        "courses": "courses_time",
                        "cours": "courses_time",
                        "exercises": "exercises_time",
                        "exercices": "exercises_time",
                        "project": "project_time",
                        "projet": "project_time",
                    }
                    for det in root.findall(".//enseignement/details/detail"):
                        label_en = _et_text(det, "code[@langue='en']").lower()
                        label_fr = _et_text(det, "code[@langue='fr']").lower()
                        label = label_en or label_fr
                        target = label_map.get(label, None)
                        if not target:
                            continue
                        quant = _et_text(det, "quantite")
                        freq = _et_text(det, "frequences/code[@langue='en']") or _et_text(det, "frequences/code[@langue='fr']")
                        composed = (f"{quant} {freq}".strip() if (quant or freq) else "").strip()
                        if composed:
                            if target == "courses_time":
                                courses_time = composed
                            elif target == "exercises_time":
                                exercises_time = composed
                            elif target == "project_time":
                                project_time = composed
                    kw_block_nodes = root.xpath("//texte[@var='RUBRIQUE_MOTS_CLES']")
                    if kw_block_nodes:
                        kw_block = kw_block_nodes[0]
                        paras = [("".join(p.itertext())).strip() for p in kw_block.xpath(".//p")]
                        raw = " ".join([p for p in paras if p])
                        keywords = [_fix_mojibake(k.strip()) for k in raw.split(",") if k.strip()]
                        keywords = [k.lower() for k in keywords]
                    available_programs = [node.text.strip() for node in root.xpath("//gps/x_gps[@langue='en']")]
                    credits = _fix_mojibake(credits)
                    exam_form = _fix_mojibake(exam_form)
                    course_type = _fix_mojibake(course_type)
                    available_programs = [_fix_mojibake(x) for x in available_programs]
                except Exception as e_xml:
                    print(f"  [error] XML parsing failed for {course_url}: {e_xml}")
                except Exception as page_err:
                    print(f"  Could not read credits from {course_url}: {page_err}")
            # If no keywords or fewer than 5, try to generate
            if len(keywords) < 5:
                course_text = " ".join([
                    course.get("X_MATIERE", ""),
                    course.get("X_LISTENOM", ""),
                    exam_form or "",
                    course_type or "",
                    courses_time or "",
                    exercises_time or "",
                    project_time or ""
                ])
                kws_local = extract_keywords_local(course_text, top_n=12)
                if len(kws_local) >= 5:
                    keywords = kws_local
                else:
                    kws_llm = generate_keywords_llm(course_text, n_min=5, n_max=12)
                    if kws_llm:
                        keywords = kws_llm
            if str(credits).strip() != "0":
                keywords = _normalize_kw_list(keywords)
                all_courses.append({
                    "course_code": course.get("C_CODECOURS", ""),
                    "lang": course.get("C_LANGUEENS", ""),
                    "program_term": course.get("C_PEDAGO", ""),
                    "section": course.get("C_SECTION", ""),
                    "semester": course.get("C_SEMESTRE", ""),
                    "prof_name": course.get("X_LISTENOM", ""),
                    "course_name": course.get("X_MATIERE", ""),
                    "credits": credits,
                    "exam_form": exam_form,
                    "courses_time": courses_time,
                    "exercises_time": exercises_time,
                    "project_time": project_time,
                    "type": course_type,
                    "keywords": keywords,
                    "available_programs": available_programs,
                    "course_url": course.get("X_URL", ""),
                })
                print("credits: ", credits)
            # print("exam_form: ", exam_form)
            # print("courses_time: ", courses_time)
            # print("exercises_time: ", exercises_time)
            # print("project_time: ", project_time)
            # print("type: ", course_type)
            # print("keywords: ", keywords)
            # print("available_programs: ", available_programs)
    except Exception as e:
        print(f"Failed to fetch data for section {section}: {e}")

# Convert to DataFrame
df = pd.DataFrame(all_courses)

# Save to CSV
df.to_csv("epfl_courses.csv", index=False)

# Display sample
df.head()