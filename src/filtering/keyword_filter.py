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

        Expects a 'keywords' key in the config dictionary containing a list
        of strings. Keywords are stored internally in lowercase.

        Args:
            config: The configuration dictionary.
        """
        # Extract keywords, default to empty list, ensure lowercase
        self.keywords = [str(kw).lower() for kw in config.get("keywords", [])]
        if not self.keywords:
            logger.warning("KeywordFilter configured with no keywords. Filter will pass all papers.")
        else:
            logger.info(f"KeywordFilter configured with {len(self.keywords)} keywords: {self.keywords}")

    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters papers based on keyword matches.

        Iterates through the provided list of papers. A paper is considered
        relevant if its title or abstract contains any of the configured keywords
        (case-insensitive comparison).

        Args:
            papers: The list of `Paper` objects to filter.

        Returns:
            A list of `Paper` objects that contain at least one keyword.
            Returns the original list if no keywords are configured.
        """
        # If no keywords are set, filtering is effectively disabled
        if not self.keywords:
            logger.warning("Keyword filtering skipped: No keywords are configured.")
            return papers

        relevant_papers = []
        logger.debug(f"Applying keyword filter ({len(self.keywords)} keywords) to {len(papers)} papers.")
        for paper in papers:
            # Combine title and abstract for searching, convert to lowercase
            # Handle potential None values for title/abstract gracefully
            title = str(paper.title).lower() if paper.title else ""
            abstract = str(paper.abstract).lower() if paper.abstract else ""
            text_to_check = title + " " + abstract

            # Check if any configured keyword is present
            if any(keyword in text_to_check for keyword in self.keywords):
                relevant_papers.append(paper)
                # Debug log for matched papers can be useful
                logger.debug(f"  Match found: Paper ID {paper.id} ('{paper.title[:50]}...') contains keyword.")

        # Log summary of filtering results
        logger.info(f"Keyword filtering complete: {len(relevant_papers)} papers matched out of {len(papers)}.")
        return relevant_papers
