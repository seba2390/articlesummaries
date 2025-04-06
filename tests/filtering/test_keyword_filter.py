import pytest
from typing import List, Dict, Any
from src.filtering.keyword_filter import KeywordFilter
from src.paper import Paper
from datetime import datetime, timezone
import logging

# --- Test Fixtures ---

@pytest.fixture
def keyword_filter_instance() -> KeywordFilter:
    """Provides a clean instance of KeywordFilter for each test."""
    return KeywordFilter()

@pytest.fixture
def sample_papers() -> List[Paper]:
    """Provides a list of sample Paper objects with varying titles and abstracts for testing."""
    # Use a fixed timezone for consistency
    dt = datetime.now(timezone.utc)
    return [
        Paper(id='1', title='Paper about LLMs', abstract='This paper discusses large language models.', published_date=dt, source='arxiv'),
        Paper(id='2', title='Diffusion Models Explained', abstract='A deep dive into diffusion models.', published_date=dt, source='arxiv'),
        Paper(id='3', title='Reinforcement Learning Basics', abstract='Introduction to RL.', published_date=dt, source='arxiv'),
        Paper(id='4', title='Computer Vision Trends', abstract='Object detection and segmentation.', published_date=dt, source='arxiv'),
        Paper(id='5', title='The Transformer Architecture', abstract='Attention is all you need.', published_date=dt, source='arxiv'),
    ]

# --- Test Cases for KeywordFilter ---

def test_configure_keywords(keyword_filter_instance: KeywordFilter):
    """Tests that keywords are correctly loaded from the config and converted to lowercase."""
    # Arrange: Config with mixed-case keywords
    config = {'paper_source': {'arxiv': {'keywords': ['Transformer', 'Diffusion Model', 'RL']}}}
    # Act: Configure the filter
    keyword_filter_instance.configure(config)
    # Assert: Check that keywords are stored in lowercase
    assert keyword_filter_instance.keywords == ['transformer', 'diffusion model', 'rl']

def test_configure_no_keywords(keyword_filter_instance: KeywordFilter, caplog: pytest.LogCaptureFixture):
    """Tests that configuration with an empty or missing keywords list results in an empty
    internal list and logs a warning message.
    """
    # Arrange: Empty config
    config_empty: Dict[str, Any] = {}
    # Act & Assert: Configure with empty config
    with caplog.at_level(logging.WARNING):
        keyword_filter_instance.configure(config_empty)
    assert keyword_filter_instance.keywords == []
    # Assert: Check the specific warning message content
    assert "KeywordFilter configured, but no valid 'keywords' list found within the provided config's 'paper_source' section." in caplog.text
    assert "The filter will pass all papers in this context." in caplog.text
    caplog.clear() # Clear logs for the next check

    # Arrange: Config with empty keywords list
    config_empty_list = {'paper_source': {'arxiv': {'keywords': []}}}
    # Act & Assert: Configure with empty list
    with caplog.at_level(logging.WARNING):
        keyword_filter_instance.configure(config_empty_list)
    assert keyword_filter_instance.keywords == []
    # Assert: Check the specific warning message content again
    assert "KeywordFilter configured, but no valid 'keywords' list found within the provided config's 'paper_source' section." in caplog.text
    assert "The filter will pass all papers in this context." in caplog.text

def test_filter_with_keywords(keyword_filter_instance: KeywordFilter, sample_papers: List[Paper]):
    """Tests the core filtering logic: papers matching configured keywords (case-insensitive)
    in their title or abstract are returned, and their `matched_keywords` attribute is set.
    """
    # Arrange: Configure with keywords expected to match some sample papers
    config = {'paper_source': {'arxiv': {'keywords': ['Transformer', 'Diffusion Model', 'RL']}}}
    keyword_filter_instance.configure(config)
    # Act: Filter the sample papers
    filtered_papers = keyword_filter_instance.filter(sample_papers)
    # Assert: Check the number of returned papers
    assert len(filtered_papers) == 3

    # Assert: Check that the correct papers were returned and `matched_keywords` is set
    matched_map = {p.id: p.matched_keywords for p in filtered_papers}
    assert matched_map.get('5') == ['transformer']      # Matched 'Transformer' in title
    assert matched_map.get('2') == ['diffusion model'] # Matched 'diffusion models' in title/abstract
    assert matched_map.get('3') == ['rl']              # Matched 'RL' in abstract
    assert '1' not in matched_map # LLM paper didn't match specific keywords
    assert '4' not in matched_map # CV paper didn't match

def test_filter_case_insensitivity(keyword_filter_instance: KeywordFilter, sample_papers: List[Paper]):
    """Tests explicitly that keyword matching ignores case differences between the keyword
    list and the paper content.
    """
    # Arrange: Configure with lowercase keywords
    config = {'paper_source': {'arxiv': {'keywords': ['transformer', 'rl']}}}
    keyword_filter_instance.configure(config)
    # Act: Filter the sample papers
    filtered_papers = keyword_filter_instance.filter(sample_papers)
    # Assert: Check that papers with different casing still match
    assert len(filtered_papers) == 2
    matched_map = {p.id: p.matched_keywords for p in filtered_papers}
    assert matched_map.get('5') == ['transformer'] # Matched 'Transformer' title
    assert matched_map.get('3') == ['rl']          # Matched 'RL' abstract

def test_filter_no_match(keyword_filter_instance: KeywordFilter, sample_papers: List[Paper]):
    """Tests that no papers are returned if none of the configured keywords match any papers."""
    # Arrange: Configure with keywords that do not appear in sample papers
    config = {'paper_source': {'arxiv': {'keywords': ['nonexistent', 'keyword']}}}
    keyword_filter_instance.configure(config)
    # Act: Filter the sample papers
    filtered_papers = keyword_filter_instance.filter(sample_papers)
    # Assert: The list of filtered papers should be empty
    assert len(filtered_papers) == 0

def test_filter_no_keywords_configured(keyword_filter_instance: KeywordFilter, sample_papers: List[Paper], caplog: pytest.LogCaptureFixture):
    """Tests that if the filter is used without any keywords configured, it returns all
    input papers and logs an informational message.
    """
    # Arrange: Configure with no keywords
    keyword_filter_instance.configure({}) # Results in empty self.keywords
    caplog.clear() # Clear logs from configure warning

    # Act & Assert Logging: Filter the papers and check logs
    with caplog.at_level(logging.INFO):
        filtered_papers = keyword_filter_instance.filter(sample_papers)

    # Assert: All original papers should be returned
    assert len(filtered_papers) == len(sample_papers)
    # Assert: Check for the specific INFO log message
    assert "KeywordFilter has no keywords configured" in caplog.text
    assert "passing all papers through." in caplog.text
    # Assert: Ensure matched_keywords is None as the filter was bypassed
    for paper in filtered_papers:
        assert paper.matched_keywords is None

def test_filter_empty_paper_list(keyword_filter_instance: KeywordFilter):
    """Tests that filtering an empty list of papers returns an empty list."""
    # Arrange: Configure with some keywords (doesn't matter which for this test)
    config = {'paper_source': {'arxiv': {'keywords': ['test']}}}
    keyword_filter_instance.configure(config)
    # Act: Filter an empty list
    filtered_papers = keyword_filter_instance.filter([])
    # Assert: The result should be an empty list
    assert len(filtered_papers) == 0
