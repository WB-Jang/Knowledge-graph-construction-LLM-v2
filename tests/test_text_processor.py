"""Tests for text processing utilities"""
import pytest
from src.utils.text_processor import split_articles, clean_text


class TestSplitArticles:
    """Test article splitting functionality"""
    
    def test_split_articles_basic(self):
        """Test basic article splitting"""
        text = """
        제1조(목적) 이 법은 개인정보의 처리를 정함을 목적으로 한다.
        제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.
        제3조(원칙) 개인정보처리자는 목적을 명확하게 하여야 한다.
        """
        
        articles = split_articles(text)
        
        assert len(articles) == 3
        assert "제1조" in articles[0]
        assert "제2조" in articles[1]
        assert "제3조" in articles[2]
    
    def test_split_articles_with_subparagraph(self):
        """Test splitting articles with sub-paragraphs"""
        text = """
        제1조(목적) 이 법은 목적을 정함.
        제1조의2(추가) 추가 조항입니다.
        제2조제1항 첫 번째 항입니다.
        """
        
        articles = split_articles(text)
        
        assert len(articles) >= 2
        assert "제1조" in articles[0]
    
    def test_split_articles_empty(self):
        """Test splitting empty text"""
        text = ""
        articles = split_articles(text)
        
        assert len(articles) == 1
        assert articles[0] == ""
    
    def test_split_articles_no_matches(self):
        """Test text without article markers"""
        text = "이것은 일반 텍스트입니다."
        articles = split_articles(text)
        
        assert len(articles) == 1
        assert articles[0] == text


class TestCleanText:
    """Test text cleaning functionality"""
    
    def test_clean_text_multiple_spaces(self):
        """Test removing multiple spaces"""
        text = "이것은    여러    공백이   있습니다"
        cleaned = clean_text(text)
        
        assert "    " not in cleaned
        assert cleaned == "이것은 여러 공백이 있습니다"
    
    def test_clean_text_special_characters(self):
        """Test normalizing special characters"""
        text = "텍스트\xa0특수문자"
        cleaned = clean_text(text)
        
        assert "\xa0" not in cleaned
        assert " " in cleaned
    
    def test_clean_text_strip(self):
        """Test stripping whitespace"""
        text = "  텍스트  "
        cleaned = clean_text(text)
        
        assert cleaned == "텍스트"
        assert not cleaned.startswith(" ")
        assert not cleaned.endswith(" ")
    
    def test_clean_text_empty(self):
        """Test cleaning empty text"""
        text = ""
        cleaned = clean_text(text)
        
        assert cleaned == ""
