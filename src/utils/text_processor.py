import re
from typing import List, Dict

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

def clean_text(text: str) -> str:
    """텍스트 정제"""
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 특수문자 정규화
    text = text.replace('\xa0', ' ')
    return text.strip()
