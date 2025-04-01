"""Implements a filter based on keyword matching in paper titles and abstracts."""

import logging
from typing import Any, Dict, List

from src.filtering.base_filter import BaseFilter
from src.paper import Paper

logger = logging.getLogger(__name__)


class KeywordFilter(BaseFilter):
    """Filters a list of papers based on keyword matches in title or abstract.

    Implements the `BaseFilter` interface. It checks if any of the configured
    keywords (case-insensitive) are present in the concatenated lowercased
    title and abstract of each paper.
    If keywords are found, the paper is considered relevant, and the matched
    keywords are stored in the `paper.matched_keywords` attribute.
    If no keywords are configured, the filter passes all papers through.
    """

    def __init__(self):
        """Initializes the KeywordFilter with an empty list for keywords."""
        # Stores the configured keywords, converted to lowercase.
        self.keywords: List[str] = []

    def configure(self, config: Dict[str, Any]):
        """Configures the filter by loading keywords from the application config.

        Reads keywords from `config['paper_source']['arxiv']['keywords']`.
        Keywords are converted to lowercase for case-insensitive matching.
        Logs a warning if no keywords are found in the configuration.

        Args:
            config: The main application configuration dictionary.
        """
        # Navigate the config structure to find the keywords list
        # Uses .get() with defaults to avoid KeyErrors if structure is missing
        arxiv_config = config.get("paper_source", {}).get("arxiv", {})
        keywords_raw = arxiv_config.get("keywords", [])  # Get list or empty list

        # Ensure keywords are strings and lowercase them for consistent matching
        self.keywords = [str(kw).lower() for kw in keywords_raw if kw]  # Added check for empty strings

        # Log the outcome of configuration
        if not self.keywords:
            logger.warning(
                "KeywordFilter configured with no valid keywords found in config['paper_source']['arxiv']['keywords']. "
                "The filter will pass all papers."
            )
        else:
            logger.info(f"KeywordFilter configured with keywords: {self.keywords}")

    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters the provided list of papers based on configured keywords.

        Iterates through each paper, checks for keyword presence in the title
        and abstract (case-insensitive). If a match is found, the paper is added
        to the results and its `matched_keywords` field is populated.
        If no keywords were configured, returns the original list of papers.

        Args:
            papers: The list of `Paper` objects to filter.

        Returns:
            A new list containing only the papers that matched the keywords,
            or the original list if no keywords were configured.
        """
        # If no keywords were loaded during configure, pass all papers through
        if not self.keywords:
            logger.info("KeywordFilter has no keywords configured; passing all papers through.")
            return papers

        relevant_papers: List[Paper] = []
        logger.info(f"Filtering {len(papers)} papers using keywords: {self.keywords}")

        # Process each paper
        for paper in papers:
            # Combine title and abstract into a single lowercased string for searching
            # Handle potential None values for title or abstract
            title_lower = str(paper.title).lower() if paper.title else ""
            abstract_lower = str(paper.abstract).lower() if paper.abstract else ""
            text_to_search = title_lower + " " + abstract_lower

            # Find all configured keywords present in the combined text
            matched = [kw for kw in self.keywords if kw in text_to_search]

            # If any keywords matched, consider the paper relevant
            if matched:
                paper.matched_keywords = matched  # Store the list of keywords that matched
                relevant_papers.append(paper)
            # else: logger.debug(f"Paper {paper.id} did not match keywords.") # Optional debug log

        logger.info(f"Found {len(relevant_papers)} papers matching keywords.")
        return relevant_papers
