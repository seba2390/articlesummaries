import pytest
from unittest.mock import patch, MagicMock

# Import the function to test
from main import main_job
from src.paper import Paper
from datetime import datetime

# --- Test Fixtures ---
@pytest.fixture
def mock_config():
    # Provide a basic config for testing main_job structure
    return {
        'categories': ['test'],
        'keywords': ['relevant'],
        'max_total_results': 5,
        'output_file': 'output.txt'
    }

@pytest.fixture
def mock_components():
    """Provides mocked instances of source, filter, and output handler."""
    with patch('main.ArxivSource') as MockSource, \
         patch('main.KeywordFilter') as MockFilter, \
         patch('main.FileWriter') as MockOutput:

        mock_source_instance = MockSource()
        mock_filter_instance = MockFilter()
        mock_output_instance = MockOutput()

        # Set default return values for mocks
        mock_source_instance.fetch_papers.return_value = [] # Default: no papers
        mock_filter_instance.filter.return_value = []       # Default: no relevant papers
        mock_output_instance.output.return_value = None

        yield {
            'source': mock_source_instance,
            'filter': mock_filter_instance,
            'output': mock_output_instance
        }

# --- Test Cases ---

def test_main_job_success_flow(mock_config, mock_components):
    """Test the successful execution path of main_job."""

    # Arrange: Configure mocks for a successful run
    paper1 = Paper(id='p1', title='Relevant Paper', abstract='abc', published_date=datetime.now())
    paper2 = Paper(id='p2', title='Irrelevant Paper', abstract='xyz', published_date=datetime.now())
    fetched_papers = [paper1, paper2]
    relevant_papers = [paper1] # Only paper1 matches 'relevant' keyword hypothetically

    mock_components['source'].fetch_papers.return_value = fetched_papers
    mock_components['filter'].filter.return_value = relevant_papers

    # Act: Run the main job
    main_job(mock_config)

    # Assert: Check that components were configured and methods called
    mock_components['source'].configure.assert_called_once_with(mock_config)
    mock_components['filter'].configure.assert_called_once_with(mock_config)
    mock_components['output'].configure.assert_called_once_with(mock_config)

    mock_components['source'].fetch_papers.assert_called_once()
    mock_components['filter'].filter.assert_called_once_with(fetched_papers) # Called with fetched papers
    mock_components['output'].output.assert_called_once_with(relevant_papers) # Called with relevant papers

def test_main_job_no_papers_fetched(mock_config, mock_components):
    """Test the flow when the paper source returns no papers."""

    # Arrange: source returns empty list (default mock behavior)
    # mock_components['source'].fetch_papers.return_value = []

    # Act
    main_job(mock_config)

    # Assert
    mock_components['source'].configure.assert_called_once_with(mock_config)
    mock_components['filter'].configure.assert_called_once_with(mock_config)
    mock_components['output'].configure.assert_called_once_with(mock_config)

    mock_components['source'].fetch_papers.assert_called_once()
    # Filter and output should NOT be called if fetch returns nothing
    mock_components['filter'].filter.assert_not_called()
    mock_components['output'].output.assert_not_called()

def test_main_job_no_relevant_papers(mock_config, mock_components):
    """Test the flow when papers are fetched but none are relevant."""

    # Arrange: source returns papers, filter returns empty list
    paper1 = Paper(id='p1', title='Irrelevant Paper', abstract='xyz', published_date=datetime.now())
    fetched_papers = [paper1]
    mock_components['source'].fetch_papers.return_value = fetched_papers
    # mock_components['filter'].filter.return_value = [] # Default mock behavior

    # Act
    main_job(mock_config)

    # Assert
    mock_components['source'].configure.assert_called_once_with(mock_config)
    mock_components['filter'].configure.assert_called_once_with(mock_config)
    mock_components['output'].configure.assert_called_once_with(mock_config)

    mock_components['source'].fetch_papers.assert_called_once()
    mock_components['filter'].filter.assert_called_once_with(fetched_papers)
    # Output should NOT be called if filter returns nothing
    mock_components['output'].output.assert_not_called()

@patch('main.logger') # Mock the logger in main.py
def test_main_job_source_error(mock_logger, mock_config, mock_components):
    """Test handling of an error during paper fetching."""

    # Arrange: source fetch_papers raises an error
    mock_components['source'].fetch_papers.side_effect = Exception("Fetch failed!")

    # Act
    main_job(mock_config)

    # Assert
    mock_components['source'].configure.assert_called_once_with(mock_config)
    mock_components['filter'].configure.assert_called_once_with(mock_config)
    mock_components['output'].configure.assert_called_once_with(mock_config)

    mock_components['source'].fetch_papers.assert_called_once()
    # Filter and output should not be called
    mock_components['filter'].filter.assert_not_called()
    mock_components['output'].output.assert_not_called()
    # Check error logging
    mock_logger.error.assert_called()
    # Check the specific arguments of the *first* error call
    assert len(mock_logger.error.call_args_list) > 0
    first_error_call_args = mock_logger.error.call_args_list[0]
    # Check the message part of the log call
    assert "An error occurred during the main job execution" in first_error_call_args[0][0]
    # Check that exc_info=True was passed in kwargs
    assert first_error_call_args[1].get('exc_info') is True

# Add similar tests for errors during filtering and outputting if desired
