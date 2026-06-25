import os
import re
from typing import List, Dict, Optional, Tuple

# Old vresion parser
def split_articles(text: str) -> List[str]:
    """법령 텍스트를 조항별로 분리"""
    # 제N조, 제N조의N, 제N조제N항 패턴 매칭
    pattern = r'제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?'
    
    # 조항 시작 위치 찾기
    matches = list(re.finditer(pattern, text))
    
    if not matches:
        return [text]
    
    articles = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        article = text[start:end].strip()
        if article:
            articles.append(article)
    
    return articles

# New version parser with global context categorization
def split_and_categorize_articles(text: str) -> Dict[str, List[str]]:
    """법령 텍스트를 조항별로 분리하고 글로벌 구조를 분류"""
    
    # 정규식 업데이트: '제N조' 패턴뿐만 아니라 '부칙'도 매칭 단위로 잡음
    pattern = r'(제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?|부\s*칙(?:\s*<[^>]+>)?\s*)'
    
    matches = list(re.finditer(pattern, text))
    if not matches:
        return {"front": [], "main": [clean_text(text)], "back": []}
    
    articles = []
    addenda = [] # 부칙 저장용
    
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        
        header = match.group(1).replace(" ", "")
        content = clean_text(text[start:end])
        
        if content:
            if "부칙" in header:
                addenda.append(content)
            else:
                articles.append(content)
                
    # 글로벌 컨텍스트 식별 (Front & Back)
    # Front: 보통 제1조(목적), 제2조(정의), 제3조(적용범위)가 글로벌 맥락을 담음
    # (안전하게 첫 3개 조항을 글로벌 앵커로 사용)
    front_context = articles[:3] if len(articles) >= 3 else articles
    
    return {
        "front_raw": front_context,   # 나중에 Relation에 주입할 목적, 정의 등
        "back_raw": addenda,          # 문서 메타데이터(시행일) 추출용
        "main_raw": articles          # 일반적인 엔터티 추출을 돌릴 전체 조항
    }

def _parse_structural_index(chapter: Optional[int], section: Optional[int], article: int) -> List[Optional[int]]:
    """Build [장, 절, 조] structural index. None means the unit hasn't appeared yet."""
    return [chapter, section, article]


def split_markdown_articles(text: str) -> Dict[str, List[Dict]]:
    """Parse Markdown-formatted legal text produced by FormattingChain.

    Returns a dict with keys:
      front_raw  – first 3 article dicts (purpose / definitions / scope)
      main_raw   – all article dicts from the main body
      back_raw   – addenda article dicts (부칙)

    Each article dict has:
      article_number   – e.g. "제1조" or "제1조의2"
      structural_index – [장, 절, 조] List[Optional[int]]
      full_text        – the raw text of that article
      is_addendum      – True if inside 부칙
    """
    lines = text.splitlines()

    current_chapter: Optional[int] = None
    current_section: Optional[int] = None
    in_addendum: bool = False

    articles: List[Dict] = []
    addenda: List[Dict] = []

    current_article: Optional[str] = None
    current_buf: List[str] = []
    current_index: List[Optional[int]] = []

    chapter_re = re.compile(r'^#+\s*제\s*(\d+)\s*장')
    section_re = re.compile(r'^#+\s*제\s*(\d+)\s*절')
    addendum_re = re.compile(r'^#+\s*부\s*칙')
    article_re = re.compile(r'^##\s*(제\s*\d+\s*조(?:의\s*\d+)?)\s*(.*)')

    def _flush():
        nonlocal current_article, current_buf
        if current_article is not None:
            body = "\n".join(current_buf).strip()
            entry = {
                "article_number": current_article,
                "structural_index": list(current_index),
                "full_text": body,
                "is_addendum": in_addendum,
            }
            if in_addendum:
                addenda.append(entry)
            else:
                articles.append(entry)
        current_article = None
        current_buf = []

    for line in lines:
        chap_m = chapter_re.match(line)
        sec_m = section_re.match(line)
        add_m = addendum_re.match(line)
        art_m = article_re.match(line)

        if chap_m:
            _flush()
            current_chapter = int(chap_m.group(1))
            current_section = None
        elif sec_m:
            _flush()
            current_section = int(sec_m.group(1))
        elif add_m:
            _flush()
            in_addendum = True
            # Reset article counter context for addendum
            current_chapter = None
            current_section = None
        elif art_m:
            _flush()
            raw_num = art_m.group(1).replace(" ", "")
            num_m = re.search(r'(\d+)', raw_num)
            article_num = int(num_m.group(1)) if num_m else 0
            current_article = raw_num
            current_index = _parse_structural_index(current_chapter, current_section, article_num)
            # Include heading line in full_text
            current_buf = [line]
        else:
            if current_article is not None:
                current_buf.append(line)

    _flush()

    front_context = articles[:3] if len(articles) >= 3 else articles[:]

    return {
        "front_raw": front_context,
        "main_raw": articles,
        "back_raw": addenda,
    }


# ──────────────────────────────────────────────────────────────────────────────
# 계층적 파서 (조 > 항 > 호/목) — 위치(마커) 기반, 줄바꿈에 의존하지 않음
#
# 한국 법령의 번호 체계는 결정론적이다:
#   조: 제N조 / 제N조의M
#   항: ①②③… (원문자)  또는  "제N항"
#   호: 1. 2. 3.        목: 가. 나. 다.   (항/조 본문에 종속되므로 분리하지 않음)
#
# 추출 단위 = '항(項)' 단위. 항이 없는 조(예: 정의 조)는 조 전체가 1단위.
# 각 단위의 full_text 앞에 조 제목(heading)을 context로 붙여 LLM이 소속 조를
# 인지하도록 한다. structural_index = [장, 절, 조, 항].
# ──────────────────────────────────────────────────────────────────────────────

# 타 법령 참조 패턴 — 「법령명」(+선택적 제N조[제M항][제M호]) (HGT 학습용 핵심 특성)
# 조문번호 없이 법령명만 인용하는 경우(예: 「공공기관의 운영에 관한 법률」에 따른 공공기관)도
# 포착한다. 본 법령 조항이 아니므로 경계로 인식하면 안 되고 cross_law_refs로 별도 기록한다.
_ARTICLE_SUFFIX = r'(?:\s*제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?(?:제\s*\d+\s*호)?)?'
_CROSS_LAW_REF_RE = re.compile(
    r'(?:「[^」]+」|『[^』]+』|〔[^〕]+〕)' + _ARTICLE_SUFFIX + r'|'
    r'(?:같은\s*법|동법|해당\s*법)\s*제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?(?:제\s*\d+\s*호)?'
)

# cross_law_ref 문자열 → {law_name, article} 분해용
_CROSS_LAW_PARSE_RE = re.compile(
    r'(?:「([^」]+)」|『([^』]+)』|〔([^〕]+)〕|(같은\s*법|동법|해당\s*법))'
    r'(\s*제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?(?:제\s*\d+\s*호)?)?'
)


def parse_cross_law_ref(ref: str) -> Dict[str, Optional[str]]:
    """'「금융지주회사법」 제2조제1항제5호' → {'law_name':'금융지주회사법','article':'제2조제1항제5호'}.

    조문번호가 없으면 article=None. 그래프에서 (법령, 조항) 노드를 만들 때 사용한다.
    """
    m = _CROSS_LAW_PARSE_RE.search(ref)
    if not m:
        return {"law_name": None, "article": None, "raw": ref.strip()}
    law = m.group(1) or m.group(2) or m.group(3) or m.group(4)
    article = re.sub(r'\s+', '', m.group(5)) if m.group(5) else None
    return {
        "law_name": re.sub(r'\s+', ' ', law).strip() if law else None,
        "article": article,
        "raw": re.sub(r'\s+', ' ', ref).strip(),
    }

# 본 법령 내부 조항 상호참조 — 「법명」 없이 등장하는 제N조[제M항][제M호]
# (예: "제16조제1항부터 제3항까지", "제12조제1항 및 같은 조 제2항")
# 이는 본 법령의 다른 조항을 가리키는 그래프 엣지(REFERS_TO)로 활용.
_INTRA_LAW_REF_RE = re.compile(
    r'제\s*\d+\s*조(?:의\s*\d+)?(?:제\s*\d+\s*항)?(?:제\s*\d+\s*호)?'
)


_RELATIVE_LAW = ("같은", "동법", "해당")


def extract_cross_law_refs(text: str) -> List[str]:
    """타 법령 참조 목록. HGT가 다법령 통합 추론을 학습하는 핵심 특성.

    '같은 법'/'동법'/'해당 법'은 직전에 명시된 「법령명」으로 해소해 반환한다
    (예: '...자본시장법...같은 법 제9조제17항' → '「자본시장과 금융투자업에 관한 법률」 제9조제17항').
    """
    results: List[str] = []
    last_law: Optional[str] = None
    for m in _CROSS_LAW_REF_RE.finditer(text):
        raw = re.sub(r'\s+', ' ', m.group(0)).strip()
        parsed = parse_cross_law_ref(raw)
        law = parsed["law_name"]
        is_relative = bool(law) and any(law.startswith(p) for p in _RELATIVE_LAW)
        if is_relative and last_law:
            article = parsed["article"] or ""
            results.append(f"「{last_law}」 {article}".strip())
        else:
            if law and not is_relative:
                last_law = law
            results.append(raw)
    return results


def extract_intra_law_refs(text: str) -> List[str]:
    """본 법령 내부 조항 상호참조 목록 (타 법령 참조는 제외). REFERS_TO 엣지용."""
    # 타 법령 참조 구간을 먼저 제거해 중복 집계 방지
    masked = _CROSS_LAW_REF_RE.sub(" ", text)
    refs = []
    for m in _INTRA_LAW_REF_RE.finditer(masked):
        ref = re.sub(r'\s+', '', m.group(0))
        refs.append(ref)
    return refs


_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_CIRCLED_TO_INT = {c: i + 1 for i, c in enumerate(_CIRCLED)}

# 조 경계: '제N조' 뒤에 '(제목)' 괄호가 오는 실제 조 헤딩만 인정한다.
# 내부 참조(제16조제1항 → 뒤에 '제'), 인용(제5조, → 뒤에 ',', 제33조에 → 뒤에 '에')은
# 괄호가 따라오지 않으므로 경계로 잡히지 않는다. 부칙은 괄호 없이 인정.
_ARTICLE_BOUNDARY_RE = re.compile(
    r'(제\s*\d+\s*조(?:의\s*\d+)?(?=\s*\()|부\s*칙(?:\s*<[^>]*>)?)'
)
_ARTICLE_NUM_RE = re.compile(r'제\s*(\d+)\s*조(?:의\s*(\d+))?')
_CHAPTER_FINDER = re.compile(r'제\s*(\d+)\s*장')
_SECTION_FINDER = re.compile(r'제\s*(\d+)\s*절')
_HANG_FINDER = re.compile(r'[' + _CIRCLED + r']')
_TITLE_RE = re.compile(r'제\s*\d+\s*조(?:의\s*\d+)?\s*\(([^)]*)\)')


# 문제 2: 항 단위 최대 문자 수. 초과하면 경고 (현재는 분할하지 않고 경고만)
# 이 값을 초과하는 항은 LLM이 긴 입력으로 인해 잘릴 수 있음을 로그로 알림
HANG_MAX_CHARS = int(os.getenv("HANG_MAX_CHARS", "3000"))


def _make_unit(article_number, hang_number, structural_index, full_text,
               article_title, is_addendum, cross_law_refs=None, intra_law_refs=None):
    """항 단위 딕셔너리를 생성한다.

    cross_law_refs: 타 법령(「법명」) 조항 참조 — HGT 다법령 통합 추론 학습용 핵심 특성.
    intra_law_refs: 본 법령 내부 조항 상호참조 — REFERS_TO 엣지용.
    """
    if len(full_text) > HANG_MAX_CHARS:
        label = f"{article_number}" + (f" 항{hang_number}" if hang_number else "")
        print(f"  ⚠️  [parser] {label} 항 텍스트가 길어 LLM 입력 잘림 위험 "
              f"({len(full_text)}자 > {HANG_MAX_CHARS}자 기준)")
    return {
        "article_number": article_number,
        "hang_number": hang_number,
        "structural_index": structural_index,
        "full_text": full_text,
        "article_title": article_title,
        "is_addendum": is_addendum,
        "cross_law_refs": cross_law_refs or [],
        "intra_law_refs": intra_law_refs or [],
    }


def _split_block_into_hang(block, article_number, article_int, chapter, section,
                           article_title, is_addendum):
    """조 블록을 항(①②③) 단위로 분할. 항이 없으면 조 전체를 1단위로 반환.

    문제 1 대응: 각 항 full_text 앞에 조 제목(stem)을 붙여 "이 조항", "이 자" 같은
    대명사를 LLM이 맥락으로 해소할 수 있도록 한다.
    항별로 타 법령 참조(cross)와 본 법령 내부 참조(intra)를 각각 추출해 저장한다.
    """
    hang_positions = [(m.start(), _CIRCLED_TO_INT[m.group(0)])
                      for m in _HANG_FINDER.finditer(block)]

    # 조 제목/본문 머리말(첫 항 이전 텍스트) = context stem (문제 1)
    stem_end = hang_positions[0][0] if hang_positions else len(block)
    stem = clean_text(block[:stem_end])

    if not hang_positions:
        clean_block = clean_text(block)
        return [_make_unit(article_number, None, [chapter, section, article_int, None],
                           clean_block, article_title, is_addendum,
                           extract_cross_law_refs(clean_block),
                           extract_intra_law_refs(clean_block))]

    units = []
    for j, (pos, hno) in enumerate(hang_positions):
        end = hang_positions[j + 1][0] if j + 1 < len(hang_positions) else len(block)
        hang_text = block[pos:end]
        # 조 제목(stem)을 context로 앞에 부착 → "이 조항"="stem에 정의된 해당 조항" 해소
        full = clean_text(f"{stem}\n{hang_text}".strip() if stem else hang_text.strip())
        units.append(_make_unit(article_number, hno,
                                [chapter, section, article_int, hno],
                                full, article_title, is_addendum,
                                extract_cross_law_refs(hang_text),
                                extract_intra_law_refs(hang_text)))
    return units


def split_into_units(text: str) -> Dict[str, List[Dict]]:
    """법령 텍스트를 조>항 계층으로 분해해 항 단위 추출 단위 리스트를 만든다.

    반환: {front_raw, main_raw, back_raw} — 각 항목은 _make_unit() 딕셔너리.
      front_raw : 앞쪽 3개 조(목적/정의/적용범위 등)의 단위 — 글로벌 컨텍스트용
      main_raw  : 본문 전체 항 단위
      back_raw  : 부칙 항 단위

    조 경계는 '제N조(제목)'(괄호가 따라오는 헤딩)과 부칙만 인정하므로, 내부 참조
    (제16조제1항)나 타 법령 참조(「보험업법」 제2조에)는 경계로 잡히지 않는다.
    드물게 타 법령 참조가 괄호를 동반하는 경우를 대비해, 타 법령 참조 구간 내
    경계는 추가로 배제한다.
    """
    cross_spans = [(m.start(), m.end()) for m in _CROSS_LAW_REF_RE.finditer(text)]
    matches = [
        m for m in _ARTICLE_BOUNDARY_RE.finditer(text)
        if not any(s <= m.start() < e for s, e in cross_spans)
    ]
    if not matches:
        return {
            "front_raw": [],
            "main_raw": [_make_unit("N/A", None, [], clean_text(text), None, False)],
            "back_raw": [],
        }

    # 장/절 위치 인덱스 (조 위치에서의 상위 컨텍스트 조회용)
    chapters = [(m.start(), int(m.group(1))) for m in _CHAPTER_FINDER.finditer(text)]
    sections = [(m.start(), int(m.group(1))) for m in _SECTION_FINDER.finditer(text)]

    def _ctx_at(pos):
        ch = se = None
        for p, v in chapters:
            if p <= pos:
                ch = v
            else:
                break
        for p, v in sections:
            if p <= pos:
                se = v
            else:
                break
        return ch, se

    main_units: List[Dict] = []
    back_units: List[Dict] = []
    in_addendum = False

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        header = m.group(1).replace(" ", "")

        if "부칙" in header:
            in_addendum = True
            continue  # 부칙 헤더 자체는 단위로 만들지 않음 (뒤따르는 제N조가 부칙 조항)

        num_m = _ARTICLE_NUM_RE.search(header)
        article_int = int(num_m.group(1)) if num_m else 0
        chapter, section = _ctx_at(start)
        title_m = _TITLE_RE.search(block)
        article_title = title_m.group(1).strip() if title_m else None

        units = _split_block_into_hang(block, header, article_int, chapter, section,
                                       article_title, in_addendum)
        (back_units if in_addendum else main_units).extend(units)

    # front_raw: 앞쪽 3개 조 번호에 속하는 단위들
    first_article_nums = []
    for u in main_units:
        if u["article_number"] not in first_article_nums:
            first_article_nums.append(u["article_number"])
        if len(first_article_nums) >= 3:
            break
    front_set = set(first_article_nums[:3])
    front_units = [u for u in main_units if u["article_number"] in front_set]

    return {
        "front_raw": front_units,
        "main_raw": main_units,
        "back_raw": back_units,
    }


def clean_text(text: str) -> str:
    """텍스트 정제"""
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 특수문자 정규화
    text = text.replace('\xa0', ' ')
    return text.strip()
