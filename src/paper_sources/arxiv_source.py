"""Implementation of the paper source fetching papers from the arXiv API."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import arxiv
from tqdm import tqdm

from src.paper import Paper
from src.paper_sources.base_source import BasePaperSource

logger = logging.getLogger(__name__)


class ArxivSource(BasePaperSource):
    """Fetches paper information from the arXiv API.

    Implements the `BasePaperSource` interface to retrieve papers from arXiv
    based on specific categories and a defined date range (papers updated
    or submitted on the previous calendar day in UTC).
    Uses the `arxiv` library for API interaction and `tqdm` for progress indication.
    """

    DEFAULT_MAX_RESULTS = 500  # Default limit if not specified in config
    DEFAULT_FETCH_WINDOW_DAYS = 1  # Default days to look back if not specified or invalid

    def __init__(self):
        """Initializes ArxivSource with empty categories and default max results."""
        self.categories: List[str] = []
        self.max_total_results: int = self.DEFAULT_MAX_RESULTS
        self.fetch_window_days: int = self.DEFAULT_FETCH_WINDOW_DAYS  # Add fetch window attribute

    def configure(self, config: Dict[str, Any]):
        """Configures the ArxivSource with categories, result limits, and fetch window.

        Reads the following keys from the provided configuration dictionary:
          - `config['paper_source']['arxiv']['categories']`: List of arXiv category strings.
          - `config['paper_source']['arxiv']['fetch_window']`: Number of days to look back for papers.
          - `config['max_total_results']`: Maximum number of results to request from the API per run.

        Args:
            config: The main application configuration dictionary.
        """
        # Read categories and fetch window from the nested structure
        arxiv_config = config.get("paper_source", {}).get("arxiv", {})
        self.categories = arxiv_config.get("categories", [])

        # Read fetch_window, validate, and store
        fetch_window_config = arxiv_config.get("fetch_window", self.DEFAULT_FETCH_WINDOW_DAYS)
        try:
            fetch_window_int = int(fetch_window_config)
            if fetch_window_int > 0:
                self.fetch_window_days = fetch_window_int
                logger.info(f"Fetch window configured to {self.fetch_window_days} days.")
            else:
                logger.warning(
                    f"Configured fetch_window ({fetch_window_config}) is not a positive integer. "
                    f"Using default: {self.DEFAULT_FETCH_WINDOW_DAYS} days."
                )
                self.fetch_window_days = self.DEFAULT_FETCH_WINDOW_DAYS
        except (ValueError, TypeError):
            logger.warning(
                f"Configured fetch_window ({fetch_window_config}) is not a valid integer. "
                f"Using default: {self.DEFAULT_FETCH_WINDOW_DAYS} days."
            )
            self.fetch_window_days = self.DEFAULT_FETCH_WINDOW_DAYS

        # Read max_total_results from the top-level config
        self.max_total_results = config.get("max_total_results", self.DEFAULT_MAX_RESULTS)

        # Log warnings or info based on configuration
        if not self.categories:
            logger.warning(
                "ArxivSource configured with no categories specified in config['paper_source']['arxiv']['categories']. "
                "No papers will be fetched."
            )
        else:
            logger.info(f"ArxivSource configured for categories: {self.categories}")
        logger.info(f"Maximum total results to fetch per run (max_total_results): {self.max_total_results}")

    def fetch_papers(self, start_time_utc: datetime, end_time_utc: datetime) -> List[Paper]:
        """Fetches papers from arXiv that were last updated within the given time window.

        Constructs an arXiv API query based on configured categories and the provided date range
        (in UTC). Uses the `arxiv` library to perform the search and converts the results
        into a list of `Paper` objects.

        Args:
            start_time_utc: The start of the time window (inclusive, UTC).
            end_time_utc: The end of the time window (inclusive, UTC).

        Returns:
            A list of `Paper` objects fetched from arXiv, or an empty list if no
            categories are configured or an error occurs.
        """
        # Return early if no categories are configured to search
        if not self.categories:
            logger.info("Skipping arXiv fetch: No categories configured.")
            return []

        # --- Use provided Date Range ---
        # Format dates for the arXiv API query string (YYYYMMDDHHMMSS)
        start_str = start_time_utc.strftime("%Y%m%d%H%M%S")
        end_str = end_time_utc.strftime("%Y%m%d%H%M%S")

        # Construct the date part of the query
        date_query = f"lastUpdatedDate:[{start_str} TO {end_str}]"
        logger.info(
            f"Querying arXiv for papers last updated between: "
            f"{start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC and "
            f"{end_time_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC."
        )

        # --- Construct Full Query ---
        # Combine category queries with OR
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        # Combine category and date queries with AND
        search_query = f"({category_query}) AND {date_query}"
        logger.debug(f"Constructed arXiv API query: {search_query}")

        logger.info(f"Fetching up to {self.max_total_results} papers from arXiv for the specified date range...")
        fetch_start_time = time.time()  # Track duration

        # --- Execute API Search ---
        # Temporarily reduce logging noise from the underlying `arxiv` library during fetch
        arxiv_logger = logging.getLogger("arxiv")  # Get the logger used by the library
        original_level = arxiv_logger.level
        arxiv_logger.setLevel(logging.WARNING)  # Set to WARNING to hide INFO messages

        fetched_results: List[arxiv.Result] = []
        try:
            # Initialize the search object
            # We don't sort by date here, as the `lastUpdatedDate` query handles the filtering.
            # Sort by 'lastUpdatedDate' descending to potentially get newest first if limit hit?
            search = arxiv.Search(
                query=search_query,
                max_results=self.max_total_results,
                sort_by=arxiv.SortCriterion.LastUpdatedDate,  # Add sorting
                sort_order=arxiv.SortOrder.Descending,  # Add sorting order
            )
            # Get the results generator from the search object
            results_generator = search.results()

            # Consume the generator and show progress using tqdm
            logger.info("Processing results from arXiv API...")
            # `leave=False` removes the progress bar once done
            fetched_results = list(tqdm(results_generator, desc="Fetching arXiv results", unit=" papers", leave=False))

        except arxiv.UnexpectedEmptyPageError as e:
            # Handle specific arXiv library error for empty pages
            logger.warning(
                f"arXiv API returned an unexpected empty page during search. It might be a transient issue. Error: {e}"
            )
        except Exception as e:
            # Catch other potential errors during the API call
            logger.error(f"An error occurred while fetching or processing papers from arXiv: {e}", exc_info=True)
        finally:
            # Ensure the arxiv library's logger level is restored
            arxiv_logger.setLevel(original_level)

        # Log fetch duration and number of results received from API
        duration = time.time() - fetch_start_time
        logger.info(
            f"-> arXiv API fetch completed in {duration:.2f} seconds. Received {len(fetched_results)} results matching the date query."
        )

        # Log a warning if the number of results received meets or exceeds the limit
        if len(fetched_results) >= self.max_total_results:
            logger.warning(
                f"Reached or exceeded the fetch limit ({self.max_total_results}). "
                f"Some papers updated between {start_time_utc.strftime('%Y-%m-%d %H:%M:%S')} and "
                f"{end_time_utc.strftime('%Y-%m-%d %H:%M:%S')} might have been missed."  # Update warning message
            )

        # --- Process Results ---
        # Although the API query filters by date, results might contain duplicates
        # if a paper was updated multiple times within the window (e.g., different versions).
        # We keep only the first occurrence encountered based on the short ID (including version).
        papers_processed: List[arxiv.Result] = []
        seen_ids = set()
        for result in fetched_results:
            # Use get_short_id() which includes the version (e.g., '2401.1234v2')
            paper_id = result.get_short_id()
            if paper_id not in seen_ids:
                papers_processed.append(result)
                seen_ids.add(paper_id)
            # else: logger.debug(f"Skipping duplicate paper ID encountered in results: {paper_id}")

        logger.info(
            f"Processed {len(papers_processed)} unique papers from the target date range."
        )  # Update log message

        # --- Convert to Internal Format ---
        # Map the fields from arxiv.Result objects to our internal Paper dataclass.
        papers = [
            Paper(
                id=result.get_short_id(),  # Unique ID including version
                title=result.title,
                authors=[str(a) for a in result.authors],  # Convert author objects to strings
                abstract=result.summary,  # arXiv calls it summary
                url=result.entry_id,  # Use entry_id URL (abstract page)
                published_date=result.updated,  # Use 'updated' as the primary date
                source="arxiv",  # Mark the source
                categories=result.categories,  # List of category strings
            )
            for result in papers_processed
        ]

        return papers
