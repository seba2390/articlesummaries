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

    def configure(self, config: Dict[str, Any]):
        """Configures the FileWriter with the target output file path.

        Expects an 'output_file' key in the config dictionary.
        If not present, defaults to `DEFAULT_FILENAME`.

        Args:
            config: The configuration dictionary.
        """
        self.output_file = config.get("output_file", self.DEFAULT_FILENAME)
        logger.info(f"FileWriter configured. Output will be appended to: '{self.output_file}'")

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
            # Open in append mode ('a'), create if doesn't exist.
            # Specify UTF-8 encoding for broad compatibility.
            with open(self.output_file, "a", encoding="utf-8") as f:
                # Write a header for this batch of papers
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"--- Relevant Papers Found on {timestamp} ---\n\n")

                # Write details for each paper
                for paper in papers:
                    f.write(f"ID: {paper.id}\n")
                    f.write(f"Source: {paper.source}\n")
                    f.write(f"Title: {paper.title}\n")
                    # Format authors nicely, handle empty list
                    authors_str = ", ".join(paper.authors) if paper.authors else "N/A"
                    f.write(f"Authors: {authors_str}\n")
                    # Format date, handle potential None
                    published_str = (
                        paper.published_date.strftime("%Y-%m-%d %H:%M:%S %Z") if paper.published_date else "N/A"
                    )
                    f.write(f"Updated/Published: {published_str}\n")
                    f.write(f"URL: {paper.url}\n")
                    # Clean up abstract newlines for single-line representation in the file
                    abstract_cleaned = (
                        str(paper.abstract).replace("\n", " ").replace("\r", "") if paper.abstract else "N/A"
                    )
                    f.write(f"Abstract: {abstract_cleaned}\n\n")

                logger.info(f"Successfully appended {len(papers)} papers to '{self.output_file}'")

        except IOError as e:
            # Handle file system errors (permissions, disk full, etc.)
            logger.error(f"IOError writing to output file '{self.output_file}': {e}", exc_info=True)
        except Exception as e:
            # Catch any other unexpected errors during file writing
            logger.error(f"An unexpected error occurred writing to '{self.output_file}': {e}", exc_info=True)
