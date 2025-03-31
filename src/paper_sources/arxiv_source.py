"""Implementation of the paper source fetching papers from the arXiv API."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import arxiv

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
        self.max_total_results: int = 500  # Default safeguard limit

    def configure(self, config: Dict[str, Any]):
        """Configures the ArxivSource instance from the application config.

        Args:
            config: The configuration dictionary, expected to contain
                    'categories' (list of str) and optionally
                    'max_total_results' (int).
        """
        self.categories = config.get("categories", [])
        self.max_total_results = config.get("max_total_results", 500)
        if not self.categories:
            # Log warning if no categories are provided, as fetch will do nothing
            logger.warning("ArxivSource configured with no categories. No papers will be fetched.")
        else:
            logger.info(f"ArxivSource configured for categories: {self.categories}")
        logger.info(f"Maximum total results to fetch per run: {self.max_total_results}")

    def fetch_papers(self) -> List[Paper]:
        """Fetches papers submitted/updated in the last 24 hours from arXiv.

        Constructs a query for the configured categories, requests up to
        `max_total_results` sorted by submission date from the arXiv API,
        filters these results to keep only those with an 'updated' timestamp
        within the last 24 hours (UTC), ensures uniqueness by paper ID (preferring
        the first version encountered), and converts them to `Paper` objects.

        Returns:
            A list of unique `Paper` objects submitted/updated in the last 24 hours,
            or an empty list if no matching papers are found or an API error occurs.
        """
        if not self.categories:
            logger.info("Skipping fetch: No arXiv categories configured.")
            return []

        # --- Construct the category part of the query ---
        # Example: "(cat:cs.AI OR cat:cs.LG)"
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        search_query = f"({category_query})"
        # Note: We don't add date to the query string itself. Instead, we fetch
        # the most recent N papers and filter by date locally. This is generally
        # more reliable with the arXiv API than complex date range queries.

        logger.info(f"Querying arXiv for categories: {self.categories}")
        logger.info(f"Fetching up to {self.max_total_results} most recently submitted/updated papers.")

        try:
            # Perform the search, sorting by submission date to get newest first
            search = arxiv.Search(
                query=search_query,
                max_results=self.max_total_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
            )

            # Execute the search and fetch results. Convert generator to list.
            # This might take some time depending on network and API response.
            results_generator = search.results()
            fetched_results: List[arxiv.Result] = list(results_generator)

            logger.info(f"arXiv API returned {len(fetched_results)} papers (sorted by submission date). ")
            # Log a warning if we hit the configured limit, as there might be more papers.
            if len(fetched_results) == self.max_total_results:
                logger.warning(
                    f"Reached the fetch limit ({self.max_total_results}). Some papers submitted/updated today might have been missed."
                )

            # --- Filter results by 'updated' date (last 24 hours) and uniqueness ---
            # Use timezone-aware datetime for comparison
            cutoff_datetime_utc = datetime.now(timezone.utc) - timedelta(days=1)
            papers_in_window = []
            seen_ids = set()

            for result in fetched_results:
                # Use the 'updated' field, as it reflects the last modification time (incl. new versions)
                paper_time_utc = result.updated
                # Ensure the result has a valid timezone-aware datetime
                if not isinstance(paper_time_utc, datetime) or paper_time_utc.tzinfo is None:
                    logger.warning(
                        f"Skipping paper {result.entry_id}: Missing or non-timezone-aware 'updated' date: {paper_time_utc}"
                    )
                    continue  # Skip if date is invalid or naive

                paper_id = result.get_short_id()

                # Check if updated within the last 24 hours AND if ID is unique
                if paper_time_utc >= cutoff_datetime_utc and paper_id not in seen_ids:
                    papers_in_window.append(result)
                    seen_ids.add(paper_id)  # Add ID to prevent duplicates (e.g., v1, v2 of same paper ID base)

            logger.info(f"Filtered down to {len(papers_in_window)} unique papers updated in the last 24 hours.")

            # --- Convert valid arXiv results to our internal Paper format ---
            papers = [
                Paper(
                    id=result.get_short_id(),
                    title=result.title,
                    authors=[str(a) for a in result.authors],
                    abstract=result.summary,
                    url=result.entry_id,
                    published_date=result.updated,  # Store the 'updated' date
                    source="arxiv",
                )
                for result in papers_in_window
            ]
            return papers

        except arxiv.UnexpectedEmptyPageError as e:
            # Handle specific arxiv library error for potentially transient issues
            logger.warning(
                f"arXiv API returned an unexpected empty page during search. This might be transient. Error: {e}"
            )
            return []
        except Exception as e:
            # Catch broader exceptions during API interaction or processing
            logger.error(f"An error occurred while fetching or processing papers from arXiv: {e}", exc_info=True)
            return []
