import logging
from typing import Any, Dict, List

from src.filtering.base_filter import BaseFilter
from src.paper import Paper

logger = logging.getLogger(__name__)


class KeywordFilter(BaseFilter):
    """Filters papers based on keywords found in title or abstract."""

    def __init__(self):
        self.keywords: List[str] = []

    def configure(self, config: Dict[str, Any]):
        """Configure the filter with a list of keywords."""
        self.keywords = [kw.lower() for kw in config.get("keywords", [])]
        if not self.keywords:
            logger.warning("No keywords specified for KeywordFilter in the config.")
        else:
            logger.info(f"KeywordFilter configured with keywords: {self.keywords}")

    def filter(self, papers: List[Paper]) -> List[Paper]:
        """Filters the list of papers, keeping only those containing keywords."""
        if not self.keywords:
            logger.warning("KeywordFilter has no keywords configured, returning all papers.")
            return papers

        relevant_papers = []
        for paper in papers:
            text_to_check = (paper.title + " " + paper.abstract).lower()
            if any(keyword in text_to_check for keyword in self.keywords):
                relevant_papers.append(paper)
                logger.debug(f"  Relevant (Keyword): [{paper.id}] {paper.title}")

        logger.info(f"KeywordFilter reduced {len(papers)} papers to {len(relevant_papers)} relevant papers.")
        return relevant_papers
