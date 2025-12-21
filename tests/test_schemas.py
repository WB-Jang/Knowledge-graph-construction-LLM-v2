"""Tests for data models and schemas"""
import pytest
from src.models.schemas import (
    LegalEntity, 
    GraphTriplet, 
    LegalDocument, 
    RelationType
)


class TestLegalEntity:
    """Test LegalEntity model"""
    
    def test_create_legal_entity(self):
        """Test creating a legal entity"""
        entity = LegalEntity(
            article_number="제1조",
            concept="개인정보 보호",
            subject="개인정보처리자",
            action="보호하여야",
            object="개인정보",
            full_text="제1조(목적) 개인정보를 보호하여야 한다."
        )
        
        assert entity.article_number == "제1조"
        assert entity.concept == "개인정보 보호"
        assert entity.subject == "개인정보처리자"
        assert entity.action == "보호하여야"
        assert entity.object == "개인정보"
    
    def test_legal_entity_optional_fields(self):
        """Test legal entity with optional fields as None"""
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조(목적) 이 법은 목적을 정함."
        )
        
        assert entity.subject is None
        assert entity.action is None
        assert entity.object is None
    
    def test_legal_entity_validation(self):
        """Test validation of required fields"""
        with pytest.raises(Exception):
            # Missing required fields should raise error
            LegalEntity()


class TestGraphTriplet:
    """Test GraphTriplet model"""
    
    def test_create_graph_triplet(self):
        """Test creating a graph triplet"""
        triplet = GraphTriplet(
            subject="개인정보처리자",
            relation="요구함",
            object="동의",
            article_number="제15조",
            confidence=0.95
        )
        
        assert triplet.subject == "개인정보처리자"
        assert triplet.relation == "요구함"
        assert triplet.object == "동의"
        assert triplet.article_number == "제15조"
        assert triplet.confidence == 0.95
    
    def test_graph_triplet_default_confidence(self):
        """Test default confidence value"""
        triplet = GraphTriplet(
            subject="주체",
            relation="관계",
            object="대상",
            article_number="제1조"
        )
        
        assert triplet.confidence == 1.0


class TestRelationType:
    """Test RelationType enum"""
    
    def test_relation_type_values(self):
        """Test relation type enum values"""
        assert RelationType.PARENT_ARTICLE == "상위조항"
        assert RelationType.REFERS_TO == "참조함"
        assert RelationType.DEFINES == "정의함"
        assert RelationType.REQUIRES == "요구함"
        assert RelationType.PROHIBITS == "금지함"
        assert RelationType.ALLOWS == "허용함"
    
    def test_relation_type_membership(self):
        """Test checking if value is in enum"""
        assert "상위조항" in [rt.value for rt in RelationType]
        assert "요구함" in [rt.value for rt in RelationType]
        assert "invalid" not in [rt.value for rt in RelationType]


class TestLegalDocument:
    """Test LegalDocument model"""
    
    def test_create_legal_document(self):
        """Test creating a legal document"""
        doc = LegalDocument(
            title="개인정보 보호법",
            law_number="법률 제18583호",
            content="제1조(목적) 이 법은..."
        )
        
        assert doc.title == "개인정보 보호법"
        assert doc.law_number == "법률 제18583호"
        assert doc.content == "제1조(목적) 이 법은..."
        assert doc.entities == []
        assert doc.triplets == []
    
    def test_legal_document_with_entities_and_triplets(self):
        """Test legal document with entities and triplets"""
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조(목적)"
        )
        
        triplet = GraphTriplet(
            subject="법",
            relation="정의함",
            object="목적",
            article_number="제1조"
        )
        
        doc = LegalDocument(
            title="테스트 법률",
            law_number="법률 제1호",
            content="제1조",
            entities=[entity],
            triplets=[triplet]
        )
        
        assert len(doc.entities) == 1
        assert len(doc.triplets) == 1
        assert doc.entities[0].article_number == "제1조"
        assert doc.triplets[0].relation == "정의함"
