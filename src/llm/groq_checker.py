"""Groq implementation of LLM-based relevance checking."""

import json
import logging
import os  # Added for potential future env var use
import time
from typing import Any, List, Optional

# Removed requests import as we will use the Groq SDK
# import requests
from groq import APIConnectionError, APIStatusError, Groq, GroqError, RateLimitError  # Import Groq SDK

# Import specific type for message params to fix linter error
from groq.types.chat.completion_create_params import ChatCompletionMessageParam

from .base_checker import BaseLLMChecker, LLMResponse

# Logger for this module
logger = logging.getLogger(__name__)

# Define a default timeout for HTTP requests (less relevant with SDK, but can keep)
DEFAULT_REQUEST_TIMEOUT = 60  # Increased timeout for potentially longer batch requests
DEFAULT_BATCH_SIZE = 10
DEFAULT_BATCH_DELAY_SECONDS = 2  # Default seconds to wait between batches


class GroqChecker(BaseLLMChecker):
    """Concrete LLM relevance checker implementation using the Groq API.

    Uses the official `groq` Python SDK to assess paper relevance.
    Processes abstracts in batches to optimize API calls and respect rate limits.

    Attributes:
        api_key: The Groq API key for authentication.
        model: The specific Groq model to use.
        client: An instance of the Groq client.
        batch_size: Number of abstracts to process per API call.
        batch_delay_seconds: Seconds to wait between batch API calls.
    """

    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        api_key: str,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        batch_delay_seconds: Optional[float] = None,  # Added parameter
    ):
        """Initializes the GroqChecker.

        Args:
            api_key: The Groq API key.
            model: The specific Groq model ID to use.
            batch_size: Number of abstracts to process per API call.
            batch_delay_seconds: Seconds to wait between batch API calls.
        """
        if not api_key:
            # This check might be redundant if create_relevance_checker already validates
            raise ValueError("Groq API key must be provided.")

        self.api_key: str = api_key
        self.model: str = model or self.DEFAULT_MODEL
        self.batch_size: int = batch_size if batch_size is not None and batch_size > 0 else DEFAULT_BATCH_SIZE
        # Use provided delay or the default
        self.batch_delay_seconds: float = (
            batch_delay_seconds
            if batch_delay_seconds is not None and batch_delay_seconds >= 0
            else DEFAULT_BATCH_DELAY_SECONDS
        )
        logger.info(f"Using batch size: {self.batch_size}, Batch delay: {self.batch_delay_seconds}s")

        # Initialize the Groq client
        try:
            self.client = Groq(api_key=self.api_key, timeout=DEFAULT_REQUEST_TIMEOUT)
            logger.info(f"Groq client initialized successfully for model: {self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}", exc_info=True)
            # Raise a more specific error or handle inability to initialize
            raise GroqError(f"Failed to initialize Groq client: {e}") from e

    @property
    def provider_name(self) -> str:
        """Returns the name of the LLM provider."""
        return "groq"

    def _create_batch_system_prompt(self, count: int) -> str:
        """Creates the system prompt instructing the LLM to return a JSON array for a batch."""
        return (
            "You are an expert research assistant assessing paper relevance for multiple abstracts. "
            "Based on the provided abstracts and relevance prompt, determine if each paper is relevant. "
            "Respond ONLY with a single JSON array where each element corresponds to an abstract in the input order. "
            f"The array must contain exactly {count} elements. "
            "Each element in the array must be a JSON object with three keys: "
            "'is_relevant' (boolean: true if relevant, false otherwise), "
            "'confidence' (float: your confidence level from 0.0 to 1.0, e.g., 0.85), and "
            "'explanation' (string: a brief justification for your decision, max 50 words)."
        )

    def _create_batch_user_message(self, abstracts: List[str], prompt: str) -> str:
        """Creates the user message containing numbered abstracts for a batch."""
        user_message = f"Relevance Prompt for all abstracts below: {prompt}\n\n---\n"
        for i, abstract in enumerate(abstracts):
            user_message += f"Abstract {i + 1}:\n{abstract}\n\n---\n"
        return user_message

    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Checks the relevance of a single paper abstract.

        This method is kept for potential direct use but batch processing
        is preferred via `check_relevance_batch`.

        Args:
            abstract: The abstract text of the paper.
            prompt: The specific user prompt defining the desired relevance focus.

        Returns:
            An LLMResponse object.
        """
        # Essentially run a batch of size 1
        batch_responses = self._process_abstract_batch([abstract], prompt)
        return batch_responses[0] if batch_responses else LLMResponse(explanation="Failed to process single abstract.")

    def _process_abstract_batch(self, abstract_batch: List[str], prompt: str) -> List[LLMResponse]:
        """Processes a single batch of abstracts through the Groq API.

        Args:
            abstract_batch: A list of abstracts (up to self.batch_size).
            prompt: The user prompt for relevance assessment.

        Returns:
            A list of LLMResponse objects corresponding to the abstracts in the batch.
            Returns default error responses if the API call fails or parsing fails.
        """
        batch_actual_size = len(abstract_batch)
        if batch_actual_size == 0:
            return []

        system_prompt = self._create_batch_system_prompt(batch_actual_size)
        user_message = self._create_batch_user_message(abstract_batch, prompt)

        messages: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        content_str: Optional[str] = None
        try:
            logger.debug(f"Sending batch request to Groq API (model: {self.model}, size: {batch_actual_size})...")
            start_time = time.time()

            chat_completion = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.2,
                max_tokens=150 * batch_actual_size,  # Estimate max tokens needed for the JSON array
                response_format={"type": "json_object"},
            )
            duration = time.time() - start_time
            logger.debug(f"Groq API batch request completed in {duration:.2f} seconds.")

            if not chat_completion.choices:
                raise ValueError("Groq API response missing 'choices'.")
            message = chat_completion.choices[0].message
            if not message or not message.content:
                raise ValueError("Groq API response missing message content.")

            content_str = message.content
            # The response might be the list directly, or a dict containing the list
            raw_result = json.loads(content_str)

            # Check if the response is a dict containing the expected list key
            if isinstance(raw_result, dict) and "abstracts" in raw_result:
                results_list = raw_result["abstracts"]
                logger.debug("Extracted results list from 'abstracts' key in response dict.")
            elif isinstance(raw_result, list):
                results_list = raw_result  # It was already a list
            else:
                # Neither a list nor a dict with the expected key
                raise ValueError(
                    f"LLM response was not a JSON list or dict containing 'abstracts'. Got: {type(raw_result)}"
                )

            # Now validate the extracted/found list
            if not isinstance(results_list, list):  # This check might be redundant now but safe
                raise ValueError(f"Internal error: Extracted result is not a list. Got: {type(results_list)}")

            if len(results_list) != batch_actual_size:
                logger.warning(
                    f"LLM response list size ({len(results_list)}) does not match batch size "
                    f"({batch_actual_size}). Padding with errors."
                )
                # Create default error responses for the mismatch
                error_response = LLMResponse(explanation="LLM response size mismatch.")
                # Return error responses for the entire batch if size mismatch is significant?
                # Or try to use what we got and pad? Let's pad for now.
                parsed_responses = [self._parse_individual_result(res) for res in results_list]
                # Pad with errors up to batch_actual_size
                parsed_responses.extend([error_response] * (batch_actual_size - len(results_list)))
                return parsed_responses[:batch_actual_size]  # Ensure we don't exceed expected size

            # Parse each item in the list
            parsed_responses = [self._parse_individual_result(res) for res in results_list]
            return parsed_responses

        except RateLimitError as e:
            logger.error(
                f"Groq API rate limit exceeded during batch: {e}", exc_info=False
            )  # Log less verbosely for rate limits
            return [
                LLMResponse(explanation=f"Error: Groq API rate limit hit ({type(e).__name__}).")
            ] * batch_actual_size
        except APIStatusError as e:
            if e.status_code == 413:
                logger.error(f"Request for batch size {batch_actual_size} is too large for the model. {e.message}")
                logger.error(
                    f"Suggestion: Decrease 'batch_size' in config.yaml (currently {self.batch_size}) and try again."
                )
                return [
                    LLMResponse(explanation="Error: Request too large for model. Reduce batch_size.")
                ] * batch_actual_size
            else:
                # Re-raise other status errors to be caught by GroqError handler
                raise e
        except (APIConnectionError, GroqError) as e:
            logger.error(f"Groq API error during batch: {e}", exc_info=True)
            return [LLMResponse(explanation=f"Error: Groq API error ({type(e).__name__}).")] * batch_actual_size
        except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
            logger.error(f"Error parsing/validating Groq batch response: {e}", exc_info=True)
            if content_str is not None:
                logger.error(f"Problematic response content from Groq batch: {content_str}")
            return [
                LLMResponse(explanation=f"Error: Failed to parse/validate batch response ({type(e).__name__}).")
            ] * batch_actual_size
        except Exception as e:
            logger.error(f"Unexpected error processing batch with Groq: {e}", exc_info=True)
            return [LLMResponse(explanation=f"Error: Unexpected batch error ({type(e).__name__}).")] * batch_actual_size

    def _parse_individual_result(self, result_item: Any) -> LLMResponse:
        """Parses and validates a single JSON object from the batch response array."""
        if not isinstance(result_item, dict):
            logger.warning(f"Expected dict in batch result array, got {type(result_item)}.")
            return LLMResponse(explanation="Invalid item type in LLM response array.")

        try:
            # Validate structure
            if not all(k in result_item for k in ["is_relevant", "confidence", "explanation"]):
                raise ValueError("Item missing required keys.")
            if not isinstance(result_item["is_relevant"], bool):
                raise ValueError("'is_relevant' key must be a boolean.")
            if not isinstance(result_item["confidence"], (float, int)):
                raise ValueError("'confidence' key must be a number.")

            return LLMResponse(
                is_relevant=result_item["is_relevant"],
                confidence=float(result_item["confidence"]),
                explanation=str(result_item["explanation"]),
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse item in LLM response array: {e}. Item: {result_item}")
            return LLMResponse(explanation=f"Invalid item structure in LLM response array ({type(e).__name__}).")

    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Processes multiple abstracts in batches using the Groq API.

        Divides the abstracts into batches, processes each batch via a single API call,
        and combines the results. Includes delays between batches to manage rate limits.

        Args:
            abstracts: A list of abstract texts to check.
            prompt: The prompt guiding the relevance assessment for all abstracts.

        Returns:
            A list of LLMResponse objects, one for each abstract.
        """
        if not abstracts:
            return []

        total_abstracts = len(abstracts)
        logger.info(
            f"Checking relevance for {total_abstracts} abstracts in batches of {self.batch_size} "
            f"using Groq API (Delay: {self.batch_delay_seconds}s)..."
        )
        start_time_total = time.time()
        all_responses: List[LLMResponse] = []
        processed_count = 0

        for i in range(0, total_abstracts, self.batch_size):
            batch_start_index = i
            batch_end_index = min(i + self.batch_size, total_abstracts)
            abstract_batch = abstracts[batch_start_index:batch_end_index]
            batch_num = (i // self.batch_size) + 1
            total_batches = (total_abstracts + self.batch_size - 1) // self.batch_size

            logger.info(
                f"Processing batch {batch_num}/{total_batches} (Abstracts {batch_start_index + 1}-{batch_end_index})..."
            )

            batch_responses = self._process_abstract_batch(abstract_batch, prompt)
            all_responses.extend(batch_responses)
            processed_count += len(abstract_batch)

            # Check for rate limit errors specifically and wait longer if needed
            if any("RateLimitError" in resp.explanation for resp in batch_responses):
                logger.warning(f"Rate limit hit processing batch {batch_num}. Waiting longer before next batch...")
                time.sleep(10)  # Wait longer after hitting a rate limit
            # Add configured delay between batches unless it's the last one
            elif i + self.batch_size < total_abstracts:
                logger.debug(f"Waiting {self.batch_delay_seconds}s before next batch...")
                time.sleep(self.batch_delay_seconds)  # Use the instance attribute

        duration_total = time.time() - start_time_total
        # Log final count processed vs expected
        if processed_count != total_abstracts or len(all_responses) != total_abstracts:
            logger.warning(
                f"Mismatch in processed counts: Expected {total_abstracts}, Processed Count: {processed_count}, "
                f"Total Responses: {len(all_responses)}"
            )

        logger.info(f"Batch relevance check for {total_abstracts} abstracts completed in {duration_total:.2f} seconds.")
        return all_responses  # Return all collected responses

    # --- Removed old batch processing methods that used requests and /batches ---
    # _poll_batch_and_get_results
    # _fetch_results_content


# Optional: Add a main block for testing this module directly
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("Testing GroqChecker module...")

    # Requires GROQ_API_KEY environment variable to be set
    api_key_env = os.getenv("GROQ_API_KEY")
    if not api_key_env:
        logger.error("GROQ_API_KEY environment variable not set. Cannot run tests.")
    else:
        try:
            # Test with a specific batch size
            checker = GroqChecker(api_key=api_key_env, batch_size=5)

            # Test single relevance check (uses _process_abstract_batch internally)
            test_abstract_1 = "This paper introduces a novel method for accelerating quantum circuit simulation using tensor networks."
            test_prompt_1 = "Is this paper relevant to quantum circuit simulation?"
            logger.info("--- Testing Single Relevance Check (via batch method) ---")
            response_1 = checker.check_relevance(test_abstract_1, test_prompt_1)
            logger.info(f"Test Abstract 1: {test_abstract_1}")
            logger.info(
                f"Response 1: Relevant={response_1.is_relevant}, Conf={response_1.confidence:.2f}, Expl='{response_1.explanation}'"
            )

            # Test batch relevance check
            test_abstract_2 = "We discuss the impact of climate change on polar bear populations."
            test_abstract_3 = "A new algorithm for optimizing database queries using machine learning."
            test_abstract_4 = "The Hamiltonian complexity of the quantum Ising model on a lattice."
            test_abstract_5 = "Advances in protein folding prediction with AlphaFold."
            test_abstract_6 = "An unrelated abstract about culinary arts."

            test_abstracts = [
                test_abstract_1,
                test_abstract_2,
                test_abstract_3,
                test_abstract_4,
                test_abstract_5,
                test_abstract_6,
            ]
            test_prompt_batch = "Is this paper relevant to computational physics, quantum computing, or machine learning applied to science?"
            logger.info(f"--- Testing Batch Relevance Check (Size={checker.batch_size}) ---")
            responses_batch = checker.check_relevance_batch(test_abstracts, test_prompt_batch)
            logger.info(f"Test Prompt: {test_prompt_batch}")
            if len(responses_batch) == len(test_abstracts):
                for i, resp in enumerate(responses_batch):
                    logger.info(
                        f"  Abstract {i + 1}: Relevant={resp.is_relevant}, Conf={resp.confidence:.2f}, Expl='{resp.explanation}'"
                    )
            else:
                logger.error(f"Batch test failed: Expected {len(test_abstracts)} responses, got {len(responses_batch)}")
                for i, resp in enumerate(responses_batch):
                    logger.info(
                        f"  Response {i + 1}: Relevant={resp.is_relevant}, Conf={resp.confidence:.2f}, Expl='{resp.explanation}'"
                    )

        except GroqError as ge:
            logger.error(f"Test failed due to Groq API error: {ge}")
        except Exception as e:
            logger.error(f"Test failed due to unexpected error: {e}", exc_info=True)
