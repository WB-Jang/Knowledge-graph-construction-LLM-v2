"""Tests for Memgraph database client with mocking"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.database.memgraph_client import MemgraphClient
from src.models.schemas import LegalDocument, LegalEntity, GraphTriplet


class TestMemgraphClient:
    """Test MemgraphClient"""
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_memgraph_client_initialization(self, mock_graph_db, mock_memgraph):
        """Test Memgraph client initialization"""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient(host="localhost", port=7687)
        
        assert client.host == "localhost"
        assert client.port == 7687
        mock_graph_db.driver.assert_called_once()
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_clear_database(self, mock_graph_db, mock_memgraph):
        """Test clear_database method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        client.clear_database()
        
        mock_session.run.assert_called_once_with("MATCH (n) DETACH DELETE n")
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_create_indexes(self, mock_graph_db, mock_memgraph):
        """Test create_indexes method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        client.create_indexes()
        
        # Should attempt to create indexes (may fail silently)
        assert mock_session.run.called
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_save_document(self, mock_graph_db, mock_memgraph):
        """Test save_document method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
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
        
        document = LegalDocument(
            title="테스트 법률",
            law_number="법률 제1호",
            content="제1조(목적)",
            entities=[entity],
            triplets=[triplet]
        )
        
        client = MemgraphClient()
        client.save_document(document)
        
        # Should call session.run multiple times (document, entities, triplets)
        assert mock_session.run.call_count >= 3
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_query_article(self, mock_graph_db, mock_memgraph):
        """Test query_article method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = {"a": {"number": "제1조", "concept": "목적"}}
        mock_result.single.return_value = {"a": mock_record}
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        result = client.query_article("제1조")
        
        mock_session.run.assert_called_once()
        assert result is not None
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_query_article_not_found(self, mock_graph_db, mock_memgraph):
        """Test query_article when article not found"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        result = client.query_article("제999조")
        
        assert result is None
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_query_relations(self, mock_graph_db, mock_memgraph):
        """Test query_relations method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = [
            {"subject": "법", "relation": "정의함", "object": "목적", "confidence": 1.0}
        ]
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        results = client.query_relations("제1조")
        
        mock_session.run.assert_called_once()
        assert isinstance(results, list)
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_get_graph_statistics(self, mock_graph_db, mock_memgraph):
        """Test get_graph_statistics method"""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_record = {"documents": 1, "articles": 3, "entities": 5}
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        stats = client.get_graph_statistics()
        
        assert stats["documents"] == 1
        assert stats["articles"] == 3
        assert stats["entities"] == 5
    
    @patch('src.database.memgraph_client.Memgraph')
    @patch('src.database.memgraph_client.GraphDatabase')
    def test_close(self, mock_graph_db, mock_memgraph):
        """Test close method"""
        mock_driver = MagicMock()
        mock_graph_db.driver.return_value = mock_driver
        
        client = MemgraphClient()
        client.close()
        
        mock_driver.close.assert_called_once()
