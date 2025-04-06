import pytest
from unittest.mock import patch, MagicMock, ANY, call
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
import logging

# Need arxiv library itself for the Enum members
import arxiv

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
                'categories': ['cs.AI', 'cs.LG'], # Sample categories
                # fetch_window defaults to 1 day in the source class
            }
        },
        'max_total_results': 10 # Sample fetch limit
    }

@pytest.fixture
def arxiv_source_instance() -> ArxivSource:
    """Provides a clean instance of ArxivSource for each test."""
    return ArxivSource()

# Define a fixed time for mocking datetime.now()
MOCK_NOW_UTC = datetime(2025, 4, 6, 13, 15, 47, tzinfo=timezone.utc)

# --- Test Cases ---

def test_arxiv_source_configure(arxiv_source_instance: ArxivSource, valid_config: dict):
    """Tests that ArxivSource configures its attributes correctly from the config dict."""
    # Act
    arxiv_source_instance.configure(valid_config)
    # Assert
    assert arxiv_source_instance.categories == ['cs.AI', 'cs.LG']
    assert arxiv_source_instance.max_total_results == 10
    # Check fetch_window_days uses default if not present
    assert arxiv_source_instance.fetch_window_days == ArxivSource.DEFAULT_FETCH_WINDOW_DAYS

def test_arxiv_source_configure_with_fetch_window(arxiv_source_instance: ArxivSource):
    """Tests configuring fetch_window_days explicitly."""
    config = {
        'paper_source': {'arxiv': {'categories': ['cs.AI'], 'fetch_window': 3}},
        'max_total_results': 5
    }
    arxiv_source_instance.configure(config)
    assert arxiv_source_instance.fetch_window_days == 3
    assert arxiv_source_instance.max_total_results == 5

def test_arxiv_source_configure_invalid_fetch_window(arxiv_source_instance: ArxivSource, caplog):
    """Tests configuring with invalid fetch_window uses default."""
    config_neg = { 'paper_source': {'arxiv': {'fetch_window': -1}}}
    config_str = { 'paper_source': {'arxiv': {'fetch_window': 'abc'}}}
    config_zero = { 'paper_source': {'arxiv': {'fetch_window': 0}}}

    with caplog.at_level(logging.WARNING):
        arxiv_source_instance.configure(config_neg)
        assert arxiv_source_instance.fetch_window_days == ArxivSource.DEFAULT_FETCH_WINDOW_DAYS
        assert "is not a positive integer" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        arxiv_source_instance.configure(config_str)
        assert arxiv_source_instance.fetch_window_days == ArxivSource.DEFAULT_FETCH_WINDOW_DAYS
        assert "is not a valid integer" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        arxiv_source_instance.configure(config_zero)
        assert arxiv_source_instance.fetch_window_days == ArxivSource.DEFAULT_FETCH_WINDOW_DAYS
        assert "is not a positive integer" in caplog.text

def test_arxiv_source_configure_defaults(arxiv_source_instance: ArxivSource):
    """Tests that ArxivSource uses default values when keys are missing from config."""
    # Act
    arxiv_source_instance.configure({}) # Pass empty config
    # Assert
    assert arxiv_source_instance.categories == [] # Default empty list
    # Check against the class default attribute
    assert arxiv_source_instance.max_total_results == ArxivSource.DEFAULT_MAX_RESULTS
    assert arxiv_source_instance.fetch_window_days == ArxivSource.DEFAULT_FETCH_WINDOW_DAYS

# Patch datetime.now within the module where it's called
@patch('src.paper_sources.arxiv_source.datetime')
@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_success(
    mock_arxiv_search: MagicMock,
    mock_datetime: MagicMock,
    arxiv_source_instance: ArxivSource,
    valid_config: dict
):
    """Tests the happy path for fetching papers with the new logic.

    Verifies:
    - Correct API query construction (categories and dynamic date range).
    - Correct call to `arxiv.Search` including sorting parameters.
    - Processing of results (conversion to Paper objects).
    - Deduplication based on versioned ID.
    """
    # Arrange: Mock datetime.now() to return our fixed time
    mock_datetime.now.return_value = MOCK_NOW_UTC
    # Ensure timedelta and timezone are still accessible
    mock_datetime.timedelta = timedelta
    mock_datetime.timezone = timezone

    # Arrange: Configure the instance (fetch_window defaults to 1 day)
    arxiv_source_instance.configure(valid_config)
    assert arxiv_source_instance.fetch_window_days == 1 # Verify default

    # Arrange: Calculate expected date range based on MOCK_NOW_UTC and fetch_window=1
    expected_end_dt_utc = MOCK_NOW_UTC
    expected_start_dt_utc = MOCK_NOW_UTC - timedelta(days=1)

    # Arrange: Create mock arXiv results - adjust 'updated' times relative to MOCK_NOW_UTC
    # Paper 1 (v1): Updated within the last day
    mock_paper_in_window1_v1 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v1', title='Window Paper 1 v1', summary='Abstract 1',
            authors=['Auth A'], published=MOCK_NOW_UTC - timedelta(days=2),
            updated=MOCK_NOW_UTC - timedelta(hours=12), # In range
            primary_category='cs.AI', categories=['cs.AI']
        )
    # Paper 2: Updated within the last day
    mock_paper_in_window2 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0002v1', title='Window Paper 2', summary='Abstract 2',
            authors=['Auth B'], published=MOCK_NOW_UTC - timedelta(days=3),
            updated=MOCK_NOW_UTC - timedelta(hours=1), # In range
            primary_category='cs.LG', categories=['cs.LG']
        )
    # Paper 1 (v2): Also updated within the last day (should be kept as ID is unique)
    mock_paper_in_window1_v2 = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0001v2', title='Window Paper 1 v2', summary='Abstract 1 updated',
            authors=['Auth A'], published=MOCK_NOW_UTC - timedelta(days=2),
            updated=MOCK_NOW_UTC - timedelta(minutes=30), # In range
            primary_category='cs.AI', categories=['cs.AI']
        )
    # Paper 3: Updated just outside the 1-day window (should be excluded by API query)
    mock_paper_outside_window = MockArxivResult(
            entry_id='http://arxiv.org/abs/2401.0003v1', title='Outside Window Paper', summary='Abstract 3',
            authors=['Auth C'], published=MOCK_NOW_UTC - timedelta(days=3),
            updated=MOCK_NOW_UTC - timedelta(days=1, minutes=1), # Just outside range
            primary_category='cs.AI', categories=['cs.AI']
        )

    # Simulate the API search returning only papers matching the date query
    mock_results_data_from_api = [
        mock_paper_in_window1_v1,
        mock_paper_in_window2,
        mock_paper_in_window1_v2,
        # Note: mock_paper_outside_window is *not* included here
    ]
    # Configure the mock `arxiv.Search` instance
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data_from_api)
    mock_arxiv_search.return_value = mock_search_instance # `arxiv.Search(...)` will return this mock

    # Act: Call the method under test, passing the calculated times
    papers = arxiv_source_instance.fetch_papers(start_time_utc=expected_start_dt_utc, end_time_utc=expected_end_dt_utc)

    # Assert: Check API query construction
    start_str = expected_start_dt_utc.strftime("%Y%m%d%H%M%S")
    end_str = expected_end_dt_utc.strftime("%Y%m%d%H%M%S")
    date_query = f"lastUpdatedDate:[{start_str} TO {end_str}]"
    category_query = "(cat:cs.AI OR cat:cs.LG)" # Based on valid_config
    expected_query = f"{category_query} AND {date_query}"

    # Assert that `arxiv.Search` was called once with the correct arguments, including sorting
    mock_arxiv_search.assert_called_once_with(
        query=expected_query,
        max_results=10, # From valid_config
        sort_by=arxiv.SortCriterion.LastUpdatedDate, # Check sorting
        sort_order=arxiv.SortOrder.Descending # Check sorting order
    )

    # Assert: Check the final list of Paper objects
    # Should contain the 3 unique papers updated within the window
    assert len(papers) == 3
    assert all(isinstance(p, Paper) for p in papers)
    # Check IDs (including versions) - order might vary depending on API result order
    paper_ids = {p.id for p in papers}
    assert paper_ids == {'2401.0001v1', '2401.0002v1', '2401.0001v2'}

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

    # Act: Call method under test with dummy times (as it should error out before using them)
    # We still need to provide them to match the signature.
    dummy_start = MOCK_NOW_UTC - timedelta(days=1)
    dummy_end = MOCK_NOW_UTC
    papers = arxiv_source_instance.fetch_papers(start_time_utc=dummy_start, end_time_utc=dummy_end)

    # Assert
    assert papers == [] # Should return empty list on error
    mock_arxiv_search.assert_called_once() # Ensure the call was attempted

# Patch datetime.now within the module where it's called
@patch('src.paper_sources.arxiv_source.datetime')
@patch('src.paper_sources.arxiv_source.arxiv.Search')
def test_fetch_papers_max_results_warning(
    mock_arxiv_search: MagicMock,
    mock_datetime: MagicMock,
    arxiv_source_instance: ArxivSource,
    caplog: pytest.LogCaptureFixture # Use caplog fixture
):
    """Tests that a warning is logged if the number of fetched results meets the configured limit, matching new format.

    Simulates the API returning exactly `max_total_results` papers.
    """
     # Arrange: Mock datetime.now()
    mock_datetime.now.return_value = MOCK_NOW_UTC
    mock_datetime.timedelta = timedelta
    mock_datetime.timezone = timezone

    # Arrange: Configure with a low max_results limit and specific fetch_window
    config = {
        'paper_source': {'arxiv': {'categories': ['cs.AI'], 'fetch_window': 2}}, # Use window=2 days
        'max_total_results': 2 # Low limit for testing
    }
    arxiv_source_instance.configure(config)
    assert arxiv_source_instance.fetch_window_days == 2

    # Arrange: Calculate expected date range based on mocked now and fetch_window=2
    expected_end_dt_utc = MOCK_NOW_UTC
    expected_start_dt_utc = MOCK_NOW_UTC - timedelta(days=2)

    # Arrange: Mock data (updated within the 2-day window)
    mock_results_data = [
        MockArxivResult('id1v1', 'T1', 'A1', [], MOCK_NOW_UTC - timedelta(days=3), MOCK_NOW_UTC - timedelta(hours=1), 'cs.AI', ['cs.AI']),
        MockArxivResult('id2v1', 'T2', 'A2', [], MOCK_NOW_UTC - timedelta(days=3), MOCK_NOW_UTC - timedelta(hours=10), 'cs.AI', ['cs.AI']),
        # Imagine more papers exist but API stops at 2
    ]
    # Configure mock search instance to return exactly the max number of results
    mock_search_instance = MagicMock()
    mock_search_instance.results.return_value = iter(mock_results_data)
    mock_arxiv_search.return_value = mock_search_instance

    # Act: Fetch papers and capture logs at WARNING level
    with caplog.at_level(logging.WARNING):
        # Pass the calculated times
        papers = arxiv_source_instance.fetch_papers(start_time_utc=expected_start_dt_utc, end_time_utc=expected_end_dt_utc)

    # Assert: Check returned papers
    assert len(papers) == 2

    # Assert: Check that the specific warning message was logged with the new format
    start_str_formatted = expected_start_dt_utc.strftime('%Y-%m-%d %H:%M:%S')
    end_str_formatted = expected_end_dt_utc.strftime('%Y-%m-%d %H:%M:%S')
    expected_warning = (
        f"Reached or exceeded the fetch limit (2). "
        f"Some papers updated between {start_str_formatted} and "
        f"{end_str_formatted} might have been missed."
    )
    # Check if the expected warning string is present in any of the log records
    found_warning = False
    for record in caplog.records:
        if record.levelname == "WARNING" and expected_warning in record.getMessage():
            found_warning = True
            break
    assert found_warning, f"Expected warning not found in logs. Logs:\\n{caplog.text}"

def test_fetch_papers_no_categories(arxiv_source_instance: ArxivSource):
    """Tests that fetching returns an empty list if no categories are configured."""
    # Arrange: Configure with empty categories list
    config = {
        'paper_source': {'arxiv': {'categories': []}},
        'max_total_results': 10
    }
    arxiv_source_instance.configure(config)

    # Act: Call method under test with dummy times (as it should exit early)
    dummy_start = MOCK_NOW_UTC - timedelta(days=1)
    dummy_end = MOCK_NOW_UTC
    papers = arxiv_source_instance.fetch_papers(start_time_utc=dummy_start, end_time_utc=dummy_end)

    # Assert
    assert papers == []
