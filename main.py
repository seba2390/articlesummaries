"""Main execution script for the arXiv Paper Monitor.

This script orchestrates the application flow:
1. Initializes logging.
2. Loads configuration from `config.yaml`.
3. Sets up the main monitoring job (`main_job`).
4. Initializes the scheduler (`src.scheduler.Scheduler`).
5. Starts the scheduler to run the job periodically.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

import schedule

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
from src.llm import GroqChecker
from src.output.file_writer import FileWriter
from src.paper_sources.arxiv_source import ArxivSource
from src.scheduler import Scheduler

# --- Logging Configuration ---
# Configure root logger for overall application messages
logging.basicConfig(
    level=logging.INFO,  # Set default level (can be overridden by specific loggers)
    format="%(asctime)s [%(levelname)-8s] %(message)s",  # Added padding to levelname
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to console
    ],
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Get the root logger instance
# Module-specific loggers (e.g., src.paper_sources.arxiv_source) inherit this config
# but can have their levels adjusted if needed (e.g., set to DEBUG for more detail).
logger = logging.getLogger()


# --- Utility Functions ---
def print_separator(char="=", length=70):
    """Prints a separator line to the console for better visual structure."""
    print(char * length)


# --- Main Job Definition ---
def main_job(config):
    """The core job function executed by the scheduler.

    This function performs one complete cycle of fetching, filtering, and outputting
    papers based on the provided configuration.

    Steps:
    1. Instantiates the paper source (ArxivSource), filter (KeywordFilter),
       and output handler (FileWriter).
    2. Configures each component using the global configuration dictionary.
    3. Executes the workflow: fetch -> filter -> output.
    4. Logs progress and results for each step.

    Args:
        config: The loaded application configuration dictionary.
    """
    run_start_time = datetime.now()
    print_separator()
    logger.info("🚀 Starting Daily Paper Check...")
    print_separator()

    # --- Instantiate components ---
    logger.debug("Instantiating components: ArxivSource, KeywordFilter, FileWriter")
    try:
        # Revert to single ArxivSource
        paper_source = ArxivSource()
        paper_filter = KeywordFilter()
        output_handler = FileWriter()
    except Exception as e:
        logger.error(f"Fatal error instantiating components: {e}", exc_info=True)
        logger.error("Job cannot proceed.")
        return

    # --- Configure components ---
    logger.debug("Configuring components...")
    try:
        paper_source.configure(config)
        paper_filter.configure(config)
        output_handler.configure(config)
        logger.debug("Components configured successfully.")
    except KeyError as e:
        logger.error(f"Configuration error during component setup: Missing key '{e}'")
        logger.error("Job cannot proceed due to configuration error.")
        return
    except Exception as e:
        logger.error(f"Unexpected error configuring components: {e}", exc_info=True)
        logger.error("Job cannot proceed due to configuration error.")
        return

    # --- Execute workflow ---
    try:
        # 1. Fetching Papers
        print_separator("-")
        logger.info("🔎 Fetching papers...")
        fetch_start_time = datetime.now()
        # Fetch from single source
        papers = paper_source.fetch_papers()
        fetch_duration = datetime.now() - fetch_start_time
        # Revert log message logic
        if not papers:
            logger.info(f"-> No new papers found matching criteria. (Duration: {fetch_duration.total_seconds():.2f}s)")
        else:
            logger.info(
                f"-> Fetched {len(papers)} papers matching date criteria. (Duration: {fetch_duration.total_seconds():.2f}s)"
            )

        # Remove deduplication logic

        # 2. Filtering Papers (using 'papers' directly)
        relevant_papers = []
        if papers:
            print_separator("-")
            logger.info(f"🔍 Filtering {len(papers)} papers by keywords...")
            filter_start_time = datetime.now()
            relevant_papers = paper_filter.filter(papers)
            filter_duration = datetime.now() - filter_start_time
            logger.info(
                f"-> Found {len(relevant_papers)} relevant papers. (Duration: {filter_duration.total_seconds():.2f}s)"
            )
        else:
            # Revert skipping logic
            if getattr(paper_source, "categories", None):  # Check if source had categories (ArxivSource does)
                logger.info("-> Skipping keyword filtering as no papers matched date criteria.")

        # 3. Outputting Results
        if relevant_papers:
            print_separator("-")
            logger.info("💾 Processing output...")
            output_start_time = datetime.now()
            output_handler.output(relevant_papers)
            output_duration = datetime.now() - output_start_time
            logger.info(f"-> Output processing finished. (Duration: {output_duration.total_seconds():.2f}s)")
        else:
            # Revert skipping logic
            if papers:
                logger.info("-> Skipping output as no papers were deemed relevant by filters.")

        # --- Job Completion Summary ---
        run_duration = datetime.now() - run_start_time
        print_separator()
        logger.info(
            f"✅ Daily Paper Check Finished. Relevant papers found: {len(relevant_papers)}. Total duration: {run_duration.total_seconds():.2f} seconds."
        )
        print_separator()

    except Exception as e:
        # Revert error message slightly if needed, keep outer catch
        logger.error(f"❌ An unexpected error occurred during job execution: {e}", exc_info=True)
        print_separator("!")
        logger.error("❗ Job execution failed unexpectedly.")
        print_separator("!")


# --- Script Entry Point ---
if __name__ == "__main__":
    print_separator("*")
    logger.info("✨ Initializing ArXiv Paper Monitor ✨")
    print_separator("*")

    logger.info("Loading configuration from 'config.yaml'...")
    config = load_config("config.yaml")
    if not config:
        logger.error("❌ Critical error: Failed to load configuration. Please check 'config.yaml'. Exiting.")
        sys.exit(1)
    logger.info("Configuration loaded successfully.")

    job_with_config = lambda: main_job(config)

    logger.info("Initializing scheduler...")
    try:
        scheduler = Scheduler(config, job_with_config)
        logger.info("Starting scheduler main loop...")
        scheduler.run()
    except Exception as e:
        logger.error(f"❌ Critical error during scheduler setup or execution: {e}", exc_info=True)
        logger.error("Application will exit.")
        sys.exit(1)

    logger.info("🛑 ArXiv Paper Monitor stopped.")
    print_separator("*")


def create_relevance_checker(
    config: Dict[str, Any],
) -> Optional[GroqChecker]:
    """Create appropriate relevance checker based on config."""
    checker_type = config["relevance_checker"]["type"]

    if checker_type == "keyword":
        return None  # Keyword checking is handled in ArxivSource

    elif checker_type == "llm":
        llm_config = config["relevance_checker"]["llm"]
        provider = llm_config["provider"]

        if provider == "groq":
            api_key = llm_config.get("api_key")
            if not api_key:
                raise ValueError("Groq API key is required when using Groq provider")
            return GroqChecker(api_key)

        elif provider == "custom":
            # Import and instantiate custom checker
            module_path = llm_config.get("module_path")
            class_name = llm_config.get("class_name")
            if not module_path or not class_name:
                raise ValueError("module_path and class_name are required for custom provider")

            import importlib

            module = importlib.import_module(module_path)
            checker_class = getattr(module, class_name)
            return checker_class()

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    else:
        raise ValueError(f"Unknown relevance checker type: {checker_type}")


@runtime_checkable
class PaperProtocol(Protocol):
    title: str
    authors: List[str]
    categories: List[str]
    url: str
    abstract: str
    relevance: Optional[Dict[str, Any]]


@dataclass
class Paper:
    title: str
    authors: List[str]
    categories: List[str]
    url: str
    abstract: str
    relevance: Optional[Dict[str, Any]] = field(default=None)


def check_papers(config: Dict[str, Any]) -> None:
    """Check for new relevant papers."""
    try:
        # Create paper source
        source = ArxivSource()

        # Create relevance checker if needed
        relevance_checker = create_relevance_checker(config)

        # Fetch papers
        papers = source.fetch_papers()
        logger.info(f"📚 Fetched {len(papers)} papers from arXiv")

        # Check relevance
        relevant_papers: List[PaperProtocol] = []
        if relevance_checker:
            # Use LLM-based checking
            llm_config = config["relevance_checker"]["llm"]
            prompt = llm_config["prompt"]
            confidence_threshold = llm_config["confidence_threshold"]

            # Process papers one by one
            for paper in papers:
                response = relevance_checker.check_relevance(paper.abstract, prompt)
                if response.is_relevant and response.confidence >= confidence_threshold:
                    if isinstance(paper, PaperProtocol):
                        paper.relevance = {"confidence": response.confidence, "explanation": response.explanation}
                        relevant_papers.append(paper)
        else:
            # Use keyword-based checking
            relevant_papers = [p for p in papers if isinstance(p, PaperProtocol)]

        # Save relevant papers
        if relevant_papers:
            output_config = config["output"]
            output_file = output_config["file"]
            output_format = output_config["format"]
            include_confidence = output_config.get("include_confidence", False)
            include_explanation = output_config.get("include_explanation", False)

            with open(output_file, "a", encoding="utf-8") as f:
                for paper in relevant_papers:
                    if output_format == "markdown":
                        f.write(f"## {paper.title}\n\n")
                        f.write(f"**Authors:** {', '.join(paper.authors)}\n\n")
                        f.write(f"**Categories:** {', '.join(paper.categories)}\n\n")
                        f.write(f"**URL:** {paper.url}\n\n")
                        f.write(f"**Abstract:**\n{paper.abstract}\n\n")

                        if include_confidence and paper.relevance:
                            f.write(f"**Relevance Confidence:** {paper.relevance['confidence']:.2f}\n\n")
                        if include_explanation and paper.relevance:
                            f.write(f"**Relevance Explanation:**\n{paper.relevance['explanation']}\n\n")
                        f.write("---\n\n")
                    else:
                        f.write(f"Title: {paper.title}\n")
                        f.write(f"Authors: {', '.join(paper.authors)}\n")
                        f.write(f"Categories: {', '.join(paper.categories)}\n")
                        f.write(f"URL: {paper.url}\n")
                        f.write(f"Abstract:\n{paper.abstract}\n")

                        if include_confidence and paper.relevance:
                            f.write(f"Relevance Confidence: {paper.relevance['confidence']:.2f}\n")
                        if include_explanation and paper.relevance:
                            f.write(f"Relevance Explanation:\n{paper.relevance['explanation']}\n")
                        f.write("\n" + "=" * 80 + "\n\n")

            logger.info(f"✅ Saved {len(relevant_papers)} relevant papers to {output_file}")
        else:
            logger.info("ℹ️ No relevant papers found")

    except Exception as e:
        logger.error(f"❌ An unexpected error occurred during job execution: {e}", exc_info=True)


def main():
    """Main entry point."""
    try:
        # Load configuration
        config = load_config()

        # Schedule the job
        schedule_config = config["schedule"]
        schedule.every().day.at(schedule_config["run_time"]).do(check_papers, config)

        logger.info("🚀 Starting arXiv Paper Monitor")
        logger.info(f"⏰ Scheduled to run daily at {schedule_config['run_time']} {schedule_config['timezone']}")

        # Run the job immediately
        check_papers(config)

        # Keep the script running
        while True:
            schedule.run_pending()
            time.sleep(60)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
