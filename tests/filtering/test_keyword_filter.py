import pytest
from src.filtering.keyword_filter import KeywordFilter
from src.paper import Paper
from datetime import datetime

# --- Test Fixtures ---
@pytest.fixture
def keyword_filter_instance():
    return KeywordFilter()

@pytest.fixture
def sample_papers():
    return [
        Paper(id='1', title='Paper about LLMs', abstract='This paper discusses large language models.', published_date=datetime.now(), source='arxiv'),
        Paper(id='2', title='Diffusion Models Explained', abstract='A deep dive into diffusion models.', published_date=datetime.now(), source='arxiv'),
        Paper(id='3', title='Reinforcement Learning Basics', abstract='Introduction to RL.', published_date=datetime.now(), source='arxiv'),
        Paper(id='4', title='Computer Vision Trends', abstract='Object detection and segmentation.', published_date=datetime.now(), source='arxiv'),
        Paper(id='5', title='The Transformer Architecture', abstract='Attention is all you need.', published_date=datetime.now(), source='arxiv'),
    ]

# --- Test Cases ---

def test_configure_keywords(keyword_filter_instance):
    """Test that keywords are loaded and lowercased during configuration."""
    config = {'keywords': ['Transformer', 'Diffusion Model', 'RL']}
    keyword_filter_instance.configure(config)
    assert keyword_filter_instance.keywords == ['transformer', 'diffusion model', 'rl']

def test_configure_no_keywords(keyword_filter_instance, caplog):
    """Test configuration with an empty or missing keywords list."""
    keyword_filter_instance.configure({})
    assert keyword_filter_instance.keywords == []
    assert "No keywords specified for KeywordFilter" in caplog.text

    keyword_filter_instance.configure({'keywords': []})
    assert keyword_filter_instance.keywords == []

def test_filter_with_keywords(keyword_filter_instance, sample_papers):
    """Test filtering papers based on configured keywords."""
    config = {'keywords': ['Transformer', 'Diffusion Model', 'RL']}
    keyword_filter_instance.configure(config)
    filtered_papers = keyword_filter_instance.filter(sample_papers)

    assert len(filtered_papers) == 3
    assert filtered_papers[0].id == '2' # Diffusion
    assert filtered_papers[1].id == '3' # RL
    assert filtered_papers[2].id == '5' # Transformer

def test_filter_case_insensitivity(keyword_filter_instance, sample_papers):
    """Test that filtering is case-insensitive."""
    config = {'keywords': ['transformer', 'rl']} # Lowercase keywords
    keyword_filter_instance.configure(config)
    filtered_papers = keyword_filter_instance.filter(sample_papers)

    assert len(filtered_papers) == 2
    assert filtered_papers[0].id == '3' # Reinforcement Learning contains RL
    assert filtered_papers[1].id == '5' # Transformer title matches

def test_filter_no_matches(keyword_filter_instance, sample_papers):
    """Test filtering when no papers match the keywords."""
    config = {'keywords': ['GAN', 'Quantum Computing']}
    keyword_filter_instance.configure(config)
    filtered_papers = keyword_filter_instance.filter(sample_papers)
    assert len(filtered_papers) == 0

def test_filter_no_keywords_configured(keyword_filter_instance, sample_papers, caplog):
    """Test that all papers are returned if no keywords are configured."""
    keyword_filter_instance.configure({}) # No keywords
    filtered_papers = keyword_filter_instance.filter(sample_papers)

    assert len(filtered_papers) == len(sample_papers)
    assert "KeywordFilter has no keywords configured, returning all papers." in caplog.text

def test_filter_empty_paper_list(keyword_filter_instance):
    """Test filtering an empty list of papers."""
    config = {'keywords': ['test']}
    keyword_filter_instance.configure(config)
    filtered_papers = keyword_filter_instance.filter([])
    assert len(filtered_papers) == 0
