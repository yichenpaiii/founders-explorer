# Import necessary libraries
import requests
import pandas as pd
import os
from lxml import etree
import importlib
import re
import json
import html
import os
from openai import OpenAI

# Use deep-translator for translation
from deep_translator import GoogleTranslator
_translator_en = GoogleTranslator(source="auto", target="en")

# Section codes from the screenshot

section_codes = [
    "AR", "CGC", "CDH", "CDM", "CMS", "ED", "GC", "EL",
    "GM", "IN", "MX", "MA", "MT", "NX", "PH", "SIE", "SIQ", "SV", "SHS", "SC"
]

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
    # Now split on common separators, including slashes and bullets
    parts = re.split(r"(?:\n|,|;|\||\u2022|\u2027|•|·|-|—|/|\s+/\s+)", s)
    # Clean up quotes and whitespace
    cleaned = []
    for p in parts:
        t = p.strip().strip("'\"")
        if t:
            cleaned.append(t)
    return cleaned

def parse_keywords_field(raw):
    parts = _split_keywords(raw)
    parts = [_fix_mojibake(p) for p in parts]
    return _normalize_kw_list(parts)

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

# Translate a list of keywords to English using deep_translator (GoogleTranslator)
def translate_keywords_to_en(keywords, source_lang="auto"):
    """Translate keywords list to English using deep_translator.GoogleTranslator."""
    if not keywords:
        return keywords
    out = []
    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        try:
            # Avoid translating if it already looks English (basic heuristic)
            if re.fullmatch(r"[a-z0-9 \-_/&.'()]+", kw.lower()):
                out.append(kw.lower())
                continue
            translated = _translator_en.translate(kw)
            if translated:
                out.append(translated.strip().lower())
        except Exception as e:
            print("[warn] Keyword translation failed for", repr(kw), ":", e)
            out.append(kw.lower())
    return _normalize_kw_list(out)

def main():
    output_csv = "epfl_courses.csv"
    # List to store all course data
    all_courses = []
    count = 0
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
                    # count += 1
                    # if count >= 5:
                    #     break
                    # Try to fetch course page and extract credits
                    credits = ""
                    exam_form = ""
                    courses_time = ""
                    exercises_time = ""
                    project_time = ""
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
                                keywords = parse_keywords_field(raw)
                                # Detect language (simple heuristic) and translate if not English
                                kw_lang = course.get("C_LANGUEENS", "").lower()
                                if not kw_lang.startswith("en"):
                                    keywords = translate_keywords_to_en(keywords, source_lang=kw_lang if kw_lang else "auto")
                            available_programs = [node.text.strip() for node in root.xpath("//gps/x_gps[@langue='en']")]
                            credits = _fix_mojibake(credits)
                            exam_form = _fix_mojibake(exam_form)
                            course_type = _fix_mojibake(course_type)
                            available_programs = [_fix_mojibake(x) for x in available_programs]
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
                    keywords_method = "original"
                    if len(keywords) < 5:
                        course_text = " ".join([
                            course.get("X_MATIERE", ""),
                            resume_text or "",
                            content_text or "",
                        ])
                        print(course_text)
                        original_keywords = list(keywords)  # preserve current
                        kws_llm = generate_keywords_llm(course_text, n_min=min_keywords, n_max=max_keywords)
                        if kws_llm:
                            # merge while preserving order and avoiding duplicates
                            merged = []
                            seen = set()
                            for k in _normalize_kw_list(original_keywords):
                                if k not in seen:
                                    merged.append(k)
                                    seen.add(k)
                            for k in _normalize_kw_list(kws_llm):
                                if k not in seen:
                                    merged.append(k)
                                    seen.add(k)
                                if len(merged) >= max_keywords:
                                    break
                            keywords = merged
                            keywords_method = "original+LLM" if original_keywords else "LLM"
                        else:
                            # fall back to whatever we had
                            keywords = _normalize_kw_list(original_keywords)
                            keywords_method = "original"
                    else:
                        break
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
                        print("keywords method: ", keywords_method)
                        count += 1
                        if count >= 5:
                            break
                    # print("exam_form: ", exam_form)
                    # print("courses_time: ", courses_time)
                    # print("exercises_time: ", exercises_time)
                    # print("project_time: ", project_time)
                    # print("type: ", course_type)
                    # print("keywords: ", keywords)
                    # print("available_programs: ", available_programs)
                if count >= 5:
                    break
            except Exception as e:
                print(f"Failed to fetch data for section {section}: {e}")
    finally:
        try:
            # Convert to DataFrame
            df = pd.DataFrame(all_courses)
            df.to_csv(output_csv, index=False)
            print(f"Saved {len(df)} rows to {output_csv}")
        except Exception as save_err:
            print(f"[error] Failed to save CSV: {save_err}")

if __name__ == "__main__":
    main()