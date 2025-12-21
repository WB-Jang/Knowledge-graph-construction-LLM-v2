"""Tests for extraction chains with mocking"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.chains.entity_extraction_chain import EntityExtractionChain
from src.chains.relation_extraction_chain import RelationExtractionChain
from src.models.schemas import LegalEntity, GraphTriplet


class TestEntityExtractionChain:
    """Test EntityExtractionChain"""
    
    @patch('src.chains.entity_extraction_chain.opensource_llm')
    def test_entity_extraction_chain_initialization(self, mock_llm_fn):
        """Test entity extraction chain initialization"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        chain = EntityExtractionChain()
        
        assert chain.llm is not None
        assert chain.parser is not None
        assert chain.prompt is not None
    
    @patch('src.chains.entity_extraction_chain.opensource_llm')
    def test_extract_success(self, mock_llm_fn):
        """Test successful entity extraction"""
        # Mock LLM
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        # Create expected entity
        expected_entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            subject="국가",
            action="보호한다",
            object="개인정보",
            full_text="제1조(목적) 국가는 개인정보를 보호한다."
        )
        
        # Mock the chain
        chain = EntityExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.return_value = expected_entity
        
        # Test
        text = "제1조(목적) 국가는 개인정보를 보호한다."
        result = chain.extract(text)
        
        assert result.article_number == "제1조"
        assert result.concept == "목적"
        assert result.subject == "국가"
    
    @patch('src.chains.entity_extraction_chain.opensource_llm')
    def test_extract_error_handling(self, mock_llm_fn):
        """Test entity extraction error handling"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        # Mock chain to raise error
        chain = EntityExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.side_effect = Exception("LLM Error")
        
        # Should return default entity on error
        text = "제1조(목적)"
        result = chain.extract(text)
        
        assert result.article_number == "Unknown"
        assert result.concept == "Unknown"
        assert result.full_text == text
    
    @patch('src.chains.entity_extraction_chain.opensource_llm')
    def test_batch_extract(self, mock_llm_fn):
        """Test batch entity extraction"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        chain = EntityExtractionChain()
        
        # Mock extract method
        entity1 = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조"
        )
        entity2 = LegalEntity(
            article_number="제2조",
            concept="정의",
            full_text="제2조"
        )
        
        chain.extract = Mock(side_effect=[entity1, entity2])
        
        texts = ["제1조", "제2조"]
        results = chain.batch_extract(texts)
        
        assert len(results) == 2
        assert results[0].article_number == "제1조"
        assert results[1].article_number == "제2조"


class TestRelationExtractionChain:
    """Test RelationExtractionChain"""
    
    @patch('src.chains.relation_extraction_chain.opensource_llm')
    def test_relation_extraction_chain_initialization(self, mock_llm_fn):
        """Test relation extraction chain initialization"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        chain = RelationExtractionChain()
        
        assert chain.llm is not None
        assert chain.parser is not None
        assert chain.prompt is not None
    
    @patch('src.chains.relation_extraction_chain.opensource_llm')
    def test_extract_success(self, mock_llm_fn):
        """Test successful relation extraction"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        # Create test entity
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            subject="국가",
            action="보호한다",
            object="개인정보",
            full_text="제1조(목적) 국가는 개인정보를 보호한다."
        )
        
        # Expected triplet
        expected_triplet = GraphTriplet(
            subject="국가",
            relation="요구함",
            object="개인정보 보호",
            article_number="제1조",
            confidence=0.9
        )
        
        # Mock chain
        chain = RelationExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.return_value = expected_triplet
        
        # Test
        results = chain.extract(entity)
        
        assert len(results) == 1
        assert results[0].subject == "국가"
        assert results[0].relation == "요구함"
        assert results[0].article_number == "제1조"
    
    @patch('src.chains.relation_extraction_chain.opensource_llm')
    def test_extract_with_context(self, mock_llm_fn):
        """Test relation extraction with context"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        # Create entities
        context_entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조(목적)"
        )
        
        current_entity = LegalEntity(
            article_number="제2조",
            concept="정의",
            subject="법",
            action="정의한다",
            object="용어",
            full_text="제2조(정의) 법은 용어를 정의한다."
        )
        
        triplet = GraphTriplet(
            subject="제2조",
            relation="참조함",
            object="제1조",
            article_number="제2조"
        )
        
        chain = RelationExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.return_value = triplet
        
        results = chain.extract(current_entity, context=[context_entity])
        
        assert len(results) == 1
        assert results[0].relation == "참조함"
    
    @patch('src.chains.relation_extraction_chain.opensource_llm')
    def test_extract_error_handling(self, mock_llm_fn):
        """Test relation extraction error handling"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조"
        )
        
        chain = RelationExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.side_effect = Exception("LLM Error")
        
        # Should return empty list on error
        results = chain.extract(entity)
        
        assert results == []
    
    @patch('src.chains.relation_extraction_chain.opensource_llm')
    def test_extract_returns_list(self, mock_llm_fn):
        """Test that extract always returns a list"""
        mock_llm = MagicMock()
        mock_llm_fn.return_value = mock_llm
        
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조"
        )
        
        triplet = GraphTriplet(
            subject="주체",
            relation="관계",
            object="대상",
            article_number="제1조"
        )
        
        chain = RelationExtractionChain()
        chain.chain = MagicMock()
        chain.chain.invoke.return_value = triplet
        
        results = chain.extract(entity)
        
        # Should convert single triplet to list
        assert isinstance(results, list)
        assert len(results) == 1
