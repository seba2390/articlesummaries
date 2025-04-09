import pytest
from unittest.mock import patch, MagicMock
import logging
from unittest.mock import call
from unittest.mock import mock_open
from datetime import datetime
from unittest.mock import ANY

# Import the function to test
from main import check_papers
from src.paper import Paper
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
        "active_sources": ["arxiv"],
        "max_total_results": 100, # General limit (used by ArxivSource)
        "relevance_checking_method": "keyword", # Default check method
        # "global_fetch_window_days": 1, # Removed global fetch window

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
            "llm": { # LLM settings
                "provider": "groq",
                # Provider specific settings (e.g., groq) are loaded from separate file
                # but we can keep some mocks here for tests if needed
                "groq": {
                    "api_key": "mock-groq-key",
                    "model": "mock-llama-test",
                    "prompt": "Is this mock paper relevant?",
                    "confidence_threshold": 0.75
                }
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

@patch("main.KeywordFilter")
@patch("builtins.open", new_callable=mock_open)
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker", return_value=None)
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_basic_flow(MockArxivSource, mock_create_checker, MockEmailSender, mock_file_open, MockKeywordFilter, mock_config, caplog):
    """Tests the standard successful workflow using keyword filtering.

    Verifies that:
    1. ArxivSource is configured and fetches papers.
    2. KeywordFilter is configured and filters papers.
    3. FileWriter (real instance) is used, and file open is called.
    4. EmailSender is initialized and send_summary_email is called.
    5. Appropriate log messages are generated.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Get the mock instance that ArxivSource() will return
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed

    mock_filter_instance = MockKeywordFilter.return_value

    # Define mock paper data
    mock_paper1 = Paper(id='1', title='Test Paper 1', abstract='Contains test keyword.', url='url1', source='arxiv')
    mock_paper2 = Paper(id='2', title='Test Paper 2', abstract='No match here.', url='url2', source='arxiv')
    # Simulate source fetching papers - Set return value on the instance mock
    mock_source_instance.fetch_papers.return_value = [mock_paper1, mock_paper2]

    # Simulate filter finding one relevant paper
    mock_filter_instance.filter.return_value = [mock_paper1]
    mock_paper1.matched_keywords = ['test keyword'] # Simulate filter adding keywords
    # No need to reassign, modify the object directly
    # mock_filter_instance.filter.return_value[0] = mock_paper1

    # Configure config for test specifics
    mock_config["relevance_checking_method"] = "keyword"
    mock_config["send_email_summary"] = True
    output_filename = "dummy_output.txt"
    mock_config["output"] = {"file": output_filename}

    # Act: Call the function under test
    check_papers(mock_config)

    # Assert: Check interactions
    MockArxivSource.assert_called_once() # Check ArxivSource() was called
    # Assertions are now on the mock_source_instance returned by the patched call
    mock_source_instance.configure.assert_called_once_with(mock_config, 'arxiv')
    mock_source_instance.fetch_papers.assert_called_once()

    MockKeywordFilter.assert_called_once() # Check KeywordFilter() was called
    # Assert that configure was called with the temporary, source-specific config
    expected_filter_config = {'paper_source': {'arxiv': {'keywords': mock_config['paper_source']['arxiv']['keywords']}}}
    mock_filter_instance.configure.assert_called_once_with(expected_filter_config)
    mock_filter_instance.filter.assert_called_once_with([mock_paper1, mock_paper2])

    mock_file_open.assert_called_once_with(output_filename, "a", encoding="utf-8")

    # Check that EmailSender class was called (instantiated)
    MockEmailSender.assert_called_once_with(mock_config)
    # Check that the send_summary_email method was called on the returned instance
    mock_email_instance = MockEmailSender.return_value
    mock_email_instance.send_summary_email.assert_called_once()
    # Check args passed to the method call on the instance
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature (relevant_papers, run_stats)
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == [mock_paper1]
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 2
    assert run_stats_arg['total_relevant'] == 1
    assert run_stats_arg['checking_method'] == 'keyword'
    # Check source name within the sources_summary dict
    assert 'arxiv' in run_stats_arg['sources_summary']
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check log messages
    assert "🔍 Filtering 2 papers using keywords defined per source..." in caplog.text
    assert "✅ Found 1 relevant papers across all sources after checking." in caplog.text
    assert f"Attempting to append 1 papers to '{output_filename}' (Format: plain)..." in caplog.text
    assert f"Successfully appended details of 1 papers to '{output_filename}'" in caplog.text

@patch("main.KeywordFilter")
@patch("main.FileWriter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker", return_value=None)
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_no_papers_fetched(MockArxivSource, mock_create_checker, MockEmailSender, MockFileWriter, MockKeywordFilter, mock_config, caplog):
    """Tests the workflow when the paper source fetches zero papers.

    Verifies that filtering and output writing are skipped, but email summary is still sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Setup mock instances
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed
    mock_filter_instance = MockKeywordFilter.return_value
    mock_writer_instance = MockFileWriter.return_value

    mock_source_instance.fetch_papers.return_value = [] # Simulate no papers fetched
    mock_config["send_email_summary"] = True

    # Act
    check_papers(mock_config)

    # Assert: Check component interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once_with(mock_config, 'arxiv')
    mock_source_instance.fetch_papers.assert_called_once() # Should be called

    # Filter and Writer class should not be called now (check_papers exits before filter/writer instantiation)
    MockKeywordFilter.assert_not_called()
    # mock_filter_instance.configure.assert_not_called() # Instance doesn't exist if class not called
    # mock_filter_instance.filter.assert_not_called()
    MockFileWriter.assert_not_called()
    # mock_writer_instance.configure.assert_not_called()
    # mock_writer_instance.output.assert_not_called()

    # Email should still be sent
    MockEmailSender.assert_called_once_with(mock_config)
    mock_email_instance = MockEmailSender.return_value
    mock_email_instance.send_summary_email.assert_called_once()
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == []
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 0
    assert run_stats_arg['total_relevant'] == 0
    assert run_stats_arg['checking_method'] == 'keyword'
    assert 'arxiv' in run_stats_arg['sources_summary']
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check log messages
    assert "ℹ️ No papers fetched from any source, skipping relevance check." in caplog.text
    assert "ℹ️ No relevant papers to output." in caplog.text

@patch("main.KeywordFilter")
@patch("main.FileWriter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker", return_value=None)
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_no_relevant_papers(MockArxivSource, mock_create_checker, MockEmailSender, MockFileWriter, MockKeywordFilter, mock_config, caplog):
    """Tests the workflow when papers are fetched but none are relevant after filtering.

    Verifies that the filter is called, but the output writer is skipped.
    Email summary should still be sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Setup mocks
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed
    mock_filter_instance = MockKeywordFilter.return_value
    mock_writer_instance = MockFileWriter.return_value

    # Arrange: Mock email instance
    mock_email_instance = MockEmailSender.return_value

    mock_paper1 = Paper(id='1', title='Test Paper 1', abstract='Irrelevant content.', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_filter_instance.filter.return_value = [] # Filter returns empty
    mock_config["relevance_checking_method"] = "keyword"
    mock_config["send_email_summary"] = True

    # Act
    check_papers(mock_config)

    # Assert: Check component interactions
    MockArxivSource.assert_called_once()
    # Check that configure was called with the full config and the source name
    mock_source_instance.configure.assert_called_once_with(mock_config, 'arxiv') # Added source name
    mock_source_instance.fetch_papers.assert_called_once()

    MockKeywordFilter.assert_called_once()
    # Assert that configure was called with the temporary, source-specific config
    expected_filter_config = {'paper_source': {'arxiv': {'keywords': mock_config['paper_source']['arxiv']['keywords']}}}
    mock_filter_instance.configure.assert_called_once_with(expected_filter_config)
    mock_filter_instance.filter.assert_called_once_with([mock_paper1])

    # FileWriter class should NOT be instantiated if no relevant papers found
    MockFileWriter.assert_not_called()

    # Email should still be sent
    MockEmailSender.assert_called_once_with(mock_config)
    mock_email_instance.send_summary_email.assert_called_once()
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == []
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 1
    assert run_stats_arg['total_relevant'] == 0
    assert run_stats_arg['checking_method'] == 'keyword'
    assert 'arxiv' in run_stats_arg['sources_summary']
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check log messages
    assert "✅ Found 0 relevant papers across all sources after checking." in caplog.text
    assert "ℹ️ No relevant papers to output." in caplog.text

# --- LLM Marked Tests ---
# These tests are marked with '@pytest.mark.llm' and can be skipped using `pytest -m "not llm"`
# They follow a similar pattern but mock the LLM checker interactions.

@pytest.mark.llm
@patch("main.FileWriter")
@patch("main.KeywordFilter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker")
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_llm_flow(MockArxivSource, mock_create_checker, MockEmailSender, MockKeywordFilter, MockFileWriter, mock_config, caplog):
    """Tests the successful workflow using LLM relevance checking."""
    caplog.set_level(logging.INFO)

    # Arrange: Config
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["send_email_summary"] = True

    # Arrange: Mock LLM checker
    mock_llm_checker_instance = MagicMock(spec=GroqChecker)
    mock_create_checker.return_value = mock_llm_checker_instance
    mock_response_relevant = LLMResponse(is_relevant=True, confidence=0.9, explanation="Relevant explain")
    mock_response_irrelevant = LLMResponse(is_relevant=False, confidence=0.8, explanation="Irrelevant explain")
    mock_llm_checker_instance.check_relevance_batch.return_value = [mock_response_relevant, mock_response_irrelevant]

    # Arrange: Mock source instance
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed
    papers_to_check = [
        Paper(id='L1', title='Relevant Paper', abstract='Abstract 1', url='url1', source='arxiv'),
        Paper(id='L2', title='Irrelevant Paper', abstract='Abstract 2', url='url2', source='arxiv')
    ]
    mock_source_instance.fetch_papers.return_value = papers_to_check

    # Arrange: Mock writer instance
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once()
    mock_source_instance.fetch_papers.assert_called_once()
    mock_create_checker.assert_called_once_with(mock_config)
    mock_llm_checker_instance.check_relevance_batch.assert_called_once()
    call_args, _ = mock_llm_checker_instance.check_relevance_batch.call_args
    assert call_args[0] == [p.abstract for p in papers_to_check] # Check abstracts passed
    MockKeywordFilter.assert_not_called()
    MockFileWriter.assert_called_once()
    mock_writer_instance.configure.assert_called_once()
    mock_writer_instance.output.assert_called_once()
    output_call_args, _ = mock_writer_instance.output.call_args
    assert len(output_call_args[0]) == 1
    assert output_call_args[0][0].id == 'L1'
    # Check relevance info was added to the paper passed to writer
    assert output_call_args[0][0].relevance["confidence"] == 0.9
    # Make sure provider_name attribute exists on the mock
    mock_llm_checker_instance.provider_name = 'groq'
    MockEmailSender.assert_called_once_with(mock_config)
    mock_email_instance = MockEmailSender.return_value
    mock_email_instance.send_summary_email.assert_called_once()
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature (relevant_papers, run_stats)
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == [mock_paper1]
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 2
    assert run_stats_arg['total_relevant'] == 1
    assert run_stats_arg['checking_method'] == 'llm' # Check method
    assert 'arxiv' in run_stats_arg['sources_summary'] # Check source exists in summary dict
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check logs
    assert "Checking relevance of 2 papers using LLM..." in caplog.text
    assert "LLM batch processing completed" in caplog.text
    assert "✅ Found 1 relevant papers across all sources after checking." in caplog.text

@pytest.mark.llm
@patch("main.FileWriter")
@patch("main.KeywordFilter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker")
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_llm_creation_fails(MockArxivSource, mock_create_checker, MockEmailSender, MockKeywordFilter, MockFileWriter, mock_config, caplog):
    """Tests fallback behavior when LLM checker fails to instantiate.

    Verifies that check_papers falls back to 'none' relevance checking (passes all papers)
    and logs appropriate warnings.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Config
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["send_email_summary"] = True
    mock_create_checker.return_value = None # Simulate failure

    # Arrange: Mock source and writer
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed
    mock_paper1 = Paper(id='1', title='Paper 1', abstract='Abstract', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once()
    mock_source_instance.fetch_papers.assert_called_once()
    mock_create_checker.assert_called_once_with(mock_config)
    MockKeywordFilter.assert_not_called()
    MockFileWriter.assert_called_once()
    mock_writer_instance.configure.assert_called_once()
    mock_writer_instance.output.assert_called_once_with([mock_paper1])
    MockEmailSender.assert_called_once_with(mock_config)
    mock_email_instance = MockEmailSender.return_value
    mock_email_instance.send_summary_email.assert_called_once()
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == [mock_paper1]
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 1
    assert run_stats_arg['total_relevant'] == 1
    assert run_stats_arg['checking_method'] == 'none'
    assert 'arxiv' in run_stats_arg['sources_summary'] # Check source exists in summary dict
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check logs
    assert "LLM checking method selected, but failed to create LLM checker." in caplog.text
    assert "No specific relevance check performed or method defaulted." in caplog.text
    assert "✅ Found 1 relevant papers across all sources after checking." in caplog.text

@pytest.mark.llm
@patch("main.FileWriter")
@patch("main.KeywordFilter")
@patch("main.EmailSender", autospec=True)
@patch("main.create_relevance_checker")
@patch("main.ArxivSource", autospec=True) # Patch the class call within check_papers
def test_check_papers_llm_batch_error(MockArxivSource, mock_create_checker, MockEmailSender, MockKeywordFilter, MockFileWriter, mock_config, caplog):
    """Tests error handling if the LLM batch processing step fails.

    Verifies that the error is logged, no papers are outputted, but the email summary is still sent.
    """
    caplog.set_level(logging.INFO)

    # Arrange: Config
    mock_config['relevance_checking_method'] = 'llm'
    mock_config["send_email_summary"] = True
    mock_llm_checker_instance = MagicMock(spec=GroqChecker)
    mock_llm_checker_instance.check_relevance_batch.side_effect = Exception("Batch API failed")
    mock_create_checker.return_value = mock_llm_checker_instance

    # Arrange: Mock source and writer
    mock_source_instance = MockArxivSource.return_value
    mock_source_instance.fetch_window_days = 1 # Set attribute needed
    mock_paper1 = Paper(id='1', title='Paper 1', abstract='Abstract', url='url1', source='arxiv')
    mock_source_instance.fetch_papers.return_value = [mock_paper1]
    mock_writer_instance = MockFileWriter.return_value

    # Act
    check_papers(mock_config)

    # Assert: Check interactions
    MockArxivSource.assert_called_once()
    mock_source_instance.configure.assert_called_once()
    mock_source_instance.fetch_papers.assert_called_once()
    mock_create_checker.assert_called_once_with(mock_config)
    mock_llm_checker_instance.check_relevance_batch.assert_called_once()
    MockKeywordFilter.assert_not_called()
    # FileWriter class *is* instantiated now, but output is not called
    MockFileWriter.assert_called_once()
    mock_writer_instance.configure.assert_called_once()
    mock_writer_instance.output.assert_not_called() # output() not called
    MockEmailSender.assert_called_once_with(mock_config)
    mock_email_instance = MockEmailSender.return_value
    mock_email_instance.send_summary_email.assert_called_once()
    call_args, call_kwargs = mock_email_instance.send_summary_email.call_args
    # Assert based on the new call signature
    assert 'relevant_papers' in call_kwargs
    assert 'run_stats' in call_kwargs
    assert call_kwargs['relevant_papers'] == []
    run_stats_arg = call_kwargs['run_stats']
    assert run_stats_arg['total_fetched'] == 1
    assert run_stats_arg['total_relevant'] == 0
    assert run_stats_arg['checking_method'] == 'llm'
    assert 'arxiv' in run_stats_arg['sources_summary'] # Check source exists in summary dict
    assert isinstance(run_stats_arg['run_duration_secs'], float)

    # Assert: Check logs
    assert "Error during LLM batch relevance check: Batch API failed" in caplog.text
    assert "✅ Found 0 relevant papers across all sources after checking." in caplog.text
