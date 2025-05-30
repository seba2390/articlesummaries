"""Tests for the Groq LLM relevance checker."""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.llm.base_checker import LLMResponse
from src.llm.groq_checker import GroqChecker
from src.paper import Paper # Import Paper from src.paper

# Logger for test outputs
logger = logging.getLogger(__name__)

# Sample Paper objects for testing
paper1 = Paper(id="1", title="Paper 1", abstract="Summary 1", authors=["Author A"], url="url1", categories=["cs.AI"], source="arxiv")
paper2 = Paper(id="2", title="Paper 2", abstract="Summary 2", authors=["Author B"], url="url2", categories=["cs.LG"], source="arxiv")
paper3 = Paper(id="3", title="Paper 3", abstract="Summary 3", authors=["Author C"], url="url3", categories=["math.NT"], source="arxiv")

@pytest.fixture
def groq_checker():
    """Provides a GroqChecker instance for testing."""
    return GroqChecker(api_key="test-api-key")

@pytest.mark.llm # Mark this test
@patch("requests.post")
def test_check_relevance_success(mock_post, groq_checker):
    """Test successful single relevance check."""
    # Mock the requests.post response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    # Simulate the nested JSON structure Groq returns
    response_content = {
        "is_relevant": True,
        "confidence": 0.95,
        "explanation": "The abstract clearly discusses relevant topics.",
    }
    mock_response.json.return_value = {
        "choices": [{
            "message": {"content": json.dumps(response_content)}
        }]
    }
    mock_post.return_value = mock_response

    abstract = "This is an abstract about machine learning."
    prompt = "Is this relevant to AI?"
    result = groq_checker.check_relevance(abstract, prompt)

    assert isinstance(result, LLMResponse)
    assert result.is_relevant is True
    assert result.confidence == 0.95
    assert result.explanation == "The abstract clearly discusses relevant topics."
    mock_post.assert_called_once()
    call_args, call_kwargs = mock_post.call_args
    assert call_args[0] == "https://api.groq.com/openai/v1/chat/completions"
    assert call_kwargs["headers"]["Authorization"] == "Bearer test-api-key"
    assert call_kwargs["json"]["model"] == "llama-3.1-8b-instant"
    assert call_kwargs["json"]["messages"][1]["content"] == f"Prompt: {prompt}\n\nAbstract: {abstract}"


@pytest.mark.llm # Mark this test
@patch("requests.post")
def test_check_relevance_api_error(mock_post, groq_checker):
    """Test handling of API errors during single check."""
    mock_post.side_effect = requests.exceptions.RequestException("API connection failed")

    abstract = "Another abstract."
    prompt = "Is it relevant?"
    result = groq_checker.check_relevance(abstract, prompt)

    assert isinstance(result, LLMResponse)
    assert result.is_relevant is False
    assert result.confidence == 0.0
    assert "Error occurred: API connection failed" in result.explanation


@pytest.mark.llm # Mark this test
@patch("requests.get")
@patch("requests.post")
@patch("time.sleep", return_value=None) # Mock time.sleep to speed up test
def test_check_relevance_batch_success(mock_sleep, mock_post, mock_get, groq_checker):
    """Test successful batch relevance check."""
    # --- Mock Batch Creation (POST) ---
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {"id": "batch_123"}
    mock_post.return_value = mock_post_response

    # --- Mock Batch Status Check (GET) ---
    # First GET: still processing
    mock_get_processing = MagicMock()
    mock_get_processing.raise_for_status.return_value = None
    mock_get_processing.json.return_value = {"id": "batch_123", "status": "processing"}

    # Second GET: completed
    mock_get_completed = MagicMock()
    mock_get_completed.raise_for_status.return_value = None
    mock_get_completed.json.return_value = {
        "id": "batch_123",
        "status": "completed",
        "output_file_id": "file_abc",
    }
    # Simulate multiple calls to GET returning different statuses
    mock_get.side_effect = [mock_get_processing, mock_get_completed]

    # --- Mock File Content Retrieval (GET) ---
    # This needs a separate mock because it's a different GET call
    mock_get_content = MagicMock(spec=requests.Response) # Use spec for Response attributes
    mock_get_content.raise_for_status.return_value = None
    # Simulate the JSONL content
    result1 = {"is_relevant": True, "confidence": 0.8, "explanation": "Result 1"}
    result2 = {"is_relevant": False, "confidence": 0.3, "explanation": "Result 2"}
    content_line1 = json.dumps({"custom_id": "paper_0", "response": {"body": {"choices": [{"message": {"content": json.dumps(result1)}}]}}})
    content_line2 = json.dumps({"custom_id": "paper_1", "response": {"body": {"choices": [{"message": {"content": json.dumps(result2)}}]}}})
    mock_get_content.text = f"{content_line1}\n{content_line2}"

    # We need to carefully patch the *second* GET call to return this content mock
    # We achieve this by patching requests.get again within the test
    def get_side_effect(*args, **kwargs):
        if "/content" in args[0]:
            return mock_get_content
        elif "/batches/batch_123" in args[0]:
            # Use the existing side effect for status checks
            return mock_get.side_effect.pop(0) if mock_get.side_effect else MagicMock(status_code=404)
        else:
            return MagicMock(status_code=404) # Default for unexpected calls

    mock_get.side_effect = get_side_effect # Reset side_effect for the main mock

    # --- Execute Batch Check ---
    abstracts = ["Abstract 1", "Abstract 2"]
    prompt = "Is this relevant?"
    results = groq_checker.check_relevance_batch(abstracts, prompt)

    # --- Assertions ---
    assert len(results) == 2

    assert isinstance(results[0], LLMResponse)
    assert results[0].is_relevant is True
    assert results[0].confidence == 0.8
    assert results[0].explanation == "Result 1"

    assert isinstance(results[1], LLMResponse)
    assert results[1].is_relevant is False
    assert results[1].confidence == 0.3
    assert results[1].explanation == "Result 2"

    # Check POST call for batch creation
    mock_post.assert_called_once()
    post_call_args, post_call_kwargs = mock_post.call_args
    assert post_call_args[0] == groq_checker.base_url # Check correct base URL for batch POST
    assert len(post_call_kwargs["json"]["requests"]) == 2 # Check number of requests in batch
    assert post_call_kwargs["json"]["requests"][0]["url"] == "/v1/chat/completions"

    # Check GET calls (Status + Content)
    assert mock_get.call_count == 3 # 2 status checks + 1 content retrieval
    get_calls = mock_get.call_args_list
    assert get_calls[0][0][0] == "https://api.groq.com/v1/batches/batch_123"
    assert get_calls[1][0][0] == "https://api.groq.com/v1/batches/batch_123"
    assert get_calls[2][0][0] == "https://api.groq.com/openai/v1/files/file_abc/content"


@pytest.mark.llm # Mark this test
@patch("requests.post")
def test_check_relevance_batch_creation_error(mock_post, groq_checker):
    """Test handling of errors during batch creation POST request."""
    mock_post.side_effect = requests.exceptions.RequestException("Batch creation failed")

    abstracts = ["Abstract 1", "Abstract 2"]
    prompt = "Is it relevant?"
    results = groq_checker.check_relevance_batch(abstracts, prompt)

    assert len(results) == 2
    for result in results:
        assert isinstance(result, LLMResponse)
        assert result.is_relevant is False
        assert result.confidence == 0.0
        assert "Error occurred: Batch creation failed" in result.explanation


@pytest.mark.llm # Mark this test
@patch("requests.get")
@patch("requests.post")
@patch("time.sleep", return_value=None)
def test_check_relevance_batch_status_error(mock_sleep, mock_post, mock_get, groq_checker):
    """Test handling of errors during batch status GET request."""
    # Mock Batch Creation (POST) - Success
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {"id": "batch_error_status"}
    mock_post.return_value = mock_post_response

    # Mock Batch Status Check (GET) - Fail
    mock_get.side_effect = requests.exceptions.RequestException("Failed to get status")

    abstracts = ["Abstract 1", "Abstract 2"]
    prompt = "Is it relevant?"
    results = groq_checker.check_relevance_batch(abstracts, prompt)

    assert len(results) == 2
    for result in results:
        assert isinstance(result, LLMResponse)
        assert result.is_relevant is False
        assert result.confidence == 0.0
        assert "Error occurred: Failed to get status" in result.explanation


@pytest.mark.llm # Mark this test
@patch("requests.get")
@patch("requests.post")
@patch("time.sleep", return_value=None)
def test_check_relevance_batch_failed_status(mock_sleep, mock_post, mock_get, groq_checker):
    """Test handling when batch status comes back as 'failed'."""
    # Mock Batch Creation (POST) - Success
    mock_post_response = MagicMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {"id": "batch_failed"}
    mock_post.return_value = mock_post_response

    # Mock Batch Status Check (GET) - Returns 'failed'
    mock_get_failed = MagicMock()
    mock_get_failed.raise_for_status.return_value = None
    mock_get_failed.json.return_value = {
        "id": "batch_failed",
        "status": "failed",
        "error": "Something went wrong"
    }
    mock_get.return_value = mock_get_failed

    abstracts = ["Abstract 1", "Abstract 2"]
    prompt = "Is it relevant?"
    results = groq_checker.check_relevance_batch(abstracts, prompt)

    assert len(results) == 2
    for result in results:
        assert isinstance(result, LLMResponse)
        assert result.is_relevant is False
        assert result.confidence == 0.0
        assert "Error occurred: Batch processing failed:" in result.explanation


@pytest.mark.llm # Mark the entire class
class TestGroqChecker:
    """Tests for the GroqChecker class."""

    @patch('src.llm.groq_checker.Groq')
    def test_initialization_success(self, mock_groq):
        """Test successful initialization of GroqChecker."""
        mock_groq.return_value.chat.completions.create.side_effect = ValueError("API Key not found")
        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        assert checker.api_key == "fake_key"
        assert checker.model == "test-model"
        assert checker.relevance_criteria == "test criteria"
        mock_groq.assert_called_once_with(api_key="fake_key")

    @patch('src.llm.groq_checker.Groq')
    def test_initialization_failure(self, mock_groq):
        """Test initialization failure of GroqChecker (e.g., Groq client init fails)."""
        mock_groq.side_effect = Exception("Initialization failed")
        with pytest.raises(Exception, match="Initialization failed"):
            GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_success(self, mock_groq):
        """Test successful batch relevance checking."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ('```json\n' +
            '[{"paper_id": 0, "is_relevant": true, "reason": "Reason 1", "confidence": 0.9}, ' +
            ' {"paper_id": 1, "is_relevant": false, "reason": "Reason 2", "confidence": 0.8}]' +
            '\n```')
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([paper1, paper2])

        assert len(results) == 2
        assert results[0].is_relevant is True
        assert results[0].reason == "Reason 1"
        assert results[0].confidence == 0.9
        assert results[1].is_relevant is False
        assert results[1].reason == "Reason 2"
        assert results[1].confidence == 0.8

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_api_error(self, mock_groq):
        """Test handling of API errors during batch relevance checking."""
        mock_groq.return_value.chat.completions.create.side_effect = Exception("API Error")

        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([paper1])

        assert len(results) == 1
        assert results[0].is_relevant is False # Default to not relevant on error
        assert results[0].confidence == 0.0
        assert "Error occurred during LLM relevance check: API Error" in results[0].explanation

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_parsing_error(self, mock_groq):
        """Test handling of parsing errors in API response."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'invalid json'
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([paper1])

        assert len(results) == 1
        assert results[0].is_relevant is False
        assert results[0].confidence == 0.0
        assert "Failed to parse LLM response" in results[0].explanation

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_partial_parsing_error(self, mock_groq):
        """Test handling of partial parsing errors in API response."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ('```json\n' +
            '[{"paper_id": 0, "is_relevant": true, "reason": "Reason 1", "confidence": 0.9}, ' +
            ' {"paper_id": 1, "reason": "Reason 2", "confidence": 0.8}]' + # Missing is_relevant
            '\n```')
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([paper1, paper2])

        assert len(results) == 2
        # First paper should be parsed correctly
        assert results[0].is_relevant is True
        assert results[0].reason == "Reason 1"
        assert results[0].confidence == 0.9
        # Second paper should indicate a parsing error due to missing key
        assert results[1].is_relevant is False
        assert results[1].confidence == 0.0
        assert "Error parsing response item for paper_id 1: Missing key 'is_relevant'" in results[1].explanation

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_empty_input(self, mock_groq):
        """Test batch relevance checking with an empty list of papers."""
        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([])
        assert len(results) == 0
        mock_groq.return_value.chat.completions.create.assert_not_called()

    @patch('src.llm.groq_checker.Groq')
    def test_check_relevance_batch_unexpected_response_format(self, mock_groq):
        """Test handling of unexpected response formats from the API."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"message": "unexpected format"}'
        mock_groq.return_value.chat.completions.create.return_value = mock_response

        checker = GroqChecker(api_key="fake_key", model="test-model", relevance_criteria="test criteria")
        results = checker.check_relevance_batch([paper1])

        assert len(results) == 1
        assert results[0].is_relevant is False
        assert results[0].confidence == 0.0
        assert "LLM response is not a list or could not be parsed" in results[0].explanation
