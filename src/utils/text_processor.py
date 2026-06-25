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


def clean_text(text: str) -> str:
    """텍스트 정제"""
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 특수문자 정규화
    text = text.replace('\xa0', ' ')
    return text.strip()
