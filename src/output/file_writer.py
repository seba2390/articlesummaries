"""Implements an output handler that appends relevant paper details to a file."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional  # Import Optional

from src.output.base_output import BaseOutput
from src.paper import Paper

logger = logging.getLogger(__name__)


class FileWriter(BaseOutput):
    """Implements the `BaseOutput` interface to write relevant papers to a file.

    Supports appending paper details to a specified file in either plain text
    or Markdown format. Includes options to include LLM confidence scores
    and explanations if available.
    """

    DEFAULT_FILENAME = "relevant_papers.txt"

    def __init__(self):
        """Initializes FileWriter with default settings.

        Sets the output file path to None initially and defaults to 'plain' format.
        LLM detail inclusion flags default to False.
        """
        self.output_file: Optional[str] = None  # Path to the output file
        self.output_format: str = "plain"  # Format: 'plain' or 'markdown'
        self.include_confidence: bool = False  # Include LLM confidence score?
        self.include_explanation: bool = False  # Include LLM explanation?

    def configure(self, config: Dict[str, Any]):
        """Configures the FileWriter using settings from the 'output' config section.

        Reads the following keys from the provided dictionary (typically `config['output']`):
          - `file`: Path to the output file (defaults to `DEFAULT_FILENAME`).
          - `format`: Output format ('plain' or 'markdown', defaults to 'plain').
          - `include_confidence`: Boolean flag to include LLM confidence (defaults to False).
          - `include_explanation`: Boolean flag to include LLM explanation (defaults to False).

        Args:
            config: The 'output' dictionary from the main application configuration.
        """
        self.output_file = config.get("file", self.DEFAULT_FILENAME)
        self.output_format = config.get("format", "plain").lower()  # Ensure lowercase format
        self.include_confidence = config.get("include_confidence", False)
        self.include_explanation = config.get("include_explanation", False)

        # Log the configuration being used
        logger.info(
            f"FileWriter configured. Output file: '{self.output_file}', "
            f"Format: {self.output_format}, Include Confidence: {self.include_confidence}, "
            f"Include Explanation: {self.include_explanation}"
        )

    def output(self, papers: List[Paper]):
        """Appends the details of the provided papers to the configured output file.

        Opens the file in append mode (`'a'`). If the file doesn't exist, it will be created.
        Writes a timestamped header (for plain text format) and then iterates through
        the `papers` list, writing the details of each paper according to the
        configured format (`plain` or `markdown`).

        Handles potential `IOError` exceptions during file operations.
        Logs messages for success, failure, or if no papers are provided.

        Args:
            papers: A list of `Paper` objects deemed relevant and to be written.
        """
        # Validate configuration before proceeding
        if not self.output_file:
            logger.error("FileWriter cannot write output: Output file path is not configured via `configure()`.")
            return

        # Handle the case where no relevant papers were found
        if not papers:
            logger.info(f"No relevant papers provided to FileWriter for file '{self.output_file}'. Nothing written.")
            return

        logger.info(
            f"Attempting to append {len(papers)} papers to '{self.output_file}' (Format: {self.output_format})..."
        )
        try:
            # Ensure the directory exists (optional, good practice for robustness)
            # output_dir = os.path.dirname(self.output_file)
            # if output_dir and not os.path.exists(output_dir):
            #     os.makedirs(output_dir)
            #     logger.info(f"Created output directory: {output_dir}")

            # Open the file in append mode with UTF-8 encoding
            with open(self.output_file, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Add a header for plain text format to separate runs
                if self.output_format != "markdown":
                    f.write(f"--- Relevant Papers Found on {timestamp} ---\n\n")

                # Iterate through each paper and write its details
                for paper in papers:
                    # Prepare common string representations, handling potential None values
                    categories_str = ", ".join(paper.categories) if paper.categories else "N/A"
                    matched_kw_str = ", ".join(paper.matched_keywords) if paper.matched_keywords else "N/A"
                    authors_str = ", ".join(paper.authors) if paper.authors else "N/A"
                    # Format datetime including timezone if available
                    published_str = (
                        paper.published_date.strftime("%Y-%m-%d %H:%M:%S %Z") if paper.published_date else "N/A"
                    )
                    # Clean abstract: replace newlines with spaces for plain text format
                    abstract_cleaned = (
                        str(paper.abstract).replace("\n", " ").replace("\r", "") if paper.abstract else "N/A"
                    )

                    # --- Write based on format ---
                    if self.output_format == "markdown":
                        # Markdown Formatting
                        f.write(f"## {paper.title}\n\n")
                        f.write(f"**Authors:** {authors_str}\n")
                        f.write(f"**Categories:** {categories_str}\n")
                        f.write(f"**Source:** {paper.source}\n")
                        f.write(f"**URL:** {paper.url}\n")
                        # Use simpler date format for Markdown
                        published_md_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"
                        f.write(f"**Published/Updated:** {published_md_str}\n")
                        if paper.matched_keywords:
                            f.write(f"**Matched Keywords:** {matched_kw_str}\n")
                        f.write(
                            f"\n**Abstract:**\n{paper.abstract if paper.abstract else 'N/A'}\n\n"
                        )  # Preserve newlines in MD abstract

                        # Add LLM details if configured and available
                        if self.include_confidence and paper.relevance:
                            confidence_val = paper.relevance.get("confidence", "N/A")
                            try:
                                f.write(f"**Relevance Confidence:** {float(confidence_val):.2f}\n")
                            except (ValueError, TypeError):
                                f.write(f"**Relevance Confidence:** {confidence_val}\n")
                        if self.include_explanation and paper.relevance:
                            f.write(f"**Relevance Explanation:**\n{paper.relevance.get('explanation', 'N/A')}\n")
                        f.write("---\n\n")  # Markdown separator

                    else:  # Plain Text Formatting (Default)
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
                        # Add LLM details if configured and available
                        if self.include_confidence and paper.relevance:
                            confidence_val = paper.relevance.get("confidence", "N/A")
                            try:
                                f.write(f"Relevance Confidence: {float(confidence_val):.2f}\n")
                            except (ValueError, TypeError):
                                f.write(f"Relevance Confidence: {confidence_val}\n")
                        if self.include_explanation and paper.relevance:
                            f.write(f"Relevance Explanation: {paper.relevance.get('explanation', 'N/A')}\n")
                        # Separator for plain text entries
                        f.write("\n" + "=" * 80 + "\n\n")

                logger.info(f"Successfully appended details of {len(papers)} papers to '{self.output_file}'")

        except IOError as e:
            # Handle file system errors (e.g., permissions, disk full)
            logger.error(f"IOError writing to output file '{self.output_file}': {e}", exc_info=True)
        except Exception as e:
            # Catch any other unexpected errors during file writing or processing
            logger.error(f"An unexpected error occurred writing to '{self.output_file}': {e}", exc_info=True)
