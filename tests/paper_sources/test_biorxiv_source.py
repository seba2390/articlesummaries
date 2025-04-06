"""Tests for the BiorxivSource paper fetching implementation."""

import pytest
import requests
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.paper import Paper
from src.paper_sources.biorxiv_source import BiorxivSource

# Sample API response structure for mocking
SAMPLE_API_RESPONSE_PAGE_1 = {
    "messages": [{
        "status": "ok",
        "count": 2,
        "total": 2,
        "cursor": 0
    }],
    "collection": [
        {
            "doi": "10.1101/2024.01.01.123456",
            "title": "Test Paper 1",
            "authors": "Author One; Author Two",
            "author_corresponding": "Author One",
            "author_corresponding_institution": "Test University",
            "date": "2024-01-15",
            "version": "1",
            "type": "New Results",
            "license": "cc_by",
            "category": "Bioinformatics",
            "jats_xml": "/lookup/xml/123456.xml",
            "abstract": "This is the abstract for test paper 1.",
            "published": "NA",
            "server": "biorxiv"
        },
        {
            "doi": "10.1101/2024.01.02.789012",
            "title": "Test Paper 2",
            "authors": "Author Three",
            "author_corresponding": "Author Three",
            "author_corresponding_institution": "Another University",
            "date": "2024-01-16",
            "version": "2",
            "type": "New Results",
            "license": "cc_by_nc_nd",
            "category": "Genomics",
            "jats_xml": "/lookup/xml/789012.xml",
            "abstract": "Abstract for test paper 2, a newer version.",
            "published": "NA",
            "server": "biorxiv"
        }
    ]
}

SAMPLE_API_RESPONSE_EMPTY = {
    "messages": [{
        "status": "ok",
        "count": 0,
        "total": 0,
        "cursor": 0
    }],
    "collection": []
}


@pytest.fixture
def biorxiv_source():
    """Provides a default BiorxivSource instance for testing."""
    return BiorxivSource()

@pytest.fixture
def sample_config():
    """Provides a sample configuration dictionary."""
    return {
        "paper_source": {
            "biorxiv": {
                "server": "biorxiv",
                "categories": ["bioinformatics", "genomics"],
                "fetch_window": 2 # Override global
            }
        },
        "global_fetch_window_days": 5
    }

# --- Test Configuration ---

def test_configure_defaults(biorxiv_source):
    """Test configuration with minimal settings, relying on defaults."""
    config = {
        "paper_source": {"biorxiv": {}}
    }
    biorxiv_source.configure(config)
    assert biorxiv_source.server == "biorxiv"
    assert biorxiv_source.categories == []
    # Should use BasePaperSource default initially, but configure sets it
    assert biorxiv_source.fetch_window_days == BiorxivSource.DEFAULT_FETCH_WINDOW_DAYS

def test_configure_specific_settings(biorxiv_source, sample_config):
    """Test configuration with specific server, categories, and source fetch window."""
    biorxiv_source.configure(sample_config)
    assert biorxiv_source.server == "biorxiv"
    assert biorxiv_source.categories == ["bioinformatics", "genomics"]
    assert biorxiv_source.fetch_window_days == 2 # Source specific override

def test_configure_global_fetch_window(biorxiv_source):
    """Test configuration uses global fetch window when source-specific is missing."""
    config = {
        "paper_source": {
            "biorxiv": {
                "server": "medrxiv",
                "categories": []
            }
        },
        "global_fetch_window_days": 3
    }
    biorxiv_source.configure(config)
    assert biorxiv_source.server == "medrxiv"
    assert biorxiv_source.fetch_window_days == 3

def test_configure_invalid_server(biorxiv_source, sample_config, caplog):
    """Test configuration falls back to default server if invalid one is provided."""
    sample_config["paper_source"]["biorxiv"]["server"] = "invalid_server"
    biorxiv_source.configure(sample_config)
    assert biorxiv_source.server == "biorxiv" # Should default back
    assert "Invalid server 'invalid_server'" in caplog.text

def test_configure_invalid_fetch_window(biorxiv_source, caplog):
    """Test configuration uses default fetch window if invalid ones are provided."""
    config = {
        "paper_source": {
            "biorxiv": {
                "fetch_window": "invalid"
            }
        },
        "global_fetch_window_days": "also_invalid"
    }
    biorxiv_source.configure(config)
    assert biorxiv_source.fetch_window_days == BiorxivSource.DEFAULT_FETCH_WINDOW_DAYS
    assert "fetch_window (invalid) for biorxiv is invalid" in caplog.text
    assert "Global fetch_window (also_invalid) is invalid" in caplog.text

# --- Test Fetching ---

@patch('src.paper_sources.biorxiv_source.requests.get')
def test_fetch_papers_success(mock_get, biorxiv_source, sample_config):
    """Test successful fetching and parsing of papers."""
    # Configure the mock response
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE_PAGE_1
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Configure the source
    biorxiv_source.configure(sample_config)

    # Define time window
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=biorxiv_source.fetch_window_days)

    # Perform the fetch
    papers = biorxiv_source.fetch_papers(start_time, end_time)

    # Assertions
    assert len(papers) == 2
    assert isinstance(papers[0], Paper)
    assert papers[0].id == "10.1101/2024.01.01.123456"
    assert papers[0].title == "Test Paper 1"
    assert papers[0].authors == ["Author One", "Author Two"]
    assert papers[0].abstract == "This is the abstract for test paper 1."
    assert papers[0].url == "https://www.biorxiv.org/content/10.1101/2024.01.01.123456"
    assert papers[0].published_date == datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)
    assert papers[0].source == "biorxiv"
    assert papers[0].categories == ["Bioinformatics"]

    assert papers[1].id == "10.1101/2024.01.02.789012"
    assert papers[1].published_date == datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)

    # Check API call arguments
    expected_url = f"https://api.biorxiv.org/details/biorxiv/{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}/0/json"
    expected_params = {'category': 'bioinformatics;genomics'}
    mock_get.assert_called_once_with(expected_url, params=expected_params, timeout=30)

@patch('src.paper_sources.biorxiv_source.requests.get')
def test_fetch_papers_empty_response(mock_get, biorxiv_source, sample_config):
    """Test fetching when the API returns no papers."""
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE_EMPTY
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    biorxiv_source.configure(sample_config)
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=biorxiv_source.fetch_window_days)

    papers = biorxiv_source.fetch_papers(start_time, end_time)

    assert len(papers) == 0
    mock_get.assert_called_once() # Ensure API was called

@patch('src.paper_sources.biorxiv_source.requests.get')
def test_fetch_papers_api_error(mock_get, biorxiv_source, sample_config, caplog):
    """Test fetching when the API call raises an exception."""
    # Configure the mock to raise an exception
    mock_get.side_effect = requests.exceptions.RequestException("Connection Error")

    biorxiv_source.configure(sample_config)
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=biorxiv_source.fetch_window_days)

    papers = biorxiv_source.fetch_papers(start_time, end_time)

    assert len(papers) == 0
    assert "API request failed" in caplog.text
    assert "Connection Error" in caplog.text

@patch('src.paper_sources.biorxiv_source.requests.get')
def test_fetch_papers_pagination(mock_get, biorxiv_source, sample_config):
    """Test fetching handles pagination correctly (mocking multiple pages)."""
    # Simulate two pages of results
    page1_doi = "10.1101/page1"
    page2_doi = "10.1101/page2"

    # Define mock responses
    response_page1_data = {
        "messages": [{"status": "ok", "count": 1, "total": 2, "cursor": 0}],
        "collection": [
            {"doi": page1_doi, "date": "2024-01-15", "title": "Page 1 Paper", "authors": "Auth1", "abstract": "Abs1", "category": "Cat1"}
        ]
    }
    response_page2_data = {
        "messages": [{"status": "ok", "count": 1, "total": 2, "cursor": 1}], # Cursor advanced
        "collection": [
            {"doi": page2_doi, "date": "2024-01-16", "title": "Page 2 Paper", "authors": "Auth2", "abstract": "Abs2", "category": "Cat2"}
        ]
    }
    # Mock responses needed for the API calls
    mock_response1 = MagicMock()
    mock_response1.json.return_value = response_page1_data
    mock_response1.raise_for_status.return_value = None

    mock_response2 = MagicMock()
    mock_response2.json.return_value = response_page2_data
    mock_response2.raise_for_status.return_value = None

    # Set the side effect for the mock_get
    mock_get.side_effect = [mock_response1, mock_response2]

    # Configure the source *before* overriding MAX_RESULTS_PER_PAGE
    biorxiv_source.configure(sample_config)

    # Critical Fix: Set MAX_RESULTS_PER_PAGE = 1 for this test
    # This forces the loop to continue based on total vs processed count,
    # rather than breaking because count_in_page < MAX_RESULTS_PER_PAGE.
    original_max_results = biorxiv_source.MAX_RESULTS_PER_PAGE
    biorxiv_source.MAX_RESULTS_PER_PAGE = 1
    print(f"Temporarily setting MAX_RESULTS_PER_PAGE to {biorxiv_source.MAX_RESULTS_PER_PAGE}")

    # Define time window
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=biorxiv_source.fetch_window_days)

    # Perform the fetch
    papers = []
    try:
        papers = biorxiv_source.fetch_papers(start_time, end_time)
    finally:
        # Restore original value
        biorxiv_source.MAX_RESULTS_PER_PAGE = original_max_results
        print(f"Restored MAX_RESULTS_PER_PAGE to {biorxiv_source.MAX_RESULTS_PER_PAGE}")


    # Verify results
    print(f"PAPERS RETURNED: {len(papers)}") # Add print for debugging
    assert len(papers) == 2, f"Expected 2 papers, but got {len(papers)}"
    assert papers[0].id == page1_doi
    assert papers[1].id == page2_doi
    assert mock_get.call_count == 2

    # Check URLs called
    call_args_list = mock_get.call_args_list
    assert "/0/json" in call_args_list[0].args[0] # First call: cursor 0
    assert "/1/json" in call_args_list[1].args[0] # Second call: cursor 1 (0 + count=1)
