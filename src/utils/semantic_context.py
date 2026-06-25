"""의미 유사도 기반 동적 글로벌 컨텍스트 선택기 (옵션 기능).

기본적으로 비활성화되어 있으며, 환경변수 ENABLE_SEMANTIC_GLOBAL_CONTEXT=true 로
켰을 때만 워크플로우에서 사용됩니다.

현재 분석 중인 조항과 의미적으로 유사도가 높은 다른 조항들을 동적으로 선택하여,
관계 추출 시 global context(참조 가능한 앵커 조항)로 함께 주입하는 용도입니다.

유사도 방식 (SEMANTIC_SIMILARITY_METHOD):
  - "lexical"  (기본): 문자 n-gram Jaccard 유사도. 추가 의존성 없음(형태소 분석기 불필요).
  - "embedding": OpenAI 호환 임베딩 API + 코사인 유사도. langchain-openai 필요.
"""
import os
from typing import List, Optional, Tuple

from models.schemas import LegalEntity


def _char_ngrams(text: str, n: int = 2) -> set:
    """문자 단위 n-gram 집합 (한국어 토크나이저 없이 사용 가능)."""
    text = "".join(text.split())
    if len(text) < n:
        return {text} if text else set()
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _entity_repr(entity: LegalEntity) -> str:
    """유사도 계산에 사용할 조항 대표 텍스트."""
    parts = [
        entity.concept or "",
        entity.subject or "",
        entity.object or "",
        entity.full_text or "",
    ]
    return " ".join(p for p in parts if p)


class SemanticContextSelector:
    """현재 조항과 의미적으로 유사한 후보 조항을 선택한다."""

    def __init__(self):
        self.method = os.getenv("SEMANTIC_SIMILARITY_METHOD", "lexical").lower()
        self.top_k = int(os.getenv("SEMANTIC_TOP_K", "3"))
        self.min_score = float(os.getenv("SEMANTIC_MIN_SCORE", "0.0"))
        self._embeddings = None  # 지연 초기화

        if self.method == "embedding":
            self._init_embeddings()

    def _init_embeddings(self):
        """임베딩 클라이언트 지연 초기화 (langchain-openai 필요)."""
        try:
            from langchain_openai import OpenAIEmbeddings
            model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("EMBEDDING_BASE_URL")  # None이면 OpenAI 기본 사용
            kwargs = {"model": model}
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["base_url"] = base_url
            self._embeddings = OpenAIEmbeddings(**kwargs)
        except Exception as e:
            print(f"⚠️  임베딩 초기화 실패({e}); lexical 방식으로 폴백합니다.")
            self.method = "lexical"
            self._embeddings = None

    # ── 유사도 계산 ──────────────────────────────────────────────────────────
    def _lexical_scores(self, target: LegalEntity, candidates: List[LegalEntity]) -> List[float]:
        target_ng = _char_ngrams(_entity_repr(target))
        return [_jaccard(target_ng, _char_ngrams(_entity_repr(c))) for c in candidates]

    def _embedding_scores(self, target: LegalEntity, candidates: List[LegalEntity]) -> List[float]:
        texts = [_entity_repr(target)] + [_entity_repr(c) for c in candidates]
        vectors = self._embeddings.embed_documents(texts)
        target_vec = vectors[0]

        def _cosine(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = sum(x * x for x in a) ** 0.5
            nb = sum(y * y for y in b) ** 0.5
            return dot / (na * nb) if na and nb else 0.0

        return [_cosine(target_vec, v) for v in vectors[1:]]

    # ── 공개 API ─────────────────────────────────────────────────────────────
    def select(
        self,
        target: LegalEntity,
        candidates: List[LegalEntity],
    ) -> List[LegalEntity]:
        """target과 유사도가 높은 후보 top_k개를 반환 (min_score 이상만)."""
        if not candidates:
            return []

        try:
            if self.method == "embedding" and self._embeddings is not None:
                scores = self._embedding_scores(target, candidates)
            else:
                scores = self._lexical_scores(target, candidates)
        except Exception as e:
            print(f"⚠️  의미 유사도 계산 실패({e}); lexical 방식으로 재시도합니다.")
            scores = self._lexical_scores(target, candidates)

        ranked: List[Tuple[float, LegalEntity]] = sorted(
            zip(scores, candidates), key=lambda x: x[0], reverse=True
        )
        selected = [ent for score, ent in ranked if score >= self.min_score][: self.top_k]
        return selected
