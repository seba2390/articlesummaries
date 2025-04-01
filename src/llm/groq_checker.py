"""Groq implementation of LLM-based relevance checking."""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests

from .base_checker import BaseLLMChecker, LLMResponse


class GroqChecker(BaseLLMChecker):
    """Concrete implementation using Groq's API."""

    def __init__(self, api_key: str):
        """Initialize the Groq checker.

        Args:
            api_key: Groq API key for authentication
        """
        self.api_key = api_key
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        # Using llama-3.1-8b-instant as it has good rate limits (30 RPM, 14,400 RPD)
        self.model = "llama-3.1-8b-instant"

    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Check relevance using Groq's API.

        Args:
            abstract: The paper's abstract text
            prompt: The prompt to use for relevance checking

        Returns:
            LLMResponse containing relevance decision, confidence, and explanation
        """
        messages = [
            {
                "role": "system",
                "content": "You are a paper relevance checker. Your task is to determine if a paper is relevant based on its abstract and a given prompt. Respond with a JSON object containing 'is_relevant' (boolean), 'confidence' (float between 0 and 1), and 'explanation' (string explaining your decision).",
            },
            {"role": "user", "content": f"Prompt: {prompt}\n\nAbstract: {abstract}"},
        ]

        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3,  # Lower temperature for more consistent results
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()

            # Parse the LLM's response
            result = json.loads(response.json()["choices"][0]["message"]["content"])
            return LLMResponse(
                is_relevant=result["is_relevant"], confidence=result["confidence"], explanation=result["explanation"]
            )

        except Exception as e:
            # Log the error and return a default response
            print(f"Error checking relevance with Groq: {e}")
            return LLMResponse(is_relevant=False, confidence=0.0, explanation=f"Error occurred: {str(e)}")

    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Process multiple abstracts in a single batch request.

        Args:
            abstracts: List of paper abstracts to check
            prompt: The prompt to use for relevance checking

        Returns:
            List of LLMResponse objects, one for each abstract
        """
        # Prepare batch requests
        requests_data = []
        for i, abstract in enumerate(abstracts):
            request = {
                "custom_id": f"paper_{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a paper relevance checker. Your task is to determine if a paper is relevant based on its abstract and a given prompt. Respond with a JSON object containing 'is_relevant' (boolean), 'confidence' (float between 0 and 1), and 'explanation' (string explaining your decision).",
                        },
                        {"role": "user", "content": f"Prompt: {prompt}\n\nAbstract: {abstract}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
            }
            requests_data.append(request)

        # Submit batch request
        try:
            response = requests.post(self.base_url, headers=self.headers, json={"requests": requests_data})
            response.raise_for_status()
            batch_id = response.json()["id"]

            # Wait for batch completion and get results
            results = self._wait_for_batch_completion(batch_id)

            # Parse results
            responses = []
            for result in results:
                parsed = json.loads(result["response"]["body"]["choices"][0]["message"]["content"])
                responses.append(
                    LLMResponse(
                        is_relevant=parsed["is_relevant"],
                        confidence=parsed["confidence"],
                        explanation=parsed["explanation"],
                    )
                )

            return responses

        except Exception as e:
            print(f"Error in batch processing: {e}")
            return [LLMResponse(is_relevant=False, confidence=0.0, explanation=f"Error occurred: {str(e)}")] * len(
                abstracts
            )

    def _wait_for_batch_completion(self, batch_id: str, timeout_minutes: int = 60) -> List[Dict[str, Any]]:
        """Wait for batch completion and retrieve results.

        Args:
            batch_id: ID of the batch request
            timeout_minutes: Maximum time to wait for completion

        Returns:
            List of results from the batch processing

        Raises:
            TimeoutError: If batch processing takes longer than timeout_minutes
        """
        start_time = datetime.now()
        timeout = timedelta(minutes=timeout_minutes)

        while datetime.now() - start_time < timeout:
            response = requests.get(f"{self.base_url}/{batch_id}", headers=self.headers)
            response.raise_for_status()
            status = response.json()

            if status["status"] == "completed":
                # Get results from output file
                output_file_id = status["output_file_id"]
                output_response = requests.get(
                    f"https://api.groq.com/openai/v1/files/{output_file_id}/content", headers=self.headers
                )
                output_response.raise_for_status()

                # Parse JSONL results
                results = []
                for line in output_response.text.strip().split("\n"):
                    results.append(json.loads(line))
                return results

            elif status["status"] in ["failed", "expired", "cancelled"]:
                raise Exception(f"Batch processing {status['status']}: {status.get('error', 'Unknown error')}")

            # Wait before checking again
            time.sleep(5)

        raise TimeoutError("Batch processing timed out")
