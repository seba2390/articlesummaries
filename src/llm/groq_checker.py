"""Groq implementation of LLM-based relevance checking."""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from .base_checker import BaseLLMChecker, LLMResponse

# Logger for this module
logger = logging.getLogger(__name__)

# Define a default timeout for HTTP requests
DEFAULT_REQUEST_TIMEOUT = 30  # seconds


class GroqChecker(BaseLLMChecker):
    """Concrete LLM relevance checker implementation using the Groq API.

    This class interacts with the Groq API (specifically the OpenAI-compatible
    chat completions endpoint) to assess paper relevance based on abstracts.
    It supports both single and batch processing of abstracts.

    Attributes:
        api_key: The Groq API key for authentication.
        model: The specific Groq model to use (defaults to llama-3.1-8b-instant).
        relevance_criteria: Optional string describing the relevance criteria,
                            used in the system prompt.
        base_url: The base URL for the Groq chat completions API endpoint.
        headers: Standard headers including Authorization for API requests.
    """

    DEFAULT_MODEL = "llama-3.1-8b-instant"  # Known fast and capable model
    BASE_API_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str, model: Optional[str] = None, relevance_criteria: Optional[str] = None):
        """Initializes the GroqChecker.

        Args:
            api_key: The Groq API key.
            model: The specific Groq model ID to use (e.g., 'mixtral-8x7b-32768').
                   Defaults to `DEFAULT_MODEL` if None.
            relevance_criteria: Optional description of relevance criteria to include
                                in the system prompt for the LLM.
        """
        if not api_key:
            raise ValueError("Groq API key must be provided.")

        self.api_key: str = api_key
        self.model: str = model or self.DEFAULT_MODEL
        self.relevance_criteria: str = (
            relevance_criteria or "Determine relevance based on general scientific interest and potential impact."
        )
        self.base_url: str = f"{self.BASE_API_URL}/chat/completions"
        self.batch_url: str = f"{self.BASE_API_URL}/batches"
        self.files_url: str = f"{self.BASE_API_URL}/files"
        self.headers: Dict[str, str] = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        logger.info(f"GroqChecker initialized with model: {self.model}")

    def _create_system_prompt(self) -> str:
        """Creates the system prompt including relevance criteria."""
        return (
            "You are an expert research assistant assessing paper relevance. "
            "Based on the provided abstract and relevance prompt, determine if the paper is relevant. "
            f"Relevance Criteria: {self.relevance_criteria}\n\n"
            "Respond ONLY with a single JSON object containing three keys: "
            "'is_relevant' (boolean: true if relevant, false otherwise), "
            "'confidence' (float: your confidence level from 0.0 to 1.0), and "
            "'explanation' (string: a brief justification for your decision, max 50 words)."
        )

    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Checks the relevance of a single paper abstract using the Groq chat completions API.

        Args:
            abstract: The abstract text of the paper.
            prompt: The specific user prompt defining the desired relevance focus.

        Returns:
            An LLMResponse object. On error, returns a default LLMResponse
            indicating failure, with the error message in the explanation.
        """
        system_prompt = self._create_system_prompt()
        user_message = f"Relevance Prompt: {prompt}\n\nAbstract: {abstract}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,  # Low temperature for consistent JSON output
            "max_tokens": 150,  # Max tokens for the JSON response + explanation
            "response_format": {"type": "json_object"},  # Request JSON output
        }

        content_str: Optional[str] = None
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            # Extract and parse the JSON response from the LLM
            response_data = response.json()
            content_str = response_data["choices"][0]["message"]["content"]

            # Explicitly check type before loading to satisfy linter
            if content_str is None:
                raise ValueError("Extracted content string is unexpectedly None after assignment.")

            result = json.loads(content_str)

            # Basic validation of the received JSON structure
            if not all(k in result for k in ["is_relevant", "confidence", "explanation"]):
                raise ValueError("LLM response missing required keys.")
            if not isinstance(result["is_relevant"], bool):
                raise ValueError("'is_relevant' key must be a boolean.")
            if not isinstance(result["confidence"], (float, int)):
                raise ValueError("'confidence' key must be a number.")

            return LLMResponse(
                is_relevant=result["is_relevant"],
                confidence=float(result["confidence"]),
                explanation=result["explanation"],
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request error checking relevance with Groq: {e}", exc_info=True)
            return LLMResponse(
                is_relevant=False,
                confidence=0.0,
                explanation=f"Error occurred: Network or API request failed ({type(e).__name__})",
            )
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.error(f"Error parsing or validating Groq LLM response: {e}", exc_info=True)
            if content_str is not None:
                logger.error(f"Problematic response content: {content_str}")
            return LLMResponse(
                is_relevant=False,
                confidence=0.0,
                explanation=f"Error occurred: Failed to parse or validate LLM response ({type(e).__name__}).",
            )
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error checking relevance with Groq: {e}", exc_info=True)
            return LLMResponse(
                is_relevant=False,
                confidence=0.0,
                explanation=f"Error occurred: An unexpected error occurred ({type(e).__name__}).",
            )

    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Processes multiple abstracts using the Groq Batch API.

        Constructs a batch request, submits it, polls for completion,
        retrieves the results, and parses them into LLMResponse objects.

        Args:
            abstracts: A list of abstract texts to check.
            prompt: The prompt guiding the relevance assessment for all abstracts.

        Returns:
            A list of LLMResponse objects, one for each abstract. If the batch
            fails entirely, returns a list of default failure responses.
            If individual items fail parsing, they get a failure response.
        """
        if not abstracts:
            return []

        logger.info(f"Preparing Groq batch request for {len(abstracts)} abstracts...")
        system_prompt = self._create_system_prompt()

        # Create individual requests for the batch payload
        requests_data = []
        for i, abstract in enumerate(abstracts):
            user_message = f"Relevance Prompt: {prompt}\n\nAbstract: {abstract}"
            request_body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.2,
                "max_tokens": 150,
                "response_format": {"type": "json_object"},
            }
            requests_data.append({
                "custom_id": f"req_{i}",  # Custom ID to map results back
                "method": "POST",
                "url": "/v1/chat/completions",  # Relative URL for batch API
                "body": request_body,
            })

        # Submit the batch request
        batch_payload = {
            "input_file_id": None,  # We are providing data directly
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",  # Default completion window
            "requests": requests_data,  # Include requests directly (Groq feature)
        }

        batch_id = None
        try:
            logger.info(f"Submitting batch request to {self.batch_url}...")
            response = requests.post(
                self.batch_url, headers=self.headers, json=batch_payload, timeout=DEFAULT_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            batch_info = response.json()
            batch_id = batch_info.get("id")
            if not batch_id:
                raise ValueError("Batch ID not found in Groq API response.")
            logger.info(f"Groq batch request submitted successfully. Batch ID: {batch_id}")

            # Wait for completion and retrieve results file content
            results_content = self._poll_batch_and_get_results(batch_id)
            logger.info(f"Batch {batch_id} completed. Processing {len(results_content)} results...")

            # --- Parse Results ---
            # Initialize results with default failure responses
            parsed_responses: Dict[str, LLMResponse] = {}

            for line_data in results_content:
                custom_id = line_data.get("custom_id")
                response_body = line_data.get("response", {}).get("body")
                error_body = line_data.get("error")  # Check for per-request errors

                content_str: Optional[str] = None
                if not custom_id:
                    logger.warning(f"Skipping result line with missing custom_id in batch {batch_id}.")
                    continue

                if error_body:
                    err_msg = error_body.get("message", "Unknown error")
                    logger.warning(f"Request {custom_id} in batch {batch_id} failed: {err_msg}")
                    parsed_responses[custom_id] = LLMResponse(explanation=f"Request failed in batch: {err_msg}")
                    continue

                if not response_body:
                    logger.warning(
                        f"Skipping result line with missing response body for {custom_id} in batch {batch_id}."
                    )
                    parsed_responses[custom_id] = LLMResponse(explanation="Missing response body in batch result.")
                    continue

                try:
                    content_str = response_body["choices"][0]["message"]["content"]

                    # Explicitly check type before loading to satisfy linter
                    if content_str is None:
                        raise ValueError("Extracted content string is unexpectedly None after assignment.")

                    result = json.loads(content_str)

                    # Validate the parsed JSON
                    if not all(k in result for k in ["is_relevant", "confidence", "explanation"]):
                        raise ValueError("LLM response missing required keys.")
                    if not isinstance(result["is_relevant"], bool):
                        raise ValueError("'is_relevant' key must be a boolean.")
                    if not isinstance(result["confidence"], (float, int)):
                        raise ValueError("'confidence' key must be a number.")

                    # Store the successful response
                    parsed_responses[custom_id] = LLMResponse(
                        is_relevant=result["is_relevant"],
                        confidence=float(result["confidence"]),
                        explanation=result["explanation"],
                    )
                except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
                    logger.warning(f"Error parsing/validating response for {custom_id} in batch {batch_id}: {e}")
                    if content_str is not None:
                        logger.warning(f"Problematic content for {custom_id}: {content_str}")
                    parsed_responses[custom_id] = LLMResponse(
                        explanation=f"Failed to parse/validate LLM response ({type(e).__name__})."
                    )

            # Map results back to the original order using custom_id
            final_results = [
                parsed_responses.get(f"req_{i}", LLMResponse(explanation="Result missing in batch output."))
                for i in range(len(abstracts))
            ]
            return final_results

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error during batch processing (Batch ID: {batch_id}): {e}", exc_info=True)
            return [
                LLMResponse(explanation=f"Batch processing failed: Network or API request error ({type(e).__name__}).")
            ] * len(abstracts)
        except Exception as e:
            # Catch errors during polling, result fetching, or general logic
            logger.error(f"Unexpected error during batch processing (Batch ID: {batch_id}): {e}", exc_info=True)
            return [LLMResponse(explanation=f"Batch processing failed: Unexpected error ({type(e).__name__}).")] * len(
                abstracts
            )

    def _poll_batch_and_get_results(
        self, batch_id: str, poll_interval_sec: int = 5, timeout_minutes: int = 10
    ) -> List[Dict[str, Any]]:
        """Polls the Groq Batch API for completion status and retrieves results.

        Args:
            batch_id: The ID of the submitted batch request.
            poll_interval_sec: How often to check the batch status (in seconds).
            timeout_minutes: Maximum time to wait for the batch to complete.

        Returns:
            A list of dictionaries, where each dictionary represents a line
            from the JSONL output file containing the result for a single request.

        Raises:
            TimeoutError: If the batch does not complete within the timeout period.
            Exception: If the batch fails, is cancelled, or expires, or if there are
                       HTTP errors during polling or result fetching.
        """
        start_time = datetime.now()
        timeout_delta = timedelta(minutes=timeout_minutes)
        batch_status_url = f"{self.batch_url}/{batch_id}"

        logger.info(f"Polling batch status for {batch_id} every {poll_interval_sec}s (Timeout: {timeout_minutes}m)...")

        while datetime.now() - start_time < timeout_delta:
            try:
                response = requests.get(batch_status_url, headers=self.headers, timeout=DEFAULT_REQUEST_TIMEOUT)
                response.raise_for_status()
                status_data = response.json()
                current_status = status_data.get("status")

                logger.debug(f"Batch {batch_id} status: {current_status}")

                if current_status == "completed":
                    logger.info(f"Batch {batch_id} completed. Retrieving results file...")
                    output_file_id = status_data.get("output_file_id")
                    if not output_file_id:
                        raise ValueError("Batch completed but no output_file_id found.")

                    # Retrieve the content of the results file
                    results_content_url = f"{self.files_url}/{output_file_id}/content"
                    results_response = requests.get(
                        results_content_url, headers=self.headers, timeout=DEFAULT_REQUEST_TIMEOUT
                    )
                    results_response.raise_for_status()

                    # Parse the JSONL content (one JSON object per line)
                    results_list = []
                    for line in results_response.text.strip().split("\n"):
                        if line:
                            try:
                                results_list.append(json.loads(line))
                            except json.JSONDecodeError as json_e:
                                logger.warning(
                                    f"Failed to parse line in results file for batch {batch_id}: {json_e}. Line: '{line}'"
                                )
                    logger.info(f"Successfully retrieved and parsed {len(results_list)} results for batch {batch_id}.")
                    return results_list

                elif current_status in ["failed", "expired", "cancelled"]:
                    error_details = status_data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Batch {batch_id} processing {current_status}: {error_details}")
                    raise Exception(f"Batch {batch_id} {current_status}: {error_details}")
                elif current_status == "validating":
                    logger.debug(f"Batch {batch_id} is validating input...")
                elif current_status == "in_progress":
                    logger.debug(f"Batch {batch_id} is in progress...")
                # Add other potential statuses if needed (e.g., 'queued')

            except requests.exceptions.RequestException as e:
                # Handle transient network errors during polling differently?
                # For now, log and potentially raise to signal batch failure.
                logger.error(f"HTTP error polling status for batch {batch_id}: {e}")
                raise  # Re-raise to be caught by the caller

            # Wait before the next poll
            time.sleep(poll_interval_sec)

        # If the loop finishes without returning, it timed out
        logger.error(f"Batch {batch_id} processing timed out after {timeout_minutes} minutes.")
        raise TimeoutError(f"Groq batch processing for {batch_id} timed out after {timeout_minutes} minutes.")
