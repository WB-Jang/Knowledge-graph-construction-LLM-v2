"""Tests for LegalKnowledgeGraphWorkflow"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.graphs.legal_graph import LegalKnowledgeGraphWorkflow, GraphState
from src.models.schemas import LegalDocument, LegalEntity, GraphTriplet


class TestLegalKnowledgeGraphWorkflow:
    """Test LegalKnowledgeGraphWorkflow"""
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_workflow_initialization(self, mock_relation_chain, mock_entity_chain):
        """Test workflow initialization"""
        workflow = LegalKnowledgeGraphWorkflow()
        
        assert workflow.entity_chain is not None
        assert workflow.relation_chain is not None
        assert workflow.workflow is not None
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_split_articles(self, mock_relation_chain, mock_entity_chain):
        """Test _split_articles method"""
        workflow = LegalKnowledgeGraphWorkflow()
        
        document = LegalDocument(
            title="테스트 법률",
            law_number="법률 제1호",
            content="제1조(목적) 목적입니다.\n제2조(정의) 정의입니다."
        )
        
        state: GraphState = {
            "document": document,
            "articles": [],
            "entities": [],
            "triplets": [],
            "current_index": 0,
            "errors": []
        }
        
        result = workflow._split_articles(state)
        
        assert len(result["articles"]) > 0
        assert result["current_index"] == 0
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_extract_entities(self, mock_relation_chain, mock_entity_chain):
        """Test _extract_entities method"""
        # Mock entity chain
        mock_entity_instance = MagicMock()
        test_entities = [
            LegalEntity(
                article_number="제1조",
                concept="목적",
                full_text="제1조"
            )
        ]
        mock_entity_instance.batch_extract.return_value = test_entities
        mock_entity_chain.return_value = mock_entity_instance
        
        workflow = LegalKnowledgeGraphWorkflow()
        
        document = LegalDocument(
            title="테스트",
            law_number="법률 제1호",
            content="제1조"
        )
        
        state: GraphState = {
            "document": document,
            "articles": ["제1조(목적)"],
            "entities": [],
            "triplets": [],
            "current_index": 0,
            "errors": []
        }
        
        result = workflow._extract_entities(state)
        
        assert len(result["entities"]) == 1
        assert result["entities"][0].article_number == "제1조"
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_extract_entities_error_handling(self, mock_relation_chain, mock_entity_chain):
        """Test _extract_entities error handling"""
        mock_entity_instance = MagicMock()
        mock_entity_instance.batch_extract.side_effect = Exception("Extraction error")
        mock_entity_chain.return_value = mock_entity_instance
        
        workflow = LegalKnowledgeGraphWorkflow()
        
        document = LegalDocument(
            title="테스트",
            law_number="법률 제1호",
            content="제1조"
        )
        
        state: GraphState = {
            "document": document,
            "articles": ["제1조"],
            "entities": [],
            "triplets": [],
            "current_index": 0,
            "errors": []
        }
        
        result = workflow._extract_entities(state)
        
        assert len(result["errors"]) == 1
        assert "Entity extraction error" in result["errors"][0]
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_extract_relations(self, mock_relation_chain, mock_entity_chain):
        """Test _extract_relations method"""
        # Mock relation chain
        mock_relation_instance = MagicMock()
        test_triplet = GraphTriplet(
            subject="주체",
            relation="관계",
            object="대상",
            article_number="제1조"
        )
        mock_relation_instance.extract.return_value = [test_triplet]
        mock_relation_chain.return_value = mock_relation_instance
        
        workflow = LegalKnowledgeGraphWorkflow()
        
        entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조"
        )
        
        document = LegalDocument(
            title="테스트",
            law_number="법률 제1호",
            content="제1조"
        )
        
        state: GraphState = {
            "document": document,
            "articles": ["제1조"],
            "entities": [entity],
            "triplets": [],
            "current_index": 0,
            "errors": []
        }
        
        result = workflow._extract_relations(state)
        
        assert len(result["triplets"]) == 1
        assert result["triplets"][0].article_number == "제1조"
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_validate_graph(self, mock_relation_chain, mock_entity_chain):
        """Test _validate_graph method"""
        workflow = LegalKnowledgeGraphWorkflow()
        
        # Create duplicate triplets
        triplet1 = GraphTriplet(
            subject="주체",
            relation="관계",
            object="대상",
            article_number="제1조",
            confidence=0.8
        )
        
        triplet2 = GraphTriplet(
            subject="주체",
            relation="관계",
            object="대상",
            article_number="제1조",
            confidence=0.9
        )
        
        document = LegalDocument(
            title="테스트",
            law_number="법률 제1호",
            content="제1조"
        )
        
        state: GraphState = {
            "document": document,
            "articles": [],
            "entities": [],
            "triplets": [triplet1, triplet2],
            "current_index": 0,
            "errors": []
        }
        
        result = workflow._validate_graph(state)
        
        # Should keep only one with higher confidence
        assert len(result["triplets"]) == 1
        assert result["triplets"][0].confidence == 0.9
    
    @patch('src.graphs.legal_graph.EntityExtractionChain')
    @patch('src.graphs.legal_graph.RelationExtractionChain')
    def test_process_document(self, mock_relation_chain, mock_entity_chain):
        """Test full process method"""
        # Setup mocks
        mock_entity_instance = MagicMock()
        test_entity = LegalEntity(
            article_number="제1조",
            concept="목적",
            full_text="제1조(목적)"
        )
        mock_entity_instance.batch_extract.return_value = [test_entity]
        mock_entity_chain.return_value = mock_entity_instance
        
        mock_relation_instance = MagicMock()
        test_triplet = GraphTriplet(
            subject="법",
            relation="정의함",
            object="목적",
            article_number="제1조"
        )
        mock_relation_instance.extract.return_value = [test_triplet]
        mock_relation_chain.return_value = mock_relation_instance
        
        workflow = LegalKnowledgeGraphWorkflow()
        
        document = LegalDocument(
            title="개인정보 보호법",
            law_number="법률 제18583호",
            content="제1조(목적) 이 법은 개인정보 보호를 목적으로 한다."
        )
        
        result = workflow.process(document)
        
        assert result.title == "개인정보 보호법"
        assert len(result.entities) > 0
        assert len(result.triplets) > 0
