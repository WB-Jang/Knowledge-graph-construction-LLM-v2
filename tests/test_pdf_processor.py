"""Tests for PDF processing utilities"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestPDFProcessor:
    """Test PDF processor utilities"""
    
    @patch('fitz.open')
    @patch('os.path.exists')
    def test_extract_text_from_pdf(self, mock_exists, mock_fitz_open):
        """Test extracting text from PDF"""
        from src.utils.pdf_processor import extract_text_from_pdf
        
        mock_exists.return_value = True
        
        # Mock PDF document
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "제1조(목적) 이 법은 목적을 정함."
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz_open.return_value = mock_doc
        
        # Test
        result = extract_text_from_pdf("test.pdf")
        
        assert "제1조" in result
        assert "목적" in result
        mock_fitz_open.assert_called_once_with("test.pdf")
    
    def test_extract_text_file_not_found(self):
        """Test file not found error"""
        from src.utils.pdf_processor import extract_text_from_pdf
        
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf("nonexistent.pdf")
    
    @patch('fitz.open')
    @patch('os.path.exists')
    def test_get_pdf_metadata(self, mock_exists, mock_fitz_open):
        """Test getting PDF metadata"""
        from src.utils.pdf_processor import get_pdf_metadata
        
        mock_exists.return_value = True
        
        # Mock PDF document
        mock_doc = MagicMock()
        mock_doc.metadata = {
            "title": "테스트 법률",
            "author": "작성자",
            "subject": "법률 문서"
        }
        mock_doc.__len__.return_value = 10
        mock_fitz_open.return_value = mock_doc
        
        # Test
        result = get_pdf_metadata("test.pdf")
        
        assert result["title"] == "테스트 법률"
        assert result["author"] == "작성자"
        assert result["pages"] == 10
        assert result["filename"] == "test.pdf"
    
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_list_pdf_files(self, mock_listdir, mock_exists):
        """Test listing PDF files in directory"""
        from src.utils.pdf_processor import list_pdf_files
        
        mock_exists.return_value = True
        mock_listdir.return_value = ["doc1.pdf", "doc2.PDF", "text.txt", "doc3.pdf"]
        
        result = list_pdf_files("/test/dir")
        
        assert len(result) == 3
        assert all(f.endswith('.pdf') or f.endswith('.PDF') for f in result)
    
    @patch('os.path.exists')
    def test_list_pdf_files_empty_directory(self, mock_exists):
        """Test listing PDF files in non-existent directory"""
        from src.utils.pdf_processor import list_pdf_files
        
        mock_exists.return_value = False
        
        result = list_pdf_files("/nonexistent/dir")
        
        assert result == []
