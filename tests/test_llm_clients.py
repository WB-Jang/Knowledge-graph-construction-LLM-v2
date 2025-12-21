"""Tests for LLM clients with mocking"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from src.llm.gemini_client import GeminiClient, get_llm
from src.llm.llama_client import LlamaCppClient, LlamaCppChatClient


class TestGeminiClient:
    """Test GeminiClient"""
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key', 'GEMINI_MODEL': 'gemini-1.5-flash'})
    @patch('src.llm.gemini_client.genai')
    @patch('src.llm.gemini_client.ChatGoogleGenerativeAI')
    def test_gemini_client_initialization(self, mock_chat, mock_genai):
        """Test Gemini client initialization"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        
        client = GeminiClient()
        
        assert client.api_key == 'test-key'
        assert client.model_name == 'gemini-1.5-flash'
        mock_genai.configure.assert_called_once_with(api_key='test-key')
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gemini_client_missing_api_key(self):
        """Test Gemini client without API key"""
        with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
            GeminiClient()
    
    @patch.dict(os.environ, {'GOOGLE_API_KEY': 'test-key'})
    @patch('src.llm.gemini_client.genai')
    @patch('src.llm.gemini_client.ChatGoogleGenerativeAI')
    def test_gemini_invoke(self, mock_chat, mock_genai):
        """Test Gemini invoke method"""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "테스트 응답"
        mock_llm.invoke.return_value = mock_response
        mock_chat.return_value = mock_llm
        
        client = GeminiClient()
        result = client.invoke("테스트 프롬프트")
        
        assert result == "테스트 응답"
        mock_llm.invoke.assert_called_once()


class TestLlamaCppClient:
    """Test LlamaCppClient"""
    
    @patch.dict(os.environ, {
        'LLAMA_CPP_API_URL': 'http://localhost:8000',
        'LLM_MODEL_NAME': 'test-model',
        'LLM_TEMPERATURE': '0.5',
        'LLM_MAX_TOKENS': '1024'
    })
    def test_llama_client_initialization(self):
        """Test LlamaCpp client initialization"""
        client = LlamaCppClient()
        
        assert client.api_url == 'http://localhost:8000'
        assert client.model_name == 'test-model'
        assert client.temperature == 0.5
        assert client.max_tokens == 1024
    
    @patch.dict(os.environ, {'LLAMA_CPP_API_URL': 'http://localhost:8000'})
    @patch('httpx.Client')
    def test_llama_client_call(self, mock_client_class):
        """Test LlamaCpp _call method"""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"text": "테스트 응답"}]
        }
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client
        
        client = LlamaCppClient()
        result = client._call("테스트 프롬프트")
        
        assert result == "테스트 응답"
        mock_client.post.assert_called_once()
    
    @patch.dict(os.environ, {'LLAMA_CPP_API_URL': 'http://localhost:8000'})
    @patch('httpx.Client')
    def test_llama_client_call_error(self, mock_client_class):
        """Test LlamaCpp _call method with error"""
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("Connection error")
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client
        
        client = LlamaCppClient()
        
        with pytest.raises(Exception, match="예상치 못한 오류"):
            client._call("테스트 프롬프트")


class TestLlamaCppChatClient:
    """Test LlamaCppChatClient"""
    
    @patch.dict(os.environ, {'LLAMA_CPP_API_URL': 'http://localhost:8000'})
    @patch('httpx.Client')
    def test_llama_chat_client_call(self, mock_client_class):
        """Test LlamaCppChat _call method"""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "채팅 응답"}}]
        }
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client_class.return_value = mock_client
        
        client = LlamaCppChatClient()
        result = client._call("테스트 프롬프트")
        
        assert result == "채팅 응답"
        mock_client.post.assert_called_once()


class TestGetLLM:
    """Test get_llm function"""
    
    @patch.dict(os.environ, {'USE_LOCAL_LLM': 'false', 'GOOGLE_API_KEY': 'test-key'})
    @patch('src.llm.gemini_client.genai')
    @patch('src.llm.gemini_client.ChatGoogleGenerativeAI')
    def test_get_llm_gemini(self, mock_chat, mock_genai):
        """Test getting Gemini LLM"""
        mock_llm = MagicMock()
        mock_chat.return_value = mock_llm
        
        llm = get_llm()
        
        # Should return Gemini LLM
        assert llm is not None
    
    @patch.dict(os.environ, {'USE_LOCAL_LLM': 'true', 'LLAMA_CPP_API_URL': 'http://localhost:8000'})
    def test_get_llm_local(self):
        """Test getting local LLM"""
        from src.llm.llama_client import get_llm as llama_get_llm, LlamaCppChatClient
        
        llm = llama_get_llm()
        
        # Should return LlamaCppChatClient (default)
        assert isinstance(llm, LlamaCppChatClient)
