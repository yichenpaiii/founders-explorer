import requests
from lxml import etree

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

credits = ""
exam_form = ""
courses_time = ""
exercises_time = ""
project_time = ""
course_type = ""
keywords = []
available_programs = []
course_url = "https://isa.epfl.ch/imoniteur_ISAP/!itffichecours.htm?ww_i_matiere=399868361&ww_x_anneeacad=2840683608&ww_i_section=32211080&ww_i_niveau=&ww_c_langue=en"
if course_url:
    try:
        page_resp = requests.get(course_url, headers=headers, timeout=15)
        page_resp.raise_for_status()
        print(f"[debug] Content-Type: {page_resp.headers.get('Content-Type', '')}")
        with open("body_preview.txt", "w") as file:
            file.write(page_resp.text)
        exit()
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
                        _et_text(root, "//enseignement/typecourss/code[@langue='fr']")
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
if str(credits).strip() != "0":
    print("credits: ", credits)
    print("exam_form: ", exam_form)
    print("courses_time: ", courses_time)
    print("exercises_time: ", exercises_time)
    print("project_time: ", project_time)
    print("type: ", course_type)
    print("keywords: ", keywords)
    print("available_programs: ", available_programs)