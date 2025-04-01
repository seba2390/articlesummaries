"""Implements an output handler that appends relevant paper details to a file."""

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.output.base_output import BaseOutput
from src.paper import Paper

logger = logging.getLogger(__name__)


class FileWriter(BaseOutput):
    """Outputs relevant papers by appending their details to a text file.

    Each run appends a new section to the file, marked with a timestamp.
    Paper details include ID, source, title, authors, publication/update date,
    URL, and abstract.
    """

    DEFAULT_FILENAME = "relevant_papers.txt"

    def __init__(self):
        """Initializes FileWriter with no output file configured yet."""
        self.output_file: str | None = None
        self.output_format: str = "plain"  # Default format
        self.include_confidence: bool = False
        self.include_explanation: bool = False

    def configure(self, config: Dict[str, Any]):
        """Configures the FileWriter from the 'output' section of the config.

        Args:
            config: The 'output' dictionary from the main configuration.
                    Expected keys: 'file', 'format', 'include_confidence',
                    'include_explanation'.
        """
        self.output_file = config.get("file", self.DEFAULT_FILENAME)
        self.output_format = config.get("format", "plain").lower()
        self.include_confidence = config.get("include_confidence", False)
        self.include_explanation = config.get("include_explanation", False)
        logger.info(f"FileWriter configured. Output file: '{self.output_file}', Format: {self.output_format}")

    def output(self, papers: List[Paper]):
        """Appends the details of the provided papers to the configured file.

        If no papers are provided or no output file is configured, the method
        logs a message and returns early.
        Otherwise, it opens the file in append mode (creating it if necessary)
        and writes a timestamped header followed by the details of each paper.

        Args:
            papers: A list of `Paper` objects to write to the file.
        """
        if not self.output_file:
            logger.error("FileWriter cannot write output: Output file path is not configured.")
            return

        if not papers:
            logger.info("No relevant papers found in this run. Nothing to write to file.")
            return

        logger.info(f"Attempting to append {len(papers)} papers to '{self.output_file}'...")
        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if self.output_format != "markdown":  # Add header for plain text
                    f.write(f"--- Relevant Papers Found on {timestamp} ---\n\n")

                for paper in papers:
                    categories_str = ", ".join(paper.categories) if paper.categories else "N/A"
                    matched_kw_str = ", ".join(paper.matched_keywords) if paper.matched_keywords else "N/A"
                    authors_str = ", ".join(paper.authors) if paper.authors else "N/A"
                    published_str = (
                        paper.published_date.strftime("%Y-%m-%d %H:%M:%S %Z") if paper.published_date else "N/A"
                    )
                    abstract_cleaned = (
                        str(paper.abstract).replace("\n", " ").replace("\r", "") if paper.abstract else "N/A"
                    )

                    if self.output_format == "markdown":
                        f.write(f"## {paper.title}\n\n")
                        f.write(f"**Authors:** {authors_str}\n")
                        f.write(f"**Categories:** {categories_str}\n")
                        f.write(f"**Source:** {paper.source}\n")
                        f.write(f"**URL:** {paper.url}\n")
                        published_md_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"
                        f.write(f"**Published/Updated:** {published_md_str}\n")
                        if paper.matched_keywords:
                            f.write(f"**Matched Keywords:** {matched_kw_str}\n")
                        f.write(f"\n**Abstract:**\n{paper.abstract if paper.abstract else 'N/A'}\n\n")
                        if self.include_confidence and paper.relevance:
                            confidence_val = paper.relevance.get("confidence", "N/A")
                            try:
                                f.write(f"**Relevance Confidence:** {float(confidence_val):.2f}\n")
                            except (ValueError, TypeError):
                                f.write(f"**Relevance Confidence:** {confidence_val}\n")
                        if self.include_explanation and paper.relevance:
                            f.write(f"**Relevance Explanation:**\n{paper.relevance.get('explanation', 'N/A')}\n")
                        f.write("---\n\n")
                    else:  # Plain text format
                        f.write(f"ID: {paper.id}\n")
                        f.write(f"Source: {paper.source}\n")
                        f.write(f"Title: {paper.title}\n")
                        f.write(f"Authors: {authors_str}\n")
                        f.write(f"Categories: {categories_str}\n")
                        f.write(f"Updated/Published: {published_str}\n")
                        f.write(f"URL: {paper.url}\n")
                        if paper.matched_keywords:
                            f.write(f"Matched Keywords: {matched_kw_str}\n")
                        f.write(f"Abstract: {abstract_cleaned}\n")
                        if self.include_confidence and paper.relevance:
                            confidence_val = paper.relevance.get("confidence", "N/A")
                            try:
                                f.write(f"Relevance Confidence: {float(confidence_val):.2f}\n")
                            except (ValueError, TypeError):
                                f.write(f"Relevance Confidence: {confidence_val}\n")
                        if self.include_explanation and paper.relevance:
                            f.write(f"Relevance Explanation: {paper.relevance.get('explanation', 'N/A')}\n")
                        f.write("\n" + "=" * 80 + "\n\n")

                logger.info(f"Successfully appended {len(papers)} papers to '{self.output_file}'")

        except IOError as e:
            # Handle file system errors (permissions, disk full, etc.)
            logger.error(f"IOError writing to output file '{self.output_file}': {e}", exc_info=True)
        except Exception as e:
            # Catch any other unexpected errors during file writing
            logger.error(f"An unexpected error occurred writing to '{self.output_file}': {e}", exc_info=True)
