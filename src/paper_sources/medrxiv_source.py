"""Implementation of the paper source fetching papers from the medRxiv API."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException
from tqdm import tqdm

from src.paper import Paper
from src.paper_sources.base_source import BasePaperSource

logger = logging.getLogger(__name__)


class MedrxivSource(BasePaperSource):
    """Fetches paper information from the medRxiv API.

    Uses the bioRxiv API endpoint configured for the medRxiv server.
    Implements the `BasePaperSource` interface to retrieve papers from medRxiv
    based on specific categories and a defined date range.
    Uses the `requests` library for API interaction and `tqdm` for progress indication.
    API Documentation: https://api.biorxiv.org/
    """

    DEFAULT_FETCH_WINDOW_DAYS = 1
    BASE_API_URL = "https://api.biorxiv.org/details"
    MAX_RESULTS_PER_PAGE = 100  # API serves 100 results per page
    SERVER_NAME = "medrxiv"  # Hardcoded for this source
    DEFAULT_MAX_TOTAL_RESULTS = None  # Default to no limit for this source

    def __init__(self):
        """Initializes MedrxivSource with default values."""
        self.categories: List[str] = []
        self.fetch_window_days: int = self.DEFAULT_FETCH_WINDOW_DAYS
        self.max_total_results: Optional[int] = self.DEFAULT_MAX_TOTAL_RESULTS  # Added attribute
        logger.info(f"MedrxivSource initialized for server: {self.SERVER_NAME}")

    def configure(self, config: Dict[str, Any], source_name: str):
        """Configures the MedrxivSource with categories and fetch window.

        Reads the following keys:
          - `config['paper_source']['medrxiv']['categories']`: List of category strings.
          - `config['paper_source']['medrxiv']['fetch_window']`: Optional override for days.
          - `config['global_fetch_window_days']`: Default fetch window.

        Args:
            config: The main application configuration dictionary.
            source_name: The identifier for this source (should be 'medrxiv').
        """
        # Use source_name to get the specific config block
        medrxiv_config = config.get("paper_source", {}).get(source_name, {})
        if not medrxiv_config:
            logger.warning(f"No configuration found for source '{source_name}' under 'paper_source'. Using defaults.")

        # Configure categories
        self.categories = medrxiv_config.get("categories", [])
        if not isinstance(self.categories, list):
            logger.warning(
                f"Invalid format for medRxiv categories: {self.categories}. Expected a list. Disabling category filtering."
            )
            self.categories = []

        if self.categories:
            logger.info(f"MedrxivSource configured for categories: {self.categories}")
        else:
            logger.info("MedrxivSource configured to fetch from all categories.")

        # Configure fetch window (priority: source-specific > global > default)
        fetch_window_source = medrxiv_config.get("fetch_window")
        # fetch_window_global = config.get("global_fetch_window_days") # Removed

        chosen_fetch_window = self.DEFAULT_FETCH_WINDOW_DAYS  # Start with default

        if fetch_window_source is not None:
            try:
                fetch_window_int = int(fetch_window_source)
                if fetch_window_int > 0:
                    chosen_fetch_window = fetch_window_int
                    logger.info(
                        f"Using source-specific fetch window: {chosen_fetch_window} days for {self.SERVER_NAME}."
                    )
                else:
                    logger.warning(
                        # f"Source-specific fetch_window ({fetch_window_source}) for {self.SERVER_NAME} is not positive. Checking global."
                        f"Source-specific fetch_window ({fetch_window_source}) for {self.SERVER_NAME} is not positive. Using default."
                    )
            except (ValueError, TypeError):
                logger.warning(
                    # f"Source-specific fetch_window ({fetch_window_source}) for {self.SERVER_NAME} is invalid. Checking global."
                    f"Source-specific fetch_window ({fetch_window_source}) for {self.SERVER_NAME} is invalid. Using default."
                )

        self.fetch_window_days = chosen_fetch_window
        if chosen_fetch_window == self.DEFAULT_FETCH_WINDOW_DAYS and fetch_window_source is None:
            logger.info(
                f"No specific fetch_window found for {self.SERVER_NAME}. Using default: {self.fetch_window_days} days."
            )

        # Read max_total_results from the top-level config, allow None
        max_results_config = config.get("max_total_results", self.DEFAULT_MAX_TOTAL_RESULTS)
        if max_results_config is not None:
            try:
                max_results_int = int(max_results_config)
                if max_results_int > 0:
                    self.max_total_results = max_results_int
                    logger.info(f"Maximum total results for {self.SERVER_NAME} set to: {self.max_total_results}")
                else:
                    logger.warning(
                        f"Configured max_total_results ({max_results_config}) is not positive. Disabling limit for {self.SERVER_NAME}."
                    )
                    self.max_total_results = self.DEFAULT_MAX_TOTAL_RESULTS
            except (ValueError, TypeError):
                logger.warning(
                    f"Configured max_total_results ({max_results_config}) is invalid. Disabling limit for {self.SERVER_NAME}."
                )
                self.max_total_results = self.DEFAULT_MAX_TOTAL_RESULTS
        else:
            logger.info(f"No max_total_results limit applied for {self.SERVER_NAME}.")

    def fetch_papers(self, start_time_utc: datetime, end_time_utc: datetime) -> List[Paper]:
        """Fetches papers from the medRxiv API within the given time window.

        Constructs API requests based on configured categories and the provided
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

        logger.info(f"Querying {self.SERVER_NAME} API for papers between: {start_date_str} and {end_date_str}.")

        papers: List[Paper] = []
        cursor = 0
        total_results = -1  # Initialize to indicate total is unknown
        processed_dois = set()
        papers_collected_count = 0  # Track papers collected to check against limit

        # Use tqdm for progress if total results become known
        pbar = None
        limit_reached = False  # Flag to signal breaking the outer loop

        while True:
            # Check if limit has been reached *before* fetching next page
            if self.max_total_results is not None and papers_collected_count >= self.max_total_results:
                logger.info(
                    f"Reached max_total_results limit ({self.max_total_results}). Stopping fetch for {self.SERVER_NAME}."
                )
                break

            fetch_url = f"{self.BASE_API_URL}/{self.SERVER_NAME}/{interval}/{cursor}/json"
            params = {}
            if self.categories:
                # Join categories with semicolon if multiple, handle URL encoding if necessary (requests does this)
                # API docs suggest space or underscore, let's use underscore for safety.
                # Example: "Addiction Medicine", "Allergy and Immunology" -> "Addiction_Medicine;Allergy_and_Immunology"
                category_param = ";".join([cat.replace(" ", "_") for cat in self.categories])
                params["category"] = category_param

            logger.debug(f"Fetching URL: {fetch_url} with params: {params}")

            try:
                response = requests.get(fetch_url, params=params, timeout=30)  # Add timeout
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                data = response.json()

            except RequestException as e:
                logger.error(f"API request failed for {self.SERVER_NAME}: {e}", exc_info=True)
                if pbar:
                    pbar.close()
                return []  # Return empty list on connection error
            except ValueError as e:  # Catches JSONDecodeError
                logger.error(f"Failed to decode JSON response from {self.SERVER_NAME}: {e}", exc_info=True)
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
                        total=total_results, desc=f"Fetching {self.SERVER_NAME} results", unit=" papers", leave=False
                    )

            if not collection:
                logger.info(f"No more results found from {self.SERVER_NAME} at cursor {cursor}.")
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
                paper_url = f"https://www.{self.SERVER_NAME}.org/content/{doi}"

                paper = Paper(
                    id=doi,
                    title=item.get("title", "N/A"),
                    authors=item.get("authors", "N/A").split("; "),  # Authors seem semi-colon separated
                    abstract=item.get("abstract", "N/A"),
                    url=paper_url,
                    published_date=published_date,
                    source=self.SERVER_NAME,
                    categories=[item.get("category", "N/A")],  # API seems to return one primary category
                )
                papers.append(paper)
                papers_collected_count += 1  # Increment collected count
                if pbar:
                    pbar.update(1)  # Increment progress bar for each valid paper processed

            # Stop processing this page if limit reached
            if self.max_total_results is not None and papers_collected_count >= self.max_total_results:
                logger.info(
                    f"Reached max_total_results limit ({self.max_total_results}) within page. Stopping processing for {self.SERVER_NAME}."
                )
                limit_reached = True  # Set the flag
                break  # Break inner loop (page processing)

            # After processing the page, check if the limit was reached
            if limit_reached:
                break  # Break outer loop (pagination)

            # Update cursor for next page
            # Ensure cursor and count are treated as integers
            try:
                current_cursor_val = int(messages.get("cursor", 0))
                count_val = int(messages.get("count", 0))
                next_cursor = current_cursor_val + count_val
            except (ValueError, TypeError) as e:
                logger.error(
                    f"Error converting cursor/count to int: {e}. Response messages: {messages}. Stopping pagination."
                )
                break  # Stop pagination if values are invalid

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
                    f"Stopping pagination for {self.SERVER_NAME}. Reason: "
                    f"count_in_page ({count_in_page}) < MAX ({self.MAX_RESULTS_PER_PAGE}) or "
                    f"next_cursor ({next_cursor}) <= cursor ({cursor}) or "
                    f"processed ({len(processed_dois)}) >= total ({total_results})."
                )
                break  # Exit loop after processing the current page

            cursor = next_cursor
            # Optional: Add a small delay between pages if needed
            # time.sleep(0.1)

        if pbar:
            # Ensure the progress bar closes cleanly, especially if total was estimated
            pbar.n = len(processed_dois)  # Set final count
            pbar.close()

        # Truncate list if limit was applied and exceeded
        if self.max_total_results is not None and len(papers) > self.max_total_results:
            logger.info(f"Truncating fetched papers list from {len(papers)} to {self.max_total_results} due to limit.")
            papers = papers[: self.max_total_results]

        logger.info(
            f"✅ Finished fetching from {self.SERVER_NAME}. Total unique papers processed: {len(papers)}."
        )  # Log final count after potential truncation
        return papers
