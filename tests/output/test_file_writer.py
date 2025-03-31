import pytest
import os
from unittest.mock import patch, mock_open, call
from datetime import datetime, timezone
import logging

from src.output.file_writer import FileWriter
from src.paper import Paper

# --- Test Fixtures ---
@pytest.fixture
def file_writer_instance():
    return FileWriter()

@pytest.fixture
def relevant_papers():
    dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        Paper(id='1', title='Paper 1', authors=['Auth A', 'Auth B'], abstract='Abstract one.\nLine two.', url='url1', published_date=dt, source='test'),
        Paper(id='2', title='Paper 2', authors=['Auth C'], abstract='Abstract two.', url='url2', published_date=dt, source='test'),
    ]

# --- Test Cases ---

def test_configure_file_writer(file_writer_instance):
    """Test configuring the FileWriter with a specific output file."""
    config = {'output_file': 'my_output.log'}
    file_writer_instance.configure(config)
    assert file_writer_instance.output_file == 'my_output.log'

def test_configure_file_writer_default(file_writer_instance):
    """Test that the default output file is used if not specified."""
    file_writer_instance.configure({})
    assert file_writer_instance.output_file == 'relevant_papers.txt' # Default value

@patch("builtins.open", new_callable=mock_open) # Mock the built-in open function
def test_output_writes_to_file(mock_open_file, file_writer_instance, relevant_papers):
    """Test that relevant papers are correctly formatted and written to the file."""
    output_filename = "test_out.txt"
    config = {'output_file': output_filename}
    file_writer_instance.configure(config)

    # Call the output method
    file_writer_instance.output(relevant_papers)

    # Assert that open was called correctly (append mode 'a', utf-8 encoding)
    mock_open_file.assert_called_once_with(output_filename, 'a', encoding='utf-8')

    # Get the handle for the mock file to check writes
    handle = mock_open_file()

    # Check that the expected content was written
    assert handle.write.call_count > 3 # Header + 2 papers + newlines
    # Check the header (tricky with dynamic datetime, check start)
    assert handle.write.call_args_list[0][0][0].startswith("--- Relevant Papers Found on")

    # Check formatting of the first paper (more robust checks)
    expected_paper1_lines = [
        "ID: 1\n",
        "Source: test\n",
        "Title: Paper 1\n",
        "Authors: Auth A, Auth B\n",
        "Updated/Published: 2024-01-15 12:00:00 UTC\n",
        "URL: url1\n",
        "Abstract: Abstract one. Line two.\n\n" # Check newline replacement
    ]
    # Get actual calls corresponding to paper 1
    actual_calls_paper1 = [c[0][0] for c in handle.write.call_args_list[1:1+len(expected_paper1_lines)]]
    assert actual_calls_paper1 == expected_paper1_lines

@patch("builtins.open", new_callable=mock_open)
def test_output_no_papers(mock_open_file, file_writer_instance, caplog):
    """Test that nothing is written if the paper list is empty."""
    config = {'output_file': 'test_out.txt'}
    file_writer_instance.configure(config)

    # Set caplog level to INFO for this test
    with caplog.at_level(logging.INFO):
        file_writer_instance.output([])

    mock_open_file.assert_not_called() # File should not be opened
    assert "No relevant papers found in this run. Nothing to write to file." in caplog.text

def test_output_no_file_configured(file_writer_instance, caplog):
    """Test behavior when output_file is not configured (set to None)."""
    file_writer_instance.output_file = None # Simulate missing config value
    # Set caplog level to ERROR for this test
    with caplog.at_level(logging.ERROR):
        file_writer_instance.output(relevant_papers) # Pass some papers to trigger the check
    # Update expected log message
    assert "FileWriter cannot write output: Output file path is not configured." in caplog.text

@patch("builtins.open", mock_open())
@patch("src.output.file_writer.logger") # Mock logger within the module
def test_output_io_error(mock_logger, file_writer_instance, relevant_papers):
    """Test handling of IOError during file writing."""
    config = {'output_file': 'test_out.txt'}
    file_writer_instance.configure(config)

    # Make the mock file's write method raise an IOError
    mock_file_handle = open('test_out.txt', 'a')
    mock_file_handle.write.side_effect = IOError("Disk full")

    file_writer_instance.output(relevant_papers)

    # Check that the error was logged
    mock_logger.error.assert_called_once()
    # Update expected log message format
    assert "IOError writing to output file 'test_out.txt': Disk full" in mock_logger.error.call_args[0][0]
    assert isinstance(mock_logger.error.call_args[1]['exc_info'], bool)
    assert mock_logger.error.call_args[1]['exc_info'] is True
