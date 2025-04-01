import pytest
from unittest.mock import patch, MagicMock, ANY, call
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
import logging

from src.paper_sources.arxiv_source import ArxivSource
from src.paper import Paper

# Mock arxiv.Result class structure needed for tests
class MockArxivResult:
    """Minimal mock of the `arxiv.Result` class needed for these tests.

    Provides necessary attributes and the `get_short_id` method.
    """
    def __init__(self, entry_id, title, summary, authors, published, updated, primary_category, categories=None):
        """Initializes the mock result with relevant paper data."""
        self.entry_id = entry_id # Full URL like http://arxiv.org/abs/2401.0001v1
        self.title = title
        self.summary = summary # Corresponds to Paper.abstract
        self.authors = authors # Stored as list of strings for simplicity
        self.published = published # datetime object
        self.updated = updated # datetime object (used as Paper.published_date)
        self.primary_category = primary_category
        self.categories = categories if categories is not None else [] # List of strings

    def get_short_id(self) -> str:
        """Mimics `arxiv.Result.get_short_id()` returning ID with version."""
        # Extracts ID like '2401.0001v1' from entry_id URL
        return self.entry_id.split('/abs/')[-1]

# --- Test Fixtures ---
@pytest.fixture
def valid_config() -> dict:
    """Provides a sample valid configuration dictionary for ArxivSource tests."""
    return {
        'paper_source': {
            'arxiv': {
                'categories': ['cs.AI', 'cs.LG'] # Sample categories
            }
            # `keywords` would be here but not used by ArxivSource itself
        },
        'max_total_results': 10 # Sample fetch limit
    }

@pytest.fixture
def arxiv_source_instance() -> ArxivSource:
    """Provides a clean instance of ArxivSource for each test."""
    return ArxivSource()

# --- Test Cases ---

def test_arxiv_source_configure(arxiv_source_instance: ArxivSource, valid_config: dict):
    """Tests that ArxivSource configures its attributes correctly from the config dict."""
    # Act
    arxiv_source_instance.configure(valid_config)
    # Assert
    assert arxiv_source_instance.categories == ['cs.AI', 'cs.LG']
    assert arxiv_source_instance.max_total_results == 10

def test_arxiv_source_configure_defaults(arxiv_source_instance: ArxivSource):
    """Tests that ArxivSource uses default values when keys are missing from config."""
    # Act
    arxiv_source_instance.configure({}) # Pass empty config
    # Assert
    assert arxiv_source_instance.categories == [] # Default empty list
    # Check against the class default attribute
    assert arxiv_source_instance.max_total_results == ArxivSource.DEFAULT_MAX_RESULTS

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_success(
    mock_arxiv_search: MagicMock,
    arxiv_source_instance: ArxivSource,
    valid_config: dict
):
    """Tests the happy path for fetching papers.

    Verifies:
    - Correct API query construction (categories and date range).
    - Correct call to `arxiv.Search`.
    - Processing of results (conversion to Paper objects).
    - Deduplication based on versioned ID.
    - Filtering based on the `lastUpdatedDate` range.
    """
    # Arrange: Configure the instance
    arxiv_source_instance.configure(valid_config)

    # Arrange: Define mock date range (yesterday UTC)
    today_utc_date = datetime.now(timezone.utc).date()
    yesterday_utc_date = today_utc_date - timedelta(days=1)
    yesterday_start_utc = datetime.combine(yesterday_utc_date, dt_time.min, tzinfo=timezone.utc)
    yesterday_end_utc = datetime.combine(yesterday_utc_date, dt_time.max, tzinfo=timezone.utc)

    # Arrange: Create mock arXiv results
    # Paper 1 (v1): Updated yesterday
    mock_paper_yesterday1_v1 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v1', title='Yesterday Paper 1', summary='Abstract 1',
            authors=['Auth A'], published=yesterday_start_utc - timedelta(days=1),
            updated=yesterday_start_utc + timedelta(hours=1), # In range
            primary_category='cs.AI', categories=['cs.AI']
        )
    # Paper 2: Updated yesterday
    mock_paper_yesterday2 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0002v1', title='Yesterday Paper 2', summary='Abstract 2',
            authors=['Auth B'], published=yesterday_start_utc - timedelta(days=2),
            updated=yesterday_end_utc - timedelta(hours=1), # In range
            primary_category='cs.LG', categories=['cs.LG']
        )
    # Paper 1 (v2): Also updated yesterday (should be kept as ID is unique)
    mock_paper_yesterday1_v2 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v2', title='Yesterday Paper 1 v2', summary='Abstract 1 updated',
            authors=['Auth A'], published=yesterday_start_utc - timedelta(days=1),
            updated=yesterday_start_utc + timedelta(minutes=30), # In range
            primary_category='cs.AI', categories=['cs.AI']
        )
    # Paper 3: Updated today (should be excluded by the conceptual API query)
    mock_paper_today = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0003v1', title='Today Paper', summary='Abstract 3',
            authors=['Auth C'], published=yesterday_start_utc - timedelta(days=1),
            updated=datetime.now(timezone.utc), # Outside range
            primary_category='cs.AI', categories=['cs.AI']
        )

    # Simulate the API search returning only papers matching the date query
    mock_results_data_from_api = [
        mock_paper_yesterday1_v1,
        mock_paper_yesterday2,
        mock_paper_yesterday1_v2,
        # Note: mock_paper_today is *not* included here
    ]
    # Configure the mock `arxiv.Search` instance
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data_from_api)
    mock_arxiv_search.return_value = mock_search_instance # `arxiv.Search(...)` will return this mock

    # Act: Call the method under test
    papers = arxiv_source_instance.fetch_papers()

    # Assert: Check API query construction
    start_str = yesterday_start_utc.strftime("%Y%m%d%H%M%S")
    end_str = yesterday_end_utc.strftime("%Y%m%d%H%M%S")
    date_query = f"lastUpdatedDate:[{start_str} TO {end_str}]"
    category_query = "(cat:cs.AI OR cat:cs.LG)" # Based on valid_config
    expected_query = f"{category_query} AND {date_query}"

    # Assert that `arxiv.Search` was called once with the correct arguments
    mock_arxiv_search.assert_called_once_with(
        query=expected_query,
        max_results=10, # From valid_config
        # No sort_by argument is expected as date filtering is done via query
    )

    # Assert: Check the final list of Paper objects
    # Should contain the 3 unique papers updated yesterday
    assert len(papers) == 3
    assert all(isinstance(p, Paper) for p in papers)
    # Check IDs (including versions) - order might vary depending on API result order
    paper_ids = {p.id for p in papers}
    assert paper_ids == {'2401.0001v1', '2401.0002v1', '2401.0001v2'}
    # Optional: Check specific fields of converted Paper objects if needed
    # paper_map = {p.id: p for p in papers}
    # assert paper_map['2401.0001v1'].title == 'Yesterday Paper 1'
    # assert paper_map['2401.0001v1'].source == 'arxiv'

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_api_error(
    mock_arxiv_search: MagicMock,
    arxiv_source_instance: ArxivSource,
    valid_config: dict
):
    """Tests handling of an exception during the `arxiv.Search` call.

    Verifies that an empty list is returned and the error is logged (implicitly).
    """
    # Arrange
    arxiv_source_instance.configure(valid_config)
    # Simulate error during API interaction
    mock_arxiv_search.side_effect = Exception("ArXiv API is down")

    # Act
    papers = arxiv_source_instance.fetch_papers()

    # Assert
    assert papers == [] # Should return empty list on error
    mock_arxiv_search.assert_called_once() # Ensure the call was attempted

@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_max_results_warning(
    mock_arxiv_search: MagicMock,
    arxiv_source_instance: ArxivSource,
    caplog: pytest.LogCaptureFixture # Use caplog fixture
):
    """Tests that a warning is logged if the number of fetched results meets the configured limit.

    Simulates the API returning exactly `max_total_results` papers.
    """
    # Arrange: Configure with a low max_results limit
    config = {
        'paper_source': {'arxiv': {'categories': ['cs.AI']}},
        'max_total_results': 2 # Low limit for testing
    }
    arxiv_source_instance.configure(config)

    # Arrange: Mock data (updated yesterday to pass date filter)
    yesterday_utc_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    yesterday_start_utc = datetime.combine(yesterday_utc_date, dt_time.min, tzinfo=timezone.utc)
    mock_results_data = [
        MockArxivResult('id1v1', 'T1', 'A1', [], yesterday_start_utc, yesterday_start_utc + timedelta(hours=1), 'cs.AI', ['cs.AI']),
        MockArxivResult('id2v1', 'T2', 'A2', [], yesterday_start_utc, yesterday_start_utc + timedelta(hours=2), 'cs.AI', ['cs.AI']),
        # Imagine more papers exist but API stops at 2
    ]
    # Configure mock search instance to return exactly the max number of results
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data)
    mock_arxiv_search.return_value = mock_search_instance

    # Act: Fetch papers and capture logs at WARNING level
    with caplog.at_level(logging.WARNING):
        papers = arxiv_source_instance.fetch_papers()

    # Assert: Check returned papers
    assert len(papers) == 2

    # Assert: Check that the specific warning message was logged
    expected_warning = (
        f"Reached or exceeded the fetch limit (2). "
        f"Some papers updated on {yesterday_utc_date.strftime('%Y-%m-%d')} might have been missed."
    )
    assert expected_warning in caplog.text

def test_fetch_papers_no_categories(arxiv_source_instance: ArxivSource):
    """Tests that fetching returns an empty list if no categories are configured."""
    # Arrange: Configure with empty categories list
    config = {
        'paper_source': {'arxiv': {'categories': []}},
        'max_total_results': 10
    }
    arxiv_source_instance.configure(config)

    # Act
    papers = arxiv_source_instance.fetch_papers()

    # Assert
    assert papers == []
