"""Tests for the MedrxivSource paper fetching implementation."""

import pytest
import requests
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.paper import Paper
from src.paper_sources.medrxiv_source import MedrxivSource # Import the new source

# Sample API response structure for mocking (similar to biorxiv, but use server="medrxiv")
SAMPLE_API_RESPONSE_PAGE_1 = {
    "messages": [{
        "status": "ok",
        "count": 2,
        "total": 2,
        "cursor": 0
    }],
    "collection": [
        {
            "doi": "10.1101/2024.01.01.654321", # Different DOI
            "title": "Med Test Paper 1",
            "authors": "Author Med One; Author Med Two",
            "author_corresponding": "Author Med One",
            "author_corresponding_institution": "Medical Test University",
            "date": "2024-01-15",
            "version": "1",
            "type": "New Results",
            "license": "cc_by",
            "category": "Epidemiology", # Medical category
            "jats_xml": "/lookup/xml/654321.xml",
            "abstract": "This is the abstract for med test paper 1.",
            "published": "NA",
            "server": "medrxiv" # Correct server
        },
        {
            "doi": "10.1101/2024.01.02.123987", # Different DOI
            "title": "Med Test Paper 2",
            "authors": "Author Med Three",
            "author_corresponding": "Author Med Three",
            "author_corresponding_institution": "Another Medical University",
            "date": "2024-01-16",
            "version": "2",
            "type": "New Results",
            "license": "cc_by_nc_nd",
            "category": "Infectious Diseases", # Medical category
            "jats_xml": "/lookup/xml/123987.xml",
            "abstract": "Abstract for med test paper 2, clinical focus.",
            "published": "NA",
            "server": "medrxiv" # Correct server
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
def medrxiv_source():
    """Provides a default MedrxivSource instance for testing."""
    return MedrxivSource()

@pytest.fixture
def sample_medrxiv_config():
    """Provides a sample configuration dictionary specific to medRxiv."""
    return {
        "paper_source": {
            "medrxiv": { # Use 'medrxiv' key
                "categories": ["Epidemiology", "Infectious Diseases"],
                "fetch_window": 3 # Override global
            }
        },
        "global_fetch_window_days": 5
    }

# --- Test Configuration ---

def test_configure_defaults(medrxiv_source):
    """Test configuration with minimal settings, relying on defaults."""
    config = {
        "paper_source": {"medrxiv": {}} # Use 'medrxiv' key
    }
    medrxiv_source.configure(config, 'medrxiv')
    assert medrxiv_source.SERVER_NAME == "medrxiv" # Verify hardcoded server
    assert medrxiv_source.categories == []
    assert medrxiv_source.fetch_window_days == MedrxivSource.DEFAULT_FETCH_WINDOW_DAYS

def test_configure_specific_settings(medrxiv_source, sample_medrxiv_config):
    """Test configuration with specific categories and source fetch window."""
    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')
    assert medrxiv_source.SERVER_NAME == "medrxiv"
    assert medrxiv_source.categories == ["Epidemiology", "Infectious Diseases"]
    assert medrxiv_source.fetch_window_days == 3 # Source specific override

def test_configure_global_fetch_window(medrxiv_source):
    """Test configuration uses global fetch window when source-specific is missing."""
    config = {
        "paper_source": {
            "medrxiv": { # Use 'medrxiv' key
                "categories": []
            }
        },
        "global_fetch_window_days": 4
    }
    medrxiv_source.configure(config, 'medrxiv')
    assert medrxiv_source.fetch_window_days == MedrxivSource.DEFAULT_FETCH_WINDOW_DAYS

def test_configure_invalid_categories(medrxiv_source, sample_medrxiv_config, caplog):
    """Test that invalid category format disables category filtering."""
    sample_medrxiv_config["paper_source"]["medrxiv"]["categories"] = "not_a_list"
    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')
    assert medrxiv_source.categories == [] # Should default to empty list
    assert "Invalid format for medRxiv categories: not_a_list" in caplog.text

def test_configure_invalid_fetch_window(medrxiv_source, caplog):
    """Test configuration uses default fetch window if invalid ones are provided."""
    config = {
        "paper_source": {
            "medrxiv": { # Use 'medrxiv' key
                "fetch_window": "invalid"
            }
        },
        "global_fetch_window_days": "also_invalid"
    }
    medrxiv_source.configure(config, 'medrxiv')
    assert medrxiv_source.fetch_window_days == MedrxivSource.DEFAULT_FETCH_WINDOW_DAYS
    assert "fetch_window (invalid) for medrxiv is invalid. Using default." in caplog.text
    assert "Global fetch_window" not in caplog.text

# --- Test Fetching ---

@patch('src.paper_sources.medrxiv_source.requests.get')
def test_fetch_papers_success(mock_get, medrxiv_source, sample_medrxiv_config):
    """Test successful fetching and parsing of papers."""
    # Configure the mock response
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE_PAGE_1
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    # Configure the source
    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')

    # Define time window
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=medrxiv_source.fetch_window_days)

    # Perform the fetch
    papers = medrxiv_source.fetch_papers(start_time, end_time)

    # Assertions
    assert len(papers) == 2
    assert isinstance(papers[0], Paper)
    assert papers[0].id == "10.1101/2024.01.01.654321"
    assert papers[0].title == "Med Test Paper 1"
    assert papers[0].authors == ["Author Med One", "Author Med Two"]
    assert papers[0].abstract == "This is the abstract for med test paper 1."
    assert papers[0].url == "https://www.medrxiv.org/content/10.1101/2024.01.01.654321"
    assert papers[0].published_date == datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc)
    assert papers[0].source == "medrxiv" # Check source name
    assert papers[0].categories == ["Epidemiology"]

    assert papers[1].id == "10.1101/2024.01.02.123987"
    assert papers[1].published_date == datetime(2024, 1, 16, 0, 0, tzinfo=timezone.utc)
    assert papers[1].source == "medrxiv"
    assert papers[1].categories == ["Infectious Diseases"]

    # Check API call arguments
    expected_url = f"https://api.biorxiv.org/details/medrxiv/{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}/0/json"
    # Categories should be joined with ';' and spaces replaced with '_'
    expected_params = {'category': 'Epidemiology;Infectious_Diseases'}
    mock_get.assert_called_once_with(expected_url, params=expected_params, timeout=30)

@patch('src.paper_sources.medrxiv_source.requests.get')
def test_fetch_papers_empty_response(mock_get, medrxiv_source, sample_medrxiv_config):
    """Test fetching when the API returns no papers."""
    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE_EMPTY
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=medrxiv_source.fetch_window_days)

    papers = medrxiv_source.fetch_papers(start_time, end_time)

    assert len(papers) == 0
    mock_get.assert_called_once() # Ensure API was called

@patch('src.paper_sources.medrxiv_source.requests.get')
def test_fetch_papers_api_error(mock_get, medrxiv_source, sample_medrxiv_config, caplog):
    """Test fetching when the API call raises an exception."""
    # Configure the mock to raise an exception
    mock_get.side_effect = requests.exceptions.RequestException("Connection Error")

    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')
    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=medrxiv_source.fetch_window_days)

    papers = medrxiv_source.fetch_papers(start_time, end_time)

    assert len(papers) == 0
    assert "API request failed for medrxiv" in caplog.text
    assert "Connection Error" in caplog.text

@patch('src.paper_sources.medrxiv_source.requests.get')
def test_fetch_papers_pagination(mock_get, medrxiv_source, sample_medrxiv_config):
    """Test fetching handles pagination correctly (mocking multiple pages)."""
    # Simulate two pages of results
    page1_doi = "10.1101/medpage1"
    page2_doi = "10.1101/medpage2"

    # Define mock responses for medrxiv
    response_page1_data = {
        "messages": [{"status": "ok", "count": 1, "total": 2, "cursor": 0}],
        "collection": [
            {"doi": page1_doi, "date": "2024-01-15", "title": "Med Page 1 Paper", "authors": "MedAuth1", "abstract": "Abs1", "category": "Cardiology", "server": "medrxiv"}
        ]
    }
    response_page2_data = {
        "messages": [{"status": "ok", "count": 1, "total": 2, "cursor": 1}], # Cursor advanced
        "collection": [
            {"doi": page2_doi, "date": "2024-01-16", "title": "Med Page 2 Paper", "authors": "MedAuth2", "abstract": "Abs2", "category": "Neurology", "server": "medrxiv"}
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

    # Configure the source *before* potentially overriding MAX_RESULTS_PER_PAGE if needed (not needed here)
    medrxiv_source.configure(sample_medrxiv_config, 'medrxiv')

    # Temporarily override MAX_RESULTS_PER_PAGE for this test to force pagination
    original_max_results = medrxiv_source.MAX_RESULTS_PER_PAGE
    medrxiv_source.MAX_RESULTS_PER_PAGE = 1
    try:
        # Define time window
        end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
        start_time = end_time - timedelta(days=medrxiv_source.fetch_window_days)

        # Perform the fetch
        papers = medrxiv_source.fetch_papers(start_time, end_time)
    finally:
        # Restore original value
        medrxiv_source.MAX_RESULTS_PER_PAGE = original_max_results

    # Assertions
    assert len(papers) == 2
    assert papers[0].id == page1_doi
    assert papers[0].source == "medrxiv"
    assert papers[1].id == page2_doi
    assert papers[1].source == "medrxiv"

    assert mock_get.call_count == 2
    # Check the first call
    call1_args, call1_kwargs = mock_get.call_args_list[0]
    assert f"/{medrxiv_source.SERVER_NAME}/{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}/0/json" in call1_args[0]
    # Check the second call (cursor should be 1 based on first response: cursor 0 + count 1)
    call2_args, call2_kwargs = mock_get.call_args_list[1]
    assert f"/{medrxiv_source.SERVER_NAME}/{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}/1/json" in call2_args[0]

@patch('src.paper_sources.medrxiv_source.requests.get')
def test_fetch_papers_no_categories(mock_get, medrxiv_source):
    """Test fetching works correctly when no categories are specified in config."""
    config = {"paper_source": {"medrxiv": {}}} # No categories
    medrxiv_source.configure(config, 'medrxiv')

    mock_response = MagicMock()
    mock_response.json.return_value = SAMPLE_API_RESPONSE_PAGE_1 # Use existing sample
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    end_time = datetime(2024, 1, 17, 12, 0, 0, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=medrxiv_source.fetch_window_days)

    papers = medrxiv_source.fetch_papers(start_time, end_time)

    assert len(papers) == 2 # Should still get papers

    # Check API call arguments - should not contain 'category' param
    expected_url = f"https://api.biorxiv.org/details/medrxiv/{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}/0/json"
    expected_params = {} # No category param
    mock_get.assert_called_once_with(expected_url, params=expected_params, timeout=30)
