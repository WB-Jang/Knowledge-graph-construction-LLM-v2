import os
from typing import List, Dict, Any
from neo4j import GraphDatabase
from src.models.schemas import LegalDocument


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
        
        # Neo4j 드라이버 (Bolt 프로토콜 - Memgraph 호환)
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
            # 문서 제목 인덱스
            try:
                session.run("CREATE INDEX ON :Document(title)")
            except: 
                pass
            
            # 조항 번호 인덱스
            try:
                session.run("CREATE INDEX ON :Article(number)")
            except:
                pass
            
            # 개체 이름 인덱스
            try:
                session.run("CREATE INDEX ON :Entity(name)")
            except: 
                pass
        
        print("📑 인덱스 생성 완료")
    
    def save_document(self, document: LegalDocument):
        """법률 문서를 Memgraph에 저장"""
        with self.driver.session() as session:
            # 1. 문서 노드 생성
            session.run("""
                CREATE (d:Document {
                    title: $title,
                    law_number: $law_number,
                    created_at: localdatetime()
                })
            """,
                title=document.title,
                law_number=document.law_number
            )
            
            # 2. 조항 노드 및 관계 생성
            for entity in document.entities:
                session.run("""
                    MATCH (d:Document {title: $doc_title})
                    CREATE (a:Article {
                        number: $number,
                        concept: $concept,
                        subject: $subject,
                        action: $action,
                        object: $object,
                        full_text: $full_text
                    })
                    CREATE (d)-[:CONTAINS]->(a)
                """,
                    doc_title=document.title,
                    number=entity.article_number,
                    concept=entity.concept,
                    subject=entity.subject,
                    action=entity.action,
                    object=entity.object,
                    full_text=entity.full_text
                )
            
            # 3. 트리플 관계 생성
            for triplet in document.triplets:
                session.run("""
                    MATCH (a:Article {number: $article_number})
                    MERGE (s:Entity {name: $subject})
                    MERGE (o:Entity {name: $object})
                    CREATE (s)-[r:RELATION {
                        type: $relation,
                        confidence: $confidence,
                        article: $article_number
                    }]->(o)
                """,
                    article_number=triplet.article_number,
                    subject=triplet.subject,
                    object=triplet.object,
                    relation=triplet.relation,
                    confidence=triplet.confidence
                )
        
        print(f"✅ '{document.title}' 지식 그래프가 Memgraph에 저장되었습니다.")
    
    def query_article(self, article_number: str) -> Dict[str, Any]:
        """조항 조회"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article {number: $number})
                RETURN a
            """, number=article_number)
            
            record = result.single()
            if record:
                return dict(record["a"])
            return None
    
    def query_relations(self, article_number: str) -> List[Dict[str, Any]]:
        """조항 관련 관계 조회"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (a:Article {number: $number})-[:HAS_RELATION]->(r:RELATION)
                MATCH (s)-[r]->(o)
                RETURN s.name as subject, r.type as relation, o.name as object, r.confidence as confidence
            """, number=article_number)
            
            return [dict(record) for record in result]
    
    def get_graph_statistics(self) -> Dict[str, int]:
        """그래프 통계"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                RETURN 
                    count(CASE WHEN 'Document' IN labels(n) THEN 1 END) as documents,
                    count(CASE WHEN 'Article' IN labels(n) THEN 1 END) as articles,
                    count(CASE WHEN 'Entity' IN labels(n) THEN 1 END) as entities
            """)
            
            record = result.single()
            return dict(record) if record else {}
    
    def close(self):
        """연결 종료"""
        if self.driver:
            self.driver.close()
        print("👋 Memgraph 연결 종료")