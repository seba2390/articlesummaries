import pytest
import os
from unittest.mock import patch, mock_open, call, MagicMock
from datetime import datetime, timezone
import logging
from typing import List, Dict, Any

from src.output.file_writer import FileWriter
from src.paper import Paper

# --- Test Fixtures ---
@pytest.fixture
def file_writer_instance() -> FileWriter:
    """Provides a clean instance of FileWriter for each test."""
    return FileWriter()

@pytest.fixture
def relevant_papers() -> List[Paper]:
    """Provides a list of sample Paper objects for testing output."""
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        Paper(id='1', title='Paper 1', authors=['Auth A', 'Auth B'], abstract='Abstract one.\nLine two.', url='url1', published_date=dt, source='test', categories=['cat1']),
        Paper(id='2', title='Paper 2', authors=['Auth C'], abstract='Abstract two.', url='url2', published_date=dt, source='test', categories=['cat2'], matched_keywords=['kw1']),
    ]

# --- Test Cases ---

def test_configure_file_writer(file_writer_instance: FileWriter):
    """Tests that the FileWriter configures its output file path correctly."""
    # Arrange
    config = {'file': 'my_output.log'}
    # Act
    file_writer_instance.configure(config)
    # Assert
    assert file_writer_instance.output_file == 'my_output.log'

def test_configure_file_writer_default(file_writer_instance: FileWriter):
    """Tests that the FileWriter uses the default output file path if none is provided."""
    # Arrange: Empty config
    # Act
    file_writer_instance.configure({})
    # Assert
    # Check against the expected default string value, as the class attribute doesn't exist
    assert file_writer_instance.output_file == 'relevant_papers.txt'

@patch("builtins.open", new_callable=mock_open)
def test_output_writes_to_file(
    mock_open_file: MagicMock,
    file_writer_instance: FileWriter,
    relevant_papers: List[Paper]
):
    """Tests the happy path: formatting and writing papers to the specified file.

    Verifies:
    - File is opened correctly (path, mode 'a', encoding).
    - A header with the current date is written.
    - Each paper's details are formatted and written according to the FileWriter logic.
    - Optional fields (keywords, categories, relevance) are included when present.
    - A separator is written between papers.
    """
    # Arrange: Configure the instance
    output_filename = "test_out.txt"
    config = {'file': output_filename, 'include_confidence': True, 'include_explanation': True}
    file_writer_instance.configure(config)

    # Add relevance info to test those fields
    relevant_papers[0].relevance = {'confidence': 0.9, 'explanation': 'Relevant due to X'}

    # Act: Call the output method
    file_writer_instance.output(relevant_papers)

    # Assert: File opening
    mock_open_file.assert_called_once_with(output_filename, 'a', encoding='utf-8')

    # Assert: File writing
    handle = mock_open_file() # Get the mock file handle

    # Verify header write
    assert handle.write.call_args_list[0][0][0].startswith("--- Relevant Papers Found on")
    assert handle.write.call_args_list[0][0][0].endswith("---\n\n")

    # --- Verify Paper 1 ---
    paper1 = relevant_papers[0]
    expected_paper1_lines = [
        f"ID: {paper1.id}\n",
        f"Source: {paper1.source}\n",
        f"Title: {paper1.title}\n",
        f"Authors: {', '.join(paper1.authors)}\n",
        f"Categories: {', '.join(paper1.categories)}\n", # Has categories
        f"Updated/Published: {paper1.published_date.strftime('%Y-%m-%d %H:%M:%S %Z')}\n",
        f"URL: {paper1.url}\n",
        # No matched keywords for paper 1
        f"Abstract: {str(paper1.abstract).replace('\n', ' ').replace('\r', '')}\n",
        # Has relevance info
        f"Relevance Confidence: {paper1.relevance['confidence']:.2f}\n",
        f"Relevance Explanation: {paper1.relevance['explanation']}\n",
        "\n" + "=" * 80 + "\n\n" # Separator
    ]

    # Get the slice of calls corresponding to paper 1
    start_index_p1 = 1 # After header
    end_index_p1 = start_index_p1 + len(expected_paper1_lines)
    actual_calls_paper1 = [c[0][0] for c in handle.write.call_args_list[start_index_p1:end_index_p1]]

    # Compare actual writes for paper 1 with expected lines
    assert actual_calls_paper1 == expected_paper1_lines

    # --- Verify Paper 2 ---
    paper2 = relevant_papers[1]
    expected_paper2_lines = [
        f"ID: {paper2.id}\n",
        f"Source: {paper2.source}\n",
        f"Title: {paper2.title}\n",
        f"Authors: {', '.join(paper2.authors)}\n",
        f"Categories: {', '.join(paper2.categories)}\n", # Has categories
        f"Updated/Published: {paper2.published_date.strftime('%Y-%m-%d %H:%M:%S %Z')}\n",
        f"URL: {paper2.url}\n",
        f"Matched Keywords: {', '.join(paper2.matched_keywords)}\n", # Has keywords
        f"Abstract: {str(paper2.abstract).replace('\n', ' ').replace('\r', '')}\n",
        # No relevance info for paper 2
        "\n" + "=" * 80 + "\n\n" # Separator
    ]

    # Get the slice of calls corresponding to paper 2
    start_index_p2 = end_index_p1 # Starts after paper 1
    end_index_p2 = start_index_p2 + len(expected_paper2_lines)
    actual_calls_paper2 = [c[0][0] for c in handle.write.call_args_list[start_index_p2:end_index_p2]]

    # Compare actual writes for paper 2 with expected lines
    assert actual_calls_paper2 == expected_paper2_lines

    # Assert total number of writes matches header + paper1 lines + paper2 lines
    assert handle.write.call_count == 1 + len(expected_paper1_lines) + len(expected_paper2_lines)


@patch("builtins.open", new_callable=mock_open)
def test_output_no_papers(
    mock_open_file: MagicMock,
    file_writer_instance: FileWriter,
    caplog: pytest.LogCaptureFixture
):
    """Tests that nothing is written and a log message is generated if the paper list is empty."""
    # Arrange
    config = {'file': 'test_out.txt'}
    file_writer_instance.configure(config)

    # Act & Assert Logging
    with caplog.at_level(logging.INFO):
        file_writer_instance.output([])

    # Assert: File should not be opened, and log message should be present
    mock_open_file.assert_not_called()
    assert "No relevant papers provided to FileWriter" in caplog.text
    assert "Nothing written." in caplog.text

def test_output_no_file_configured(
    file_writer_instance: FileWriter,
    relevant_papers: List[Paper], # Need papers to attempt output
    caplog: pytest.LogCaptureFixture
):
    """Tests that an error is logged if the output file path is not configured (e.g., None)."""
    # Arrange: Simulate missing configuration
    file_writer_instance.output_file = None

    # Act & Assert Logging
    with caplog.at_level(logging.ERROR):
        file_writer_instance.output(relevant_papers)

    # Assert: Check for the specific error log message
    assert "FileWriter cannot write output: Output file path is not configured via `configure()`." in caplog.text

@patch("builtins.open", new_callable=mock_open)
@patch("src.output.file_writer.logger") # Mock the logger in the file_writer module
def test_output_io_error(
    mock_logger: MagicMock,
    mock_open_file: MagicMock, # Need the mock_open fixture too
    file_writer_instance: FileWriter,
    relevant_papers: List[Paper]
):
    """Tests that an IOError during file writing is caught and logged."""
    # Arrange: Configure the instance
    output_filename = 'test_out.txt'
    config = {'file': output_filename}
    file_writer_instance.configure(config)

    # Arrange: Make the mock file's write method raise an IOError
    mock_file_handle = mock_open_file.return_value # Get the handle returned by mock_open
    mock_file_handle.write.side_effect = IOError("Disk full")

    # Act: Attempt to write papers
    file_writer_instance.output(relevant_papers)

    # Assert: Check that the error was logged correctly
    mock_logger.error.assert_called_once()
    log_message = mock_logger.error.call_args[0][0]
    assert f"IOError writing to output file '{output_filename}'" in log_message
    assert "Disk full" in log_message
