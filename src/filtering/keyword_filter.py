"""Implements a filter based on keyword matching in paper titles and abstracts."""

import logging
from typing import Any, Dict, List

from src.filtering.base_filter import BaseFilter
from src.paper import Paper

logger = logging.getLogger(__name__)


class KeywordFilter(BaseFilter):
    """Filters papers based on the presence of keywords in title or abstract.

    This filter checks if any of the configured keywords (case-insensitive)
    appear within the combined text of a paper's title and abstract.
    """

    def __init__(self):
        """Initializes KeywordFilter with an empty keyword list."""
        self.keywords: List[str] = []

    def configure(self, config: Dict[str, Any]):
        """Configures the filter with keywords from the application config.

        Args:
            config: The configuration dictionary. Reads keywords from:
                    config['paper_source']['arxiv']['keywords']
        """
        # Read keywords from the nested arxiv source config
        arxiv_config = config.get("paper_source", {}).get("arxiv", {})
        keywords_raw = arxiv_config.get("keywords", [])

        # Convert all keywords to lowercase for case-insensitive matching
        self.keywords = [str(kw).lower() for kw in keywords_raw]

        if not self.keywords:
            logger.warning(
                "KeywordFilter configured with no keywords. All papers will be considered irrelevant by this filter."
            )
        else:
            logger.info(f"KeywordFilter configured with keywords: {self.keywords}")

    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters a list of papers based on keyword presence and stores matched keywords."""
        if not self.keywords:
            logger.info("KeywordFilter has no keywords configured, returning empty list.")
            return []

        relevant_papers = []
        logger.info(f"Filtering {len(papers)} papers using keywords: {self.keywords}")
        for paper in papers:
            title_lower = str(paper.title).lower() if paper.title else ""
            abstract_lower = str(paper.abstract).lower() if paper.abstract else ""
            text_to_search = title_lower + " " + abstract_lower

            # Find which keywords match
            matched = [kw for kw in self.keywords if kw in text_to_search]

            if matched:
                paper.matched_keywords = matched  # Store matched keywords
                relevant_papers.append(paper)

        logger.info(f"Found {len(relevant_papers)} papers matching keywords.")
        return relevant_papers
