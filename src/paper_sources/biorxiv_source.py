"""Implementation of the paper source fetching papers from the bioRxiv/medRxiv API."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests
from requests.exceptions import RequestException
from tqdm import tqdm

from src.paper import Paper
from src.paper_sources.base_source import BasePaperSource

logger = logging.getLogger(__name__)


class BiorxivSource(BasePaperSource):
    """Fetches paper information from the bioRxiv/medRxiv API.

    Implements the `BasePaperSource` interface to retrieve papers from bioRxiv or medRxiv
    based on specific categories and a defined date range.
    Uses the `requests` library for API interaction and `tqdm` for progress indication.
    API Documentation: https://api.biorxiv.org/
    """

    DEFAULT_FETCH_WINDOW_DAYS = 1
    BASE_API_URL = "https://api.biorxiv.org/details"
    MAX_RESULTS_PER_PAGE = 100  # bioRxiv API serves 100 results per page

    def __init__(self):
        """Initializes BiorxivSource with default values."""
        self.server: str = "biorxiv"  # Default server
        self.categories: List[str] = []
        # Use the default from BasePaperSource, will be overridden by configure
        self.fetch_window_days: int = self.DEFAULT_FETCH_WINDOW_DAYS

    def configure(self, config: Dict[str, Any]):
        """Configures the BiorxivSource with server, categories, and fetch window.

        Reads the following keys:
          - `config['paper_source']['biorxiv']['server']`: 'biorxiv' or 'medrxiv'.
          - `config['paper_source']['biorxiv']['categories']`: List of category strings.
          - `config['paper_source']['biorxiv']['fetch_window']`: Optional override for days.
          - `config['global_fetch_window_days']`: Default fetch window.

        Args:
            config: The main application configuration dictionary.
        """
        biorxiv_config = config.get("paper_source", {}).get("biorxiv", {})

        # Configure server
        server_config = biorxiv_config.get("server", "biorxiv").lower()
        if server_config in ["biorxiv", "medrxiv"]:
            self.server = server_config
        else:
            logger.warning(f"Invalid server '{server_config}' configured for bioRxiv. Defaulting to 'biorxiv'.")
            self.server = "biorxiv"
        logger.info(f"BiorxivSource configured for server: {self.server}")

        # Configure categories
        self.categories = biorxiv_config.get("categories", [])
        if not isinstance(self.categories, list):
            logger.warning(
                f"Invalid format for bioRxiv categories: {self.categories}. Expected a list. Disabling category filtering."
            )
            self.categories = []

        if self.categories:
            logger.info(f"BiorxivSource configured for categories: {self.categories}")
        else:
            logger.info("BiorxivSource configured to fetch from all categories.")

        # Configure fetch window (priority: source-specific > global > default)
        fetch_window_source = biorxiv_config.get("fetch_window")
        fetch_window_global = config.get("global_fetch_window_days")

        chosen_fetch_window = self.DEFAULT_FETCH_WINDOW_DAYS  # Start with default

        if fetch_window_source is not None:
            try:
                fetch_window_int = int(fetch_window_source)
                if fetch_window_int > 0:
                    chosen_fetch_window = fetch_window_int
                    logger.info(f"Using source-specific fetch window: {chosen_fetch_window} days for {self.server}.")
                else:
                    logger.warning(
                        f"Source-specific fetch_window ({fetch_window_source}) for {self.server} is not positive. Checking global."
                    )
            except (ValueError, TypeError):
                logger.warning(
                    f"Source-specific fetch_window ({fetch_window_source}) for {self.server} is invalid. Checking global."
                )

        if chosen_fetch_window == self.DEFAULT_FETCH_WINDOW_DAYS and fetch_window_global is not None:
            # Only use global if source-specific wasn't set or was invalid/non-positive
            try:
                fetch_window_int = int(fetch_window_global)
                if fetch_window_int > 0:
                    chosen_fetch_window = fetch_window_int
                    logger.info(f"Using global fetch window: {chosen_fetch_window} days for {self.server}.")
                else:
                    logger.warning(
                        f"Global fetch_window ({fetch_window_global}) is not positive. Using default for {self.server}."
                    )
            except (ValueError, TypeError):
                logger.warning(
                    f"Global fetch_window ({fetch_window_global}) is invalid. Using default for {self.server}."
                )

        self.fetch_window_days = chosen_fetch_window
        if (
            self.fetch_window_days == self.DEFAULT_FETCH_WINDOW_DAYS
            and fetch_window_source is None
            and fetch_window_global is None
        ):
            logger.info(f"Using default fetch window: {self.fetch_window_days} days for {self.server}.")

    def fetch_papers(self, start_time_utc: datetime, end_time_utc: datetime) -> List[Paper]:
        """Fetches papers from the bioRxiv/medRxiv API within the given time window.

        Constructs API requests based on configured server, categories, and the provided
        date range (YYYY-MM-DD format). Handles pagination using the cursor.

        Args:
            start_time_utc: The start of the time window (inclusive, UTC).
            end_time_utc: The end of the time window (inclusive, UTC).

        Returns:
            A list of `Paper` objects fetched, or an empty list if an error occurs
            or no papers are found.
        """
        start_date_str = start_time_utc.strftime("%Y-%m-%d")
        end_date_str = end_time_utc.strftime("%Y-%m-%d")
        interval = f"{start_date_str}/{end_date_str}"

        logger.info(f"Querying {self.server} API for papers between: {start_date_str} and {end_date_str}.")

        papers: List[Paper] = []
        cursor = 0
        total_results = -1  # Initialize to indicate total is unknown
        processed_dois = set()

        # Use tqdm for progress if total results become known
        pbar = None

        while True:
            fetch_url = f"{self.BASE_API_URL}/{self.server}/{interval}/{cursor}/json"
            params = {}
            if self.categories:
                # Join categories with semicolon if multiple, handle URL encoding if necessary (requests does this)
                # API docs suggest space or underscore, let's use underscore for safety.
                category_param = ";".join(self.categories).replace(" ", "_")
                params["category"] = category_param

            logger.debug(f"Fetching URL: {fetch_url} with params: {params}")

            try:
                response = requests.get(fetch_url, params=params, timeout=30)  # Add timeout
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()

            except RequestException as e:
                logger.error(f"API request failed for {self.server}: {e}", exc_info=True)
                if pbar:
                    pbar.close()
                return []  # Return empty list on connection error
            except ValueError as e:
                logger.error(f"Failed to decode JSON response from {self.server}: {e}", exc_info=True)
                if pbar:
                    pbar.close()
                return []

            messages = data.get("messages", [{}])[0]  # API returns messages as a list
            collection = data.get("collection", [])

            # Try to get total results from the first message block
            if total_results == -1:
                total_results_raw = None  # Initialize before try block
                try:
                    # Ensure total_results is converted to int
                    total_results_raw = messages.get("total", 0)
                    total_results = int(total_results_raw)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not parse 'total' ({total_results_raw}) from API response message. Assuming 0."
                    )
                    total_results = 0  # Default to 0 if conversion fails

                logger.info(f"API reports {total_results} potential results for the interval.")
                if total_results > 0:
                    pbar = tqdm(
                        total=total_results, desc=f"Fetching {self.server} results", unit=" papers", leave=False
                    )

            if not collection:
                logger.info(f"No more results found from {self.server} at cursor {cursor}.")
                break  # Exit loop if collection is empty

            count_in_page = 0
            for item in collection:
                doi = item.get("doi")
                if not doi or doi in processed_dois:
                    continue  # Skip if no DOI or already processed

                processed_dois.add(doi)
                count_in_page += 1

                # Parse date - handle potential errors
                published_date = None
                date_str = item.get("date")
                if date_str:
                    try:
                        # Assuming date format is YYYY-MM-DD
                        published_date = datetime.strptime(date_str, "%Y-%m-%d")
                        # Add timezone info (assume UTC if not specified by API)
                        published_date = published_date.replace(tzinfo=timezone.utc)
                    except ValueError:
                        logger.warning(f"Could not parse date string: {date_str} for DOI: {doi}")

                # Construct URL
                paper_url = f"https://www.{self.server}.org/content/{doi}"

                paper = Paper(
                    id=doi,
                    title=item.get("title", "N/A"),
                    authors=item.get("authors", "N/A").split("; "),  # Authors seem semi-colon separated
                    abstract=item.get("abstract", "N/A"),
                    url=paper_url,
                    published_date=published_date,
                    source=self.server,
                    categories=[item.get("category", "N/A")],  # API seems to return one primary category
                )
                papers.append(paper)
                if pbar:
                    pbar.update(1)  # Increment progress bar for each valid paper processed

            # Update cursor for next page
            next_cursor = messages.get("cursor", 0) + messages.get("count", 0)

            # Check if we should stop pagination
            # Stop if count returned is less than max per page OR
            # if the cursor hasn't advanced (safeguard against infinite loops)
            # Stop if we've processed >= total results reported (if known)
            if (
                count_in_page < self.MAX_RESULTS_PER_PAGE
                or next_cursor <= cursor
                or (total_results != -1 and len(processed_dois) >= total_results)
            ):
                logger.debug(
                    f"Stopping pagination. Count: {count_in_page}, Next Cursor: {next_cursor}, Current Cursor: {cursor}, Processed: {len(processed_dois)}, Reported Total: {total_results}"
                )
                break

            cursor = next_cursor  # Prepare for the next fetch
            time.sleep(0.5)  # Be polite to the API

        if pbar:
            # Ensure pbar total reflects actual processed if different from initial total
            if total_results > 0 and pbar.n < total_results:
                pbar.total = pbar.n
                pbar.refresh()
            pbar.close()

        logger.info(f"-> {self.server} API fetch completed. Found {len(papers)} unique papers.")
        return papers
