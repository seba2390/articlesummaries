import logging
from datetime import datetime
from typing import Any, Dict, List

from src.output.base_output import BaseOutput
from src.paper import Paper

logger = logging.getLogger(__name__)


class FileWriter(BaseOutput):
    """Outputs relevant papers by appending them to a file."""

    def __init__(self):
        self.output_file: str | None = None

    def configure(self, config: Dict[str, Any]):
        """Configure the writer with the output file path."""
        self.output_file = config.get("output_file", "relevant_papers.txt")
        logger.info(f"FileWriter configured to write to: {self.output_file}")

    def output(self, papers: List[Paper]):
        """Appends the list of relevant papers to the configured file."""
        if not self.output_file:
            logger.warning("No output file specified for FileWriter. Skipping output.")
            return
        if not papers:
            logger.info("No relevant papers to write to file.")
            return

        try:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(f"--- Relevant Papers Found on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                for paper in papers:
                    f.write(f"ID: {paper.id}\n")
                    f.write(f"Source: {paper.source}\n")
                    f.write(f"Title: {paper.title}\n")
                    f.write(f"Authors: {', '.join(paper.authors)}\n")
                    published_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"
                    f.write(f"Published: {published_str}\n")
                    f.write(f"URL: {paper.url}\n")
                    # Replace newline characters within the abstract for cleaner output
                    abstract_cleaned = paper.abstract.replace("\n", " ").replace("\r", "")
                    f.write(f"Abstract: {abstract_cleaned}\n\n")  # Corrected f-string usage
                logger.info(f"Appended {len(papers)} relevant papers to {self.output_file}")
        except IOError as e:
            logger.error(f"Error writing to output file {self.output_file}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred during file writing: {e}", exc_info=True)
