import os
from typing import List, Dict, Any
from neo4j import GraphDatabase
from models.schemas import LegalDocument


class MemgraphClient:
    """Memgraph 클라이언트"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = "",
        password: str = ""
    ):
        self.host = host or os.getenv("MEMGRAPH_HOST", "memgraph")
        self.port = port or int(os.getenv("MEMGRAPH_PORT", "7687"))
        self.username = username or os.getenv("MEMGRAPH_USERNAME", "")
        self.password = password or os.getenv("MEMGRAPH_PASSWORD", "")

        uri = f"bolt://{self.host}:{self.port}"
        auth = (self.username, self.password) if self.username else None
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def clear_database(self):
        """데이터베이스 초기화"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("🗑️  데이터베이스 초기화 완료")

    def create_indexes(self):
        """인덱스 생성"""
        with self.driver.session() as session:
            for query in [
                "CREATE INDEX ON :Document(doc_id)",
                "CREATE INDEX ON :Document(title)",
                "CREATE INDEX ON :Article(number)",
                "CREATE INDEX ON :Article(entity_type)",  # ← 추가: 타입별 조회 최적화
                "CREATE INDEX ON :Entity(name)",
            ]:
                try:
                    session.run(query)
                except:
                    pass
        print("📑 인덱스 생성 완료")

    def save_document(self, document: LegalDocument):
        """법률 문서를 Memgraph에 저장"""
        with self.driver.session() as session:
            # 1. 문서 노드 생성 (doc_id 기준 MERGE로 중복 방지)
            session.run("""
                MERGE (d:Document {doc_id: $doc_id})
                SET d.title            = $title,
                    d.enforcement_date = $enforcement_date,
                    d.created_at       = $created_at,
                    d.pipeline_version = $pipeline_version,
                    d.generator_model  = $generator_model,
                    d.evaluator_model  = $evaluator_model
            """,
                doc_id=document.doc_id,
                title=document.title,
                enforcement_date=document.enforcement_date,
                created_at=document.created_at,
                pipeline_version=document.pipeline_version,
                generator_model=document.generator_model,
                evaluator_model=document.evaluator_model,
            )

            # 2. Article 노드 생성 및 Document-[:CONTAINS]->Article 관계
            for entity in document.entities:
                session.run("""
                    MATCH (d:Document {doc_id: $doc_id})
                    MERGE (a:Article {number: $number, doc_id: $doc_id})
                    SET a.entity_type      = $entity_type,
                        a.structural_index = $structural_index,
                        a.concept          = $concept,
                        a.subject          = $subject,
                        a.action           = $action,
                        a.object           = $object,
                        a.legal_force      = $legal_force,
                        a.full_text        = $full_text,
                        a.pipeline_version = $pipeline_version,
                        a.generator_model  = $generator_model,
                        a.evaluator_model  = $evaluator_model,
                        a.eval_score       = $eval_score,
                        a.retry_count      = $retry_count
                    MERGE (d)-[:CONTAINS]->(a)
                """,
                    doc_id=document.doc_id,
                    number=entity.article_number,
                    entity_type=entity.entity_type,
                    structural_index=entity.structural_index,
                    concept=entity.concept,
                    subject=entity.subject,
                    action=entity.action,
                    object=entity.object,
                    legal_force=entity.legal_force,
                    full_text=entity.full_text,
                    pipeline_version=entity.pipeline_version or document.pipeline_version,
                    generator_model=entity.generator_model or document.generator_model,
                    evaluator_model=entity.evaluator_model or document.evaluator_model,
                    eval_score=entity.eval_score,
                    retry_count=entity.retry_count,
                )

            # 3. 트리플 관계 생성
            for triplet in document.triplets:
                session.run("""
                    MERGE (s:Entity {name: $subject})
                    MERGE (o:Entity {name: $object})
                    CREATE (s)-[r:RELATION {
                        type:              $relation,
                        relation_category: $relation_category,
                        confidence:        $confidence,
                        article_number:    $article_number,
                        concepts:          $concepts,
                        created_at:        $created_at,
                        pipeline_version:  $pipeline_version,
                        generator_model:   $generator_model,
                        evaluator_model:   $evaluator_model,
                        eval_score:        $eval_score,
                        retry_count:       $retry_count
                    }]->(o)
                """,
                    subject=triplet.subject,
                    object=triplet.object,
                    relation=triplet.relation,
                    relation_category=triplet.relation_category,
                    confidence=triplet.confidence,
                    article_number=triplet.article_number,
                    concepts=triplet.concepts,
                    created_at=triplet.created_at,
                    pipeline_version=triplet.pipeline_version or document.pipeline_version,
                    generator_model=triplet.generator_model or document.generator_model,
                    evaluator_model=triplet.evaluator_model or document.evaluator_model,
                    eval_score=triplet.eval_score,
                    retry_count=triplet.retry_count,
                )

        print(f"✅ '{document.title}' 지식 그래프가 Memgraph에 저장되었습니다.")
        print(f"   📄 문서 ID : {document.doc_id}")
        print(f"   🗂  엔터티  : {len(document.entities)}개")
        print(f"   🔗 트리플  : {len(document.triplets)}개")

    def query_article(self, article_number: str) -> Dict[str, Any]:
        """조항 조회"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article {number: $number})
                RETURN a
            """, number=article_number)
            record = result.single()
            return dict(record["a"]) if record else None

    def query_relations(self, article_number: str) -> List[Dict[str, Any]]:
        """조항 관련 관계 조회"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (s:Entity)-[r:RELATION {article_number: $number}]->(o:Entity)
                RETURN s.name              AS subject,
                       r.type              AS relation,
                       r.relation_category AS relation_category,
                       o.name              AS object,
                       r.confidence        AS confidence,
                       r.concepts          AS concepts,
                       r.created_at        AS created_at
            """, number=article_number)
            return [dict(record) for record in result]

    def query_articles_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """entity_type 기준 조항 조회 (예: ACTOR, CONCEPT, REGULATION, PENALTY)"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article {entity_type: $entity_type})
                RETURN a
            """, entity_type=entity_type)
            return [dict(record["a"]) for record in result]

    def get_graph_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN
                    count(CASE WHEN 'Document' IN labels(n) THEN 1 END) AS documents,
                    count(CASE WHEN 'Article'  IN labels(n) THEN 1 END) AS articles,
                    count(CASE WHEN 'Entity'   IN labels(n) THEN 1 END) AS entities
            """)
            record = result.single()
            return dict(record) if record else {}

    def close(self):
        """연결 종료"""
        if self.driver:
            self.driver.close()
        print("👋 Memgraph 연결 종료")