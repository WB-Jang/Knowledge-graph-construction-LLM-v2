"""Tests for Colab notebook validation"""
import json
import pytest
from pathlib import Path


class TestColabNotebook:
    """Test Colab notebook structure and validity"""
    
    @pytest.fixture
    def notebook_path(self):
        """Get notebook path"""
        return Path(__file__).parent.parent / "knowledge_graph_colab.ipynb"
    
    @pytest.fixture
    def notebook(self, notebook_path):
        """Load notebook"""
        with open(notebook_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def test_notebook_exists(self, notebook_path):
        """Test that notebook file exists"""
        assert notebook_path.exists()
        assert notebook_path.is_file()
    
    def test_valid_json_format(self, notebook):
        """Test that notebook is valid JSON"""
        assert isinstance(notebook, dict)
    
    def test_nbformat_version(self, notebook):
        """Test that notebook uses correct nbformat"""
        assert notebook.get('nbformat') == 4
        assert notebook.get('nbformat_minor') == 0
    
    def test_has_cells(self, notebook):
        """Test that notebook has cells"""
        cells = notebook.get('cells', [])
        assert len(cells) > 0
        assert len(cells) == 20  # Expected number of cells
    
    def test_cell_types(self, notebook):
        """Test that notebook has both markdown and code cells"""
        cells = notebook.get('cells', [])
        cell_types = [cell.get('cell_type') for cell in cells]
        
        assert 'markdown' in cell_types
        assert 'code' in cell_types
    
    def test_gpu_metadata(self, notebook):
        """Test that notebook is configured for GPU"""
        metadata = notebook.get('metadata', {})
        
        # Check GPU configuration
        assert metadata.get('accelerator') == 'GPU'
        
        # Check Colab GPU type
        colab_metadata = metadata.get('colab', {})
        assert colab_metadata.get('gpuType') == 'T4'
    
    def test_required_sections(self, notebook):
        """Test that notebook has all required sections"""
        required_sections = [
            '환경 설정',
            'API 키 설정',
            '간소화 스크립트',
            '샘플 실행',
            'PDF 파일 처리',
            '결과 시각화',
            '결과 다운로드',
            '참고사항'
        ]
        
        cells = notebook.get('cells', [])
        markdown_content = []
        
        for cell in cells:
            if cell.get('cell_type') == 'markdown':
                source = ''.join(cell.get('source', []))
                markdown_content.append(source)
        
        full_content = '\n'.join(markdown_content)
        
        for section in required_sections:
            assert section in full_content, f"Missing section: {section}"
    
    def test_has_title(self, notebook):
        """Test that notebook has a title"""
        cells = notebook.get('cells', [])
        first_cell = cells[0] if cells else {}
        
        assert first_cell.get('cell_type') == 'markdown'
        source = ''.join(first_cell.get('source', []))
        assert 'Legal Knowledge Graph' in source
        assert 'Colab' in source
    
    def test_has_installation_code(self, notebook):
        """Test that notebook includes installation commands"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        # Check for essential installations
        assert 'pip install' in full_code
        assert 'langchain' in full_code
        assert 'google-generativeai' in full_code
        assert 'PyMuPDF' in full_code
    
    def test_has_api_key_setup(self, notebook):
        """Test that notebook includes API key setup"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        assert 'GOOGLE_API_KEY' in full_code
        assert 'getpass' in full_code
    
    def test_has_repo_clone(self, notebook):
        """Test that notebook includes repository clone command"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        assert 'git clone' in full_code
        assert 'Knowledge-graph-construction-LLM-v2' in full_code
    
    def test_has_sample_execution(self, notebook):
        """Test that notebook includes sample execution"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        # Check for sample legal text
        assert '개인정보' in full_code or '개인정보보호법' in full_code
        assert 'process_document' in full_code
    
    def test_has_visualization(self, notebook):
        """Test that notebook includes visualization code"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        assert 'matplotlib' in full_code or 'plt' in full_code
    
    def test_has_download_capability(self, notebook):
        """Test that notebook includes file download"""
        cells = notebook.get('cells', [])
        code_cells = [cell for cell in cells if cell.get('cell_type') == 'code']
        
        all_code = []
        for cell in code_cells:
            source = ''.join(cell.get('source', []))
            all_code.append(source)
        
        full_code = '\n'.join(all_code)
        
        assert 'files.download' in full_code or 'google.colab' in full_code
