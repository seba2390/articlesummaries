import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import arxiv

from src.paper import Paper
from src.paper_sources.base_source import BasePaperSource

logger = logging.getLogger(__name__)


class ArxivSource(BasePaperSource):
    """Paper source implementation for arXiv, fetching papers published 'today'."""

    def __init__(self):
        self.categories: List[str] = []
        self.max_total_results: int = 500  # Default safeguard

    def configure(self, config: Dict[str, Any]):
        """Configure the arXiv source with categories and max total results."""
        self.categories = config.get("categories", [])
        self.max_total_results = config.get("max_total_results", 500)
        if not self.categories:
            logger.warning("No arXiv categories specified in the config.")
        logger.info(f"ArxivSource configured for categories: {self.categories}")
        logger.info(f"Maximum total results to fetch: {self.max_total_results}")

    def fetch_papers(self) -> List[Paper]:
        """Fetches papers submitted to arXiv within the last 24 hours for the configured categories."""
        if not self.categories:
            return []

        # --- Define date range for "today" (last 24 hours) ---
        # arXiv API seems to work best with submission date queries.
        # Let's query for papers submitted in the last ~24 hours before the script runs.
        # Note: arXiv submission times might be UTC. Consider timezone if precise alignment is critical.
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date_query = yesterday.strftime("%Y%m%d%H%M%S")  # Format YYYYMMDDHHMMSS

        # --- Construct the query ---
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        # Combine category and date query. Querying submittedDate seems more reliable for recent papers.
        # Query format example: submittedDate:[20240101 TO 20240102] AND (cat:cs.AI OR cat:cs.LG)
        # Simpler approach: query categories and filter by date afterwards, or rely on SubmittedDate sort.
        # Let's stick to sorting by SubmittedDate and fetching max_total_results, then filtering locally.
        # This avoids complex date queries but means we might miss papers if > max_total_results were submitted.
        search_query = f"({category_query})"

        logger.info(f"Searching arXiv for categories: {self.categories}")
        logger.info(f"Fetching up to {self.max_total_results} most recently submitted papers.")

        try:
            search = arxiv.Search(
                query=search_query,
                max_results=self.max_total_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,  # Get the newest ones first
            )

            results_generator = search.results()
            fetched_results = list(results_generator)  # Fetch results

            logger.info(f"Fetched {len(fetched_results)} papers initially from arXiv (sorted by submission date). ")
            if len(fetched_results) == self.max_total_results:
                logger.warning(
                    f"Reached the maximum limit ({self.max_total_results}). There might be more papers submitted today."
                )

            # --- Filter results to include only those submitted within the last 24 hours ---
            target_datetime_utc = datetime.now(timezone.utc) - timedelta(days=1)
            papers_today = []
            seen_ids = set()

            for result in fetched_results:
                paper_id = result.get_short_id()
                # Ensure uniqueness and check submission date
                # Use updated_date as a proxy if published is much older, or stick to published?
                # Let's use 'updated' date as it often reflects the latest version submission.
                # Note: The arxiv library uses 'updated' for the last update time.
                paper_time = result.updated  # Use 'updated' which seems more reliable for recent changes

                if paper_id not in seen_ids and paper_time >= target_datetime_utc:
                    papers_today.append(result)
                    seen_ids.add(paper_id)

            logger.info(f"Found {len(papers_today)} unique papers submitted/updated in the last 24 hours.")

            # Convert arxiv.Result to our internal Paper format
            papers = [
                Paper(
                    id=result.get_short_id(),
                    title=result.title,
                    authors=[str(a) for a in result.authors],
                    abstract=result.summary,
                    url=result.entry_id,
                    # Use 'updated' date here as well for consistency with filtering
                    published_date=result.updated,
                    source="arxiv",
                )
                for result in papers_today
            ]
            return papers

        except Exception as e:
            logger.error(f"An error occurred while fetching papers from arXiv: {e}", exc_info=True)
            return []
