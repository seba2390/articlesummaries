"""Implementation of the paper source fetching papers from the arXiv API."""

import logging
import time
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time
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

    def __init__(self):
        """Initializes ArxivSource with empty categories and default max results."""
        self.categories: List[str] = []
        self.max_total_results: int = self.DEFAULT_MAX_RESULTS

    def configure(self, config: Dict[str, Any]):
        """Configures the ArxivSource with categories and result limits.

        Reads the following keys from the provided configuration dictionary:
          - `config['paper_source']['arxiv']['categories']`: List of arXiv category strings (e.g., ["cs.AI", "stat.ML"]).
          - `config['max_total_results']`: Maximum number of results to request from the API per run (top-level setting).

        Args:
            config: The main application configuration dictionary.
        """
        # Read categories from the nested structure: paper_source -> arxiv -> categories
        arxiv_config = config.get("paper_source", {}).get("arxiv", {})
        self.categories = arxiv_config.get("categories", [])

        # Read max_total_results from the top-level config, using the class default if missing
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

    def fetch_papers(self) -> List[Paper]:
        """Fetches papers from arXiv that were last updated on the previous calendar day (UTC).

        Constructs an arXiv API query based on configured categories and the date range.
        Uses the `arxiv` library to perform the search and converts the results
        into a list of `Paper` objects.

        Returns:
            A list of `Paper` objects fetched from arXiv, or an empty list if no
            categories are configured or an error occurs.
        """
        # Return early if no categories are configured to search
        if not self.categories:
            logger.info("Skipping arXiv fetch: No categories configured.")
            return []

        # --- Calculate Date Range: Previous Full Day in UTC ---
        # Get current date in UTC timezone
        today_utc = datetime.now(timezone.utc).date()
        # Calculate the date for the previous day
        yesterday_utc = today_utc - timedelta(days=1)
        # Define the start (00:00:00) and end (23:59:59) of the previous day in UTC
        start_dt_utc = datetime.combine(yesterday_utc, dt_time.min, tzinfo=timezone.utc)
        end_dt_utc = datetime.combine(yesterday_utc, dt_time.max, tzinfo=timezone.utc)
        # Format dates for the arXiv API query string (YYYYMMDDHHMMSS)
        start_str = start_dt_utc.strftime("%Y%m%d%H%M%S")
        end_str = end_dt_utc.strftime("%Y%m%d%H%M%S")
        # Construct the date part of the query
        date_query = f"lastUpdatedDate:[{start_str} TO {end_str}]"
        logger.info(f"Querying arXiv for papers last updated on: {yesterday_utc.strftime('%Y-%m-%d')} UTC")

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
            search = arxiv.Search(query=search_query, max_results=self.max_total_results)
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
                f"Some papers updated on {yesterday_utc.strftime('%Y-%m-%d')} might have been missed."
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

        logger.info(f"Processed {len(papers_processed)} unique papers from the target date.")

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
