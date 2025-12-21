import re
from typing import List


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


def clean_text(text: str) -> str:
    """텍스트 정제"""
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    # 특수문자 정규화
    text = text.replace('\xa0', ' ')
    return text.strip()
