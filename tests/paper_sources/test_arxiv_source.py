import pytest
from unittest.mock import patch, MagicMock, ANY
from datetime import datetime, timedelta, timezone
import arxiv
import logging

from src.paper_sources.arxiv_source import ArxivSource
from src.paper import Paper

# Mock arxiv.Result class structure needed for tests
class MockArxivResult:
    def __init__(self, entry_id, title, summary, authors, published, updated, primary_category):
        self.entry_id = entry_id
        self.title = title
        self.summary = summary
        self.authors = authors # Should be list of Author objects, simplified here
        self.published = published # datetime object
        self.updated = updated # datetime object
        self.primary_category = primary_category

    def get_short_id(self):
        # Extract ID like '1234.5678v1' from entry_id like 'http://arxiv.org/abs/1234.5678v1'
        return self.entry_id.split('/')[-1]

# --- Test Fixtures ---
@pytest.fixture
def valid_config():
    return {
        'categories': ['cs.AI', 'cs.LG'],
        'max_total_results': 10,
    }

@pytest.fixture
def arxiv_source_instance():
    return ArxivSource()

# --- Test Cases ---

def test_arxiv_source_configure(arxiv_source_instance, valid_config):
    """Test that ArxivSource configures correctly."""
    arxiv_source_instance.configure(valid_config)
    assert arxiv_source_instance.categories == ['cs.AI', 'cs.LG']
    assert arxiv_source_instance.max_total_results == 10

def test_arxiv_source_configure_defaults(arxiv_source_instance):
    """Test configuration with missing keys uses defaults."""
    arxiv_source_instance.configure({})
    assert arxiv_source_instance.categories == []
    assert arxiv_source_instance.max_total_results == 500 # Default value

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_success(mock_arxiv_search, arxiv_source_instance, valid_config):
    """Test successful fetching and filtering of papers."""
    arxiv_source_instance.configure(valid_config)

    # Prepare mock results
    now_utc = datetime.now(timezone.utc)
    mock_results_data = [
        # Paper updated today
        MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v1', title='Today Paper 1', summary='Abstract 1',
            authors=['Auth A'], published=now_utc - timedelta(days=1), updated=now_utc - timedelta(hours=1),
            primary_category='cs.AI'
        ),
        # Paper updated yesterday (should be included)
        MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0002v1', title='Today Paper 2', summary='Abstract 2',
            authors=['Auth B'], published=now_utc - timedelta(days=2), updated=now_utc - timedelta(hours=23),
            primary_category='cs.LG'
        ),
         # Paper updated two days ago (should be filtered out)
        MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0003v1', title='Old Paper', summary='Abstract 3',
            authors=['Auth C'], published=now_utc - timedelta(days=3), updated=now_utc - timedelta(days=2),
            primary_category='cs.AI'
        ),
        # Duplicate ID, updated today (should only appear once)
         MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v2', title='Today Paper 1 v2', summary='Abstract 1 updated',
            authors=['Auth A'], published=now_utc - timedelta(days=1), updated=now_utc - timedelta(minutes=30),
            primary_category='cs.AI'
        ),
    ]

    # Configure the mock Search object
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data) # Return results as an iterator
    mock_arxiv_search.return_value = mock_search_instance

    # --- Call the method under test ---
    papers = arxiv_source_instance.fetch_papers()

    # --- Assertions ---
    # Check that arxiv.Search was called correctly
    expected_query = "(cat:cs.AI OR cat:cs.LG)"
    mock_arxiv_search.assert_called_once_with(
        query=expected_query,
        max_results=10,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    # Check the returned papers (filtered by date and uniqueness)
    assert len(papers) == 3
    assert isinstance(papers[0], Paper)
    assert papers[0].id == '2401.0001v1' # First encountered
    assert papers[0].title == 'Today Paper 1'
    assert papers[1].id == '2401.0002v1'
    assert papers[1].title == 'Today Paper 2'
    assert papers[2].id == '2401.0001v2' # Second version also included

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_api_error(mock_arxiv_search, arxiv_source_instance, valid_config):
    """Test handling of an error during the arxiv API call."""
    arxiv_source_instance.configure(valid_config)

    # Configure mock Search to raise an exception
    mock_arxiv_search.side_effect = Exception("ArXiv API is down")

    papers = arxiv_source_instance.fetch_papers()

    assert papers == [] # Should return an empty list on error
    mock_arxiv_search.assert_called_once() # Ensure it was at least called

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_max_results_warning(mock_arxiv_search, arxiv_source_instance, caplog):
    """Test that a warning is logged if max_total_results is reached."""
    config = {'categories': ['cs.AI'], 'max_total_results': 2}
    arxiv_source_instance.configure(config)

    now_utc = datetime.now(timezone.utc)
    mock_results_data = [
        MockArxivResult('id1', 'T1', 'A1', [], now_utc, now_utc, 'cs.AI'),
        MockArxivResult('id2', 'T2', 'A2', [], now_utc, now_utc, 'cs.AI'),
        # This third one would exceed max_results if fetched, simulating the API limit
    ]

    # Simulate the API returning exactly max_results
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data[:2]) # API returns only 2
    mock_arxiv_search.return_value = mock_search_instance

    with caplog.at_level(logging.WARNING):
        papers = arxiv_source_instance.fetch_papers()

    # Check papers returned (date filter passes)
    assert len(papers) == 2

    # Check that the warning was logged because fetched == max_total_results
    assert "Reached the maximum limit (2). There might be more papers submitted today." in caplog.text

def test_fetch_papers_no_categories(arxiv_source_instance):
    """Test fetching papers when no categories are configured."""
    arxiv_source_instance.configure({'categories': [], 'max_total_results': 10})
    papers = arxiv_source_instance.fetch_papers()
    assert papers == []
