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
    """Concrete implementation for fetching papers from arXiv.

    This class queries the arXiv API for papers based on configured categories,
    sorts them by submission date, and filters them to include only those
    submitted or updated within the last 24 hours.
    It respects a `max_total_results` limit from the configuration.
    """

    def __init__(self):
        """Initializes ArxivSource with default configuration values."""
        self.categories: List[str] = []
        self.max_total_results: int = 5000  # Default safeguard limit

    def configure(self, config: Dict[str, Any]):
        """Configures the ArxivSource instance from the application config.

        Args:
            config: The configuration dictionary. Reads:
                    - config['paper_source']['arxiv']['categories']
                    - config['max_total_results'] (top-level)
        """
        # Read categories from nested config
        arxiv_config = config.get("paper_source", {}).get("arxiv", {})
        self.categories = arxiv_config.get("categories", [])

        # Read max_total_results from top-level config
        self.max_total_results = config.get("max_total_results", 500)

        if not self.categories:
            # Log warning if no categories are provided, as fetch will do nothing
            logger.warning("ArxivSource configured with no categories. No papers will be fetched.")
        else:
            logger.info(f"ArxivSource configured for categories: {self.categories}")
        logger.info(f"Maximum total results to fetch per run: {self.max_total_results}")

    def fetch_papers(self) -> List[Paper]:
        """Fetches papers last updated on the previous calendar day (UTC)."""
        if not self.categories:
            logger.info("Skipping fetch: No arXiv categories configured.")
            return []

        # --- Calculate previous day's date range in UTC ---
        today_utc = datetime.now(timezone.utc).date()
        yesterday_utc = today_utc - timedelta(days=1)
        start_dt_utc = datetime.combine(yesterday_utc, dt_time.min, tzinfo=timezone.utc)
        end_dt_utc = datetime.combine(yesterday_utc, dt_time.max, tzinfo=timezone.utc)
        # Format for arXiv API query (YYYYMMDDHHMMSS)
        start_str = start_dt_utc.strftime("%Y%m%d%H%M%S")
        end_str = end_dt_utc.strftime("%Y%m%d%H%M%S")
        date_query = f"lastUpdatedDate:[{start_str} TO {end_str}]"
        logger.info(f"Querying arXiv for papers updated on: {yesterday_utc.strftime('%Y-%m-%d')} UTC")

        # --- Construct the full query ---
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        search_query = f"({category_query}) AND {date_query}"
        logger.debug(f"Constructed arXiv query: {search_query}")

        logger.info(f"Fetching up to {self.max_total_results} papers from arXiv (querying specific date range)...")
        fetch_start_time = time.time()

        # Temporarily silence verbose arxiv library logging
        arxiv_logger = logging.getLogger("arxiv")
        original_level = arxiv_logger.level
        arxiv_logger.setLevel(logging.WARNING)

        fetched_results: List[arxiv.Result] = []
        try:
            # Perform the search - remove sort_by as date range is primary filter
            search = arxiv.Search(
                query=search_query,
                max_results=self.max_total_results,
                # sort_by=arxiv.SortCriterion.SubmittedDate, # Removed
            )
            results_generator = search.results()

            # Use tqdm to show progress while iterating through the generator
            logger.info("Processing results from arXiv API...")  # Log before tqdm
            fetched_results = list(tqdm(results_generator, desc="Fetching arXiv results", unit=" papers", leave=False))

        except arxiv.UnexpectedEmptyPageError as e:
            logger.warning(f"arXiv API returned an unexpected empty page during search. Error: {e}")
        except Exception as e:
            logger.error(f"An error occurred while fetching papers from arXiv: {e}", exc_info=True)
        finally:
            arxiv_logger.setLevel(original_level)

        duration = time.time() - fetch_start_time
        logger.info(
            f"-> arXiv API fetch completed in {duration:.2f} seconds, received {len(fetched_results)} papers for the specified date range."
        )

        if len(fetched_results) >= self.max_total_results:
            # Note: >= because max_results is not an exact guarantee with the API
            logger.warning(
                f"Reached or exceeded the fetch limit ({self.max_total_results}). Some papers from {yesterday_utc.strftime('%Y-%m-%d')} might have been missed."
            )

        # --- Process and deduplicate results (Date filtering is now done by API query) ---
        papers_processed = []
        seen_ids = set()
        for result in fetched_results:
            paper_id = result.get_short_id()
            if paper_id not in seen_ids:
                papers_processed.append(result)
                seen_ids.add(paper_id)
            # else: logger.debug(f"Skipping duplicate paper ID: {paper_id}") # Optional debug

        logger.info(f"Found {len(papers_processed)} unique papers from the target date.")

        # --- Convert valid arXiv results to our internal Paper format ---
        papers = [
            Paper(
                id=result.get_short_id(),
                title=result.title,
                authors=[str(a) for a in result.authors],
                abstract=result.summary,
                url=result.entry_id,
                published_date=result.updated,
                source="arxiv",
                categories=result.categories,
            )
            for result in papers_processed
        ]
        return papers
