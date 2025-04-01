import pytest
from unittest.mock import patch, MagicMock
import logging
from unittest.mock import call
from unittest.mock import mock_open

# Import the function to test
from main import check_papers
from src.paper import Paper
from datetime import datetime
from src.llm import LLMResponse, GroqChecker

# --- Test Fixtures ---
@pytest.fixture
def mock_config():
    """Provides a comprehensive mock configuration dictionary for tests.

    Includes sections for all major components (source, relevance, output, notifications)
    with default values suitable for most test scenarios. Tests can override specific
    values as needed.
    """
    return {
        # --- Top Level Settings ---
        "max_total_results": 100, # General limit (used by ArxivSource)
        "relevance_checking_method": "keyword", # Default check method

        # --- Paper Source Configuration (Example: arXiv) ---
        "paper_source": {
            "arxiv": {
                "categories": ["cs.AI"], # Example categories
                "keywords": ["test keyword", "another"], # Example keywords
            }
            # Add other sources here if needed (e.g., "hal": {...})
        },

        # --- Relevance Checker Configuration ---
        "relevance_checker": {
            # Keyword config is implicitly read from paper_source.arxiv.keywords
            "llm": { # LLM settings (even if method is keyword, might be needed for create_relevance_checker mock)
                "provider": "groq",
                "relevance_criteria": "General AI/ML relevance",
                "groq": {
                    "api_key": "mock-groq-key",
                    "model": "llama-3.1-8b-instant", # Optional model override
                    "prompt": "Is this paper relevant to {topic}?", # Example prompt
                    "confidence_threshold": 0.7 # Example threshold
                }
                # Add other providers here (e.g., "openai": {...})
            }
        },

        # --- Output Configuration (Example: File Writer) ---
        "output": {
            "file": "test_output.txt", # Default test output file
            "format": "plain", # Default format
            "include_confidence": False, # Default LLM detail inclusion
            "include_explanation": False
        },

        # --- Notifications Configuration (Example: Email) ---
        "notifications": {
            "send_email_summary": False, # Disable emails by default for tests
            "email_recipients": ["test@example.com"],
            "email_sender": { "address": "sender@example.com", "password": "sender_pass" },
            "smtp": { "server": "smtp.example.com", "port": 587 }
        }
        # Schedule config is not directly used by check_papers
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

# Mock classes for dependency injection (optional, could use autospec=True with patch)
class MockPaperSource:
    def __init__(self): self.papers = []
    def configure(self, config): pass
    def fetch_papers(self): return self.papers

class MockKeywordFilter:
    def __init__(self): self.relevant_papers = []
    def configure(self, config): pass
    def filter(self, papers): return self.relevant_papers

class MockFileWriter:
    def __init__(self): self.called_with = None
    def configure(self, config): pass
    def output(self, papers): self.called_with = papers

class MockEmailSender:
     def __init__(self, config): self.called = False; self.call_args = {}
     def send_summary_email(self, **kwargs): self.called = True; self.call_args = kwargs

# --- Test Cases ---

@patch("main.ArxivSource")
@patch("main.KeywordFilter")
@patch("builtins.open", new_callable=mock_open)
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker", return_value=None)
def test_check_papers_basic_flow(mock_create_checker, mock_email, mock_file_open, MockKeywordFilter, MockArxivSource, mock_config, caplog):
    """Tests the standard successful workflow using keyword filtering.

    Verifies that:
    1. ArxivSource is configured and fetches papers.
    2. KeywordFilter is configured and filters papers.
    3. FileWriter (real instance) is used, and file open is called.
    4. EmailSender is initialized and send_summary_email is called.
    5. Appropriate log messages are generated.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Configure mock instances returned when classes are called in check_papers
    mock_source_instance = MockArxivSource.return_value
    mock_filter_instance = MockKeywordFilter.return_value
    # FileWriter is NOT mocked here, we mock builtins.open instead

    # Define mock paper data
    mock_paper1 = Paper(id='1', title='Test Paper 1', abstract='Contains test keyword.', url='url1', source='arxiv')
    mock_paper2 = Paper(id='2', title='Test Paper 2', abstract='No match here.', url='url2', source='arxiv')
    # Simulate source fetching papers
    mock_source_instance.fetch_papers.return_value = [mock_paper1, mock_paper2]
    # Simulate filter finding one relevant paper
    mock_filter_instance.filter.return_value = [mock_paper1]
    # Simulate filter adding matched keywords to the paper object (as real filter does)
    mock_paper1.matched_keywords = ['test keyword']
    mock_filter_instance.filter.return_value[0] = mock_paper1

    # Ensure config specifies keyword method and enables email for this test
    mock_config["relevance_checking_method"] = "keyword"
    mock_config["notifications"]["send_email_summary"] = True
    # Ensure output file is configured for the real FileWriter
    output_filename = "dummy_output.txt"
    mock_config["output"] = {"file": output_filename}

    # Act: Call the function under test
    check_papers(mock_config)

    # Assert: Check interactions with mocked/real components
    MockArxivSource.assert_called_once() # Was ArxivSource class called?
    mock_source_instance.configure.assert_called_once_with(mock_config)
    mock_source_instance.fetch_papers.assert_called_once()

    MockKeywordFilter.assert_called_once() # Was KeywordFilter class called?
    mock_filter_instance.configure.assert_called_once_with(mock_config)
    mock_filter_instance.filter.assert_called_once_with([mock_paper1, mock_paper2])

    # Assert that the real FileWriter called open() to write the output
    mock_file_open.assert_called_once_with(output_filename, "a", encoding="utf-8")

    # Assert EmailSender interactions
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()
    # Optionally, check args passed to send_summary_email if needed:
    # email_call_args, _ = mock_email.return_value.send_summary_email.call_args
    # assert email_call_args[0]['num_fetched'] == 2 ... etc.

    # Assert: Check log messages
    assert "Keyword checking configured with keywords: ['test keyword', 'another']" in caplog.text
    assert "🔍 Filtering 2 papers using keywords..." in caplog.text
    assert "✅ Found 1 relevant papers after checking." in caplog.text
    assert f"Attempting to append 1 papers to '{output_filename}' (Format: plain)..." in caplog.text # Check log from real FileWriter
    assert f"Successfully appended details of 1 papers to '{output_filename}'" in caplog.text

@patch("main.ArxivSource") # Patch the class
@patch("main.KeywordFilter") # Patch the class
@patch("main.FileWriter") # Patch the class (don't need real output here)
@patch("main.EmailSender", autospec=True) # Mock email
@patch("main.create_relevance_checker", return_value=None) # Ensure keyword mode
def test_check_papers_no_papers_fetched(mock_create_checker, mock_email, MockFileWriter, MockKeywordFilter, MockArxivSource, mock_config, caplog):
    """Tests the workflow when the paper source fetches zero papers.

    Verifies that filtering and output writing are skipped, but email summary is still sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Setup mock instances and simulate no papers fetched
    mock_source_instance = MockArxivSource.return_value
    mock_filter_instance = MockKeywordFilter.return_value
    mock_writer_instance = MockFileWriter.return_value
    mock_source_instance.fetch_papers.return_value = [] # Key setup for this test
    mock_config["notifications"]["send_email_summary"] = True # Ensure email is attempted

    # Act
    check_papers(mock_config)

    # Assert: Check component interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once_with(mock_config)
    mock_source_instance.fetch_papers.assert_called_once()

    # Filter and Writer should not be instantiated or called
    MockKeywordFilter.assert_not_called()
    mock_filter_instance.configure.assert_not_called()
    mock_filter_instance.filter.assert_not_called()
    MockFileWriter.assert_not_called()
    mock_writer_instance.configure.assert_not_called()
    mock_writer_instance.output.assert_not_called()

    # Email should still be sent
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()

    # Assert: Check log messages
    assert "No papers fetched, skipping relevance check." in caplog.text
    assert "No relevant papers to save." in caplog.text

@patch("main.ArxivSource") # Patch the class
@patch("main.KeywordFilter") # Patch the class
@patch("main.FileWriter") # Patch the class
@patch("main.EmailSender", autospec=True) # Mock email
@patch("main.create_relevance_checker", return_value=None) # Ensure keyword mode
def test_check_papers_no_relevant_papers(mock_create_checker, mock_email, MockFileWriter, MockKeywordFilter, MockArxivSource, mock_config, caplog):
    """Tests the workflow when papers are fetched but none are relevant after filtering.

    Verifies that the filter is called, but the output writer is skipped.
    Email summary should still be sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Setup mocks, fetch papers, but filter returns empty
    mock_source_instance = MockArxivSource.return_value
    mock_filter_instance = MockKeywordFilter.return_value
    mock_writer_instance = MockFileWriter.return_value

    mock_paper1 = Paper(id='1', title='Test Paper 1', abstract='Irrelevant content.', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_filter_instance.filter.return_value = [] # Key setup for this test
    mock_config["relevance_checking_method"] = "keyword"
    mock_config["notifications"]["send_email_summary"] = True # Ensure email is attempted

    # Act
    check_papers(mock_config)

    # Assert: Check component interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once_with(mock_config)
    mock_source_instance.fetch_papers.assert_called_once()

    MockKeywordFilter.assert_called_once()
    mock_filter_instance.configure.assert_called_once_with(mock_config)
    mock_filter_instance.filter.assert_called_once_with([mock_paper1])

    # Writer should not be instantiated or called
    MockFileWriter.assert_not_called()
    mock_writer_instance.configure.assert_not_called()
    mock_writer_instance.output.assert_not_called()

    # Email should still be sent
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()

    # Assert: Check log messages
    assert "✅ Found 0 relevant papers after checking." in caplog.text
    assert "No relevant papers to save." in caplog.text

# --- LLM Marked Tests ---
# These tests are marked with '@pytest.mark.llm' and can be skipped using `pytest -m "not llm"`
# They follow a similar pattern but mock the LLM checker interactions.

@pytest.mark.llm
@patch("main.ArxivSource") # Patch source
@patch("main.FileWriter") # Patch writer
@patch("main.KeywordFilter") # Patch keyword filter (shouldn't be called)
@patch("main.EmailSender", autospec=True) # Mock email
@patch("main.create_relevance_checker") # Mock the factory function itself
def test_check_papers_llm_flow(mock_create_checker, mock_email, MockKeywordFilter, MockFileWriter, MockArxivSource, mock_config, caplog):
    """Tests the successful workflow using LLM relevance checking."""
    caplog.set_level(logging.INFO)

    # Arrange: Configure for LLM check method
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["notifications"]["send_email_summary"] = True

    # Mock the LLM checker instance that create_relevance_checker will return
    mock_llm_checker_instance = MagicMock(spec=GroqChecker)
    mock_create_checker.return_value = mock_llm_checker_instance

    # Mock LLM responses
    mock_response_relevant = LLMResponse(is_relevant=True, confidence=0.9, explanation="Relevant explain")
    mock_response_irrelevant = LLMResponse(is_relevant=False, confidence=0.8, explanation="Irrelevant explain")
    mock_llm_checker_instance.check_relevance_batch.return_value = [mock_response_relevant, mock_response_irrelevant]

    # Mock source instance and fetched papers
    mock_source_instance = MockArxivSource.return_value
    papers_to_check = [
        Paper(id='L1', title='Relevant Paper', abstract='Abstract 1', url='url1', source='arxiv'),
        Paper(id='L2', title='Irrelevant Paper', abstract='Abstract 2', url='url2', source='arxiv')
    ]
    mock_source_instance.fetch_papers.return_value = papers_to_check

    # Mock writer instance
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    mock_create_checker.assert_called_once_with(mock_config)
    mock_source_instance.fetch_papers.assert_called_once()
    # LLM checker methods should be called
    mock_llm_checker_instance.check_relevance_batch.assert_called_once()
    call_args, _ = mock_llm_checker_instance.check_relevance_batch.call_args
    assert call_args[0] == [p.abstract for p in papers_to_check] # Check abstracts passed
    # Keyword filter should NOT be instantiated or called
    MockKeywordFilter.assert_not_called()
    # Writer should be instantiated and called with the relevant paper
    MockFileWriter.assert_called_once()
    mock_writer_instance.configure.assert_called_once()
    mock_writer_instance.output.assert_called_once()
    output_call_args, _ = mock_writer_instance.output.call_args
    assert len(output_call_args[0]) == 1
    assert output_call_args[0][0].id == 'L1'
    # Check relevance info was added to the paper passed to writer
    assert output_call_args[0][0].relevance["confidence"] == 0.9
    # Email should be sent
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()

    # Assert: Check logs
    assert "Checking relevance of 2 papers using LLM..." in caplog.text
    assert "LLM batch processing completed" in caplog.text
    assert "✅ Found 1 relevant papers after checking." in caplog.text

@pytest.mark.llm
@patch("main.ArxivSource")
@patch("main.FileWriter")
@patch("main.KeywordFilter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker") # Mock the factory function
def test_check_papers_llm_creation_fails(mock_create_checker, mock_email, MockKeywordFilter, MockFileWriter, MockArxivSource, mock_config, caplog):
    """Tests fallback behavior when LLM checker fails to instantiate.

    Verifies that check_papers falls back to 'none' relevance checking (passes all papers)
    and logs appropriate warnings.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Configure for LLM, but mock factory to fail
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["notifications"]["send_email_summary"] = True
    mock_create_checker.return_value = None # Simulate failure

    # Mock source and writer
    mock_source_instance = MockArxivSource.return_value
    mock_paper1 = Paper(id='1', title='Paper 1', abstract='Abstract', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    mock_create_checker.assert_called_once_with(mock_config)
    # Keyword filter should NOT be called (fallback is 'none')
    MockKeywordFilter.assert_not_called()
    # Writer should be called with ALL fetched papers
    MockFileWriter.assert_called_once()
    mock_writer_instance.configure.assert_called_once()
    mock_writer_instance.output.assert_called_once_with([mock_paper1])
    # Email should be sent
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()
    # Verify checking_method passed to email was 'none'
    email_call_args, email_call_kwargs = mock_email.return_value.send_summary_email.call_args
    assert email_call_kwargs.get('checking_method') == 'none'

    # Assert: Check logs
    assert "LLM checking method selected, but failed to create LLM checker." in caplog.text
    assert "No specific relevance check performed or method defaulted." in caplog.text
    assert "✅ Found 1 relevant papers after checking." in caplog.text # All papers passed through

@pytest.mark.llm
@patch("main.ArxivSource")
@patch("main.FileWriter")
@patch("main.KeywordFilter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker") # Mock the factory function
def test_check_papers_llm_batch_error(mock_create_checker, mock_email, MockKeywordFilter, MockFileWriter, MockArxivSource, mock_config, caplog):
    """Tests error handling if the LLM batch processing step fails.

    Verifies that the error is logged, no papers are outputted, but the email summary is still sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Configure for LLM, mock checker to raise error on batch call
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["notifications"]["send_email_summary"] = True
    mock_llm_checker_instance = MagicMock(spec=GroqChecker)
    mock_llm_checker_instance.check_relevance_batch.side_effect = Exception("Batch API failed")
    mock_create_checker.return_value = mock_llm_checker_instance

    # Mock source and writer
    mock_source_instance = MockArxivSource.return_value
    mock_paper1 = Paper(id='1', title='Paper 1', abstract='Abstract', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    mock_create_checker.assert_called_once_with(mock_config)
    mock_source_instance.fetch_papers.assert_called_once()
    # LLM checker batch method was called (and raised error)
    mock_llm_checker_instance.check_relevance_batch.assert_called_once()
    # Keyword filter not called
    MockKeywordFilter.assert_not_called()
    # Writer not called as no papers became relevant due to error
    MockFileWriter.assert_not_called()
    mock_writer_instance.output.assert_not_called()
    # Email should still be sent
    mock_email.assert_called_once_with(mock_config)
    mock_email.return_value.send_summary_email.assert_called_once()
    # Verify checking_method passed to email was 'llm' and relevant papers is empty
    email_call_args, email_call_kwargs = mock_email.return_value.send_summary_email.call_args
    assert email_call_kwargs.get('checking_method') == 'llm'
    assert email_call_kwargs.get('relevant_papers') == []

    # Assert: Check logs
    assert "Error during LLM batch relevance check: Batch API failed" in caplog.text
    assert "✅ Found 0 relevant papers after checking." in caplog.text
