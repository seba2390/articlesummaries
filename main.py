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
from typing import Any, Dict, List, Optional

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
from src.llm import GroqChecker
from src.output.file_writer import FileWriter
from src.paper import Paper
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
def check_papers(config: Dict[str, Any]) -> None:
    """Check for new relevant papers."""
    try:
        source = ArxivSource()
        source.configure(config)

        # Explicitly log configured keywords for keyword checking
        try:
            # Read keywords from the nested arxiv source config for logging
            arxiv_config = config.get("paper_source", {}).get("arxiv", {})
            keywords_for_logging = arxiv_config.get("keywords", [])
            if keywords_for_logging:
                logger.info(f"Keyword checking configured with keywords: {keywords_for_logging}")
            else:
                logger.info("Keyword checking is configured with no keywords.")
        except Exception as e:
            logger.warning(f"Could not read or log keywords from config: {e}")

        # Determine checking method from top-level config
        checking_method = config.get("relevance_checking_method", "keyword").lower()  # Default to keyword

        llm_checker = None
        if checking_method == "llm":
            llm_checker = create_relevance_checker(config)
            if not llm_checker:
                logger.warning(
                    "LLM checking method selected, but failed to create LLM checker. Falling back to no relevance check."
                )
                checking_method = "none"  # Indicate no check will happen
        elif checking_method != "keyword":
            logger.warning(f"Unknown relevance_checking_method: '{checking_method}'. Defaulting to keyword check.")
            checking_method = "keyword"

        papers: List[Paper] = source.fetch_papers()
        logger.info(f"📚 Fetched {len(papers)} papers from arXiv matching date criteria.")

        relevant_papers: List[Paper] = []
        if not papers:
            logger.info("ℹ️ No papers fetched, skipping relevance check.")

        elif checking_method == "llm" and llm_checker:
            # --- LLM Check ---
            logger.info(f"🔍 Checking relevance of {len(papers)} papers using LLM...")
            try:
                groq_config = config.get("relevance_checker", {}).get("llm", {}).get("groq", {})
                prompt = groq_config.get("prompt", "Is this paper relevant?")
                confidence_threshold = groq_config.get("confidence_threshold", 0.0)

                abstracts = [p.abstract for p in papers]
                if abstracts:
                    start_time = time.time()
                    responses = llm_checker.check_relevance_batch(abstracts, prompt)
                    duration = time.time() - start_time
                    logger.info(f"LLM batch processing completed in {duration:.2f} seconds.")
                    for paper, response in zip(papers, responses):
                        if response.is_relevant and response.confidence >= confidence_threshold:
                            paper.relevance = {"confidence": response.confidence, "explanation": response.explanation}
                            relevant_papers.append(paper)
                        else:
                            logger.debug(
                                f"Paper {paper.id} deemed not relevant by LLM (Confidence: {response.confidence:.2f})"
                            )
                else:
                    logger.warning("No abstracts found in fetched papers for LLM checking.")
            except Exception as e:
                logger.error(f"Error during LLM batch relevance check: {e}", exc_info=True)

        elif checking_method == "keyword":
            # --- Keyword Check ---
            logger.info(f"🔍 Filtering {len(papers)} papers using keywords...")
            keyword_filter = KeywordFilter()
            keyword_filter.configure(config)
            relevant_papers = keyword_filter.filter(papers)

        else:  # E.g., checking_method was 'none' or unknown and defaulted
            logger.info("ℹ️ No specific relevance check performed or method defaulted.")
            relevant_papers = papers  # Pass all fetched papers through

        logger.info(f"✅ Found {len(relevant_papers)} relevant papers after checking.")

        if relevant_papers:
            output_config = config.get("output", {})
            file_writer = FileWriter()
            file_writer.configure(output_config)
            file_writer.output(relevant_papers)
        else:
            logger.info("ℹ️ No relevant papers to save.")

    except Exception as e:
        logger.error(f"❌ An unexpected error occurred during job execution: {e}", exc_info=True)


# --- Script Entry Point ---
if __name__ == "__main__":
    print_separator("*")
    logger.info("✨ Initializing ArXiv Paper Monitor ✨")
    print_separator("*")

    logger.info("Loading configuration from 'config.yaml'...")
    config_data = load_config("config.yaml")
    if not config_data:
        logger.error("❌ Critical error: Failed to load configuration. Please check 'config.yaml'. Exiting.")
        sys.exit(1)
    logger.info("Configuration loaded successfully.")

    # Log the chosen relevance checking method
    checking_method_log = config_data.get("relevance_checking_method", "keyword").lower()
    logger.info(f"Relevance checking method set to: '{checking_method_log}'")

    # Ensure config_data is not None for the lambda type hint
    # The check above guarantees this at runtime
    validated_config: Dict[str, Any] = config_data
    job_with_config = lambda: check_papers(validated_config)

    logger.info("Initializing scheduler...")
    try:
        # Pass the validated config
        scheduler = Scheduler(validated_config, job_with_config)
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
    """Create LLM relevance checker instance based on config.

    Reads settings from config['relevance_checker']['llm'].
    This function should ONLY be called if relevance_checking_method is "llm".
    """
    # NOTE: The decision to call this function is made in check_papers
    # based on the top-level 'relevance_checking_method' flag.
    llm_config = config.get("relevance_checker", {}).get("llm", {})
    provider = llm_config.get("provider")

    if provider == "groq":
        groq_config = llm_config.get("groq", {})
        api_key = groq_config.get("api_key")
        if not api_key:
            logger.error("Groq provider selected, but API key (relevance_checker.llm.groq.api_key) is missing.")
            return None  # Cannot create checker without API key

        # Optional: Pass model from config to checker if checker supports it
        # model = groq_config.get("model")
        # Consider modifying GroqChecker to accept model in __init__
        try:
            # Pass only api_key for now, GroqChecker uses default model
            return GroqChecker(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize GroqChecker: {e}", exc_info=True)
            return None

    # elif provider == "custom": # Future extension
    #     ...
    else:
        logger.error(f"LLM relevance checking selected, but unknown or unsupported provider specified: '{provider}'")
        return None  # Return None if provider is unknown/unsupported
