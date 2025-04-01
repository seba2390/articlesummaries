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
from datetime import datetime  # Import datetime for run start time
from typing import Any, Dict, List, Optional

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
from src.llm import GroqChecker
from src.notifications.email_sender import EmailSender  # Import EmailSender
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
    """Fetches papers, checks relevance, saves relevant ones, and sends summary.

    This is the core function executed by the scheduler.

    Args:
        config: The application configuration dictionary.
    """
    run_start_time = datetime.now()  # Record start time for duration calculation
    num_fetched = 0  # Track number of papers fetched for summary
    try:
        # 1. Initialize and configure the paper source (e.g., ArxivSource)
        # Currently hardcoded to ArxivSource, could be made dynamic if needed.
        source = ArxivSource()
        source.configure(config)

        # Explicitly log configured keywords for visibility (if keyword checking is used)
        try:
            # Read keywords from the expected config location
            arxiv_config = config.get("paper_source", {}).get("arxiv", {})
            keywords_for_logging = arxiv_config.get("keywords", [])
            if keywords_for_logging:
                logger.info(f"Keyword checking configured with keywords: {keywords_for_logging}")
            else:
                logger.info("Keyword checking is configured with no keywords.")
        except Exception as e:
            logger.warning(f"Could not read or log keywords from config: {e}")

        # 2. Determine the relevance checking method (keyword, llm, or none)
        checking_method = config.get("relevance_checking_method", "keyword").lower()

        llm_checker = None
        if checking_method == "llm":
            llm_checker = create_relevance_checker(config)
            if not llm_checker:
                logger.warning(
                    "LLM checking method selected, but failed to create LLM checker. "
                    "Falling back to no specific relevance check (all fetched papers considered relevant)."
                )
                checking_method = "none"  # Fallback: treat all fetched as relevant
        elif checking_method not in ["keyword", "none"]:
            logger.warning(f"Unknown relevance_checking_method: '{checking_method}'. Defaulting to keyword check.")
            checking_method = "keyword"

        # 3. Fetch papers from the source
        papers: List[Paper] = source.fetch_papers()
        num_fetched = len(papers)  # Store actual number fetched
        logger.info(f"📚 Fetched {len(papers)} papers from arXiv matching date criteria.")

        # 4. Perform relevance check based on the selected method
        relevant_papers: List[Paper] = []
        if not papers:
            logger.info("ℹ️ No papers fetched, skipping relevance check.")
        elif checking_method == "llm" and llm_checker:
            # --- LLM Check Path ---
            logger.info(f"🔍 Checking relevance of {len(papers)} papers using LLM...")
            try:
                # Configuration for the LLM check (e.g., prompt, threshold)
                # Assumes Groq for now based on create_relevance_checker
                llm_config = config.get("relevance_checker", {}).get("llm", {}).get("groq", {})
                prompt = llm_config.get("prompt", "Is this paper relevant based on its abstract?")
                confidence_threshold = llm_config.get("confidence_threshold", 0.7)  # Example threshold

                # Prepare abstracts for batch processing
                abstracts = [p.abstract for p in papers]
                if abstracts:
                    start_time = time.time()
                    responses = llm_checker.check_relevance_batch(abstracts, prompt)
                    duration = time.time() - start_time
                    logger.info(f"LLM batch processing completed in {duration:.2f} seconds.")

                    # Process responses and identify relevant papers
                    for paper, response in zip(papers, responses):
                        if response.is_relevant and response.confidence >= confidence_threshold:
                            paper.relevance = {"confidence": response.confidence, "explanation": response.explanation}
                            relevant_papers.append(paper)
                        else:
                            # Log why a paper was deemed irrelevant by LLM (useful for tuning)
                            logger.debug(
                                f"Paper {paper.id} deemed not relevant by LLM "
                                f"(Relevant: {response.is_relevant}, Confidence: {response.confidence:.2f}) "
                                f"Reason: {response.explanation}"
                            )
                else:
                    logger.warning("No abstracts found in fetched papers for LLM checking.")
            except Exception as e:
                logger.error(f"Error during LLM batch relevance check: {e}", exc_info=True)
                # If LLM fails, we currently find 0 relevant papers. Consider fallback? No, stick to configured method.

        elif checking_method == "keyword":
            # --- Keyword Check Path ---
            logger.info(f"🔍 Filtering {len(papers)} papers using keywords...")
            keyword_filter = KeywordFilter()
            keyword_filter.configure(config)
            relevant_papers = keyword_filter.filter(papers)

        else:  # checking_method is 'none' or fell back to 'none'
            logger.info(
                "ℹ️ No specific relevance check performed or method defaulted. Treating all fetched papers as relevant."
            )
            relevant_papers = papers  # Pass all fetched papers through

        logger.info(f"✅ Found {len(relevant_papers)} relevant papers after checking.")

        # 5. Output relevant papers (e.g., to a file)
        output_file_path = None  # Track path for potential email attachment
        if relevant_papers:
            output_config = config.get("output", {})
            file_writer = FileWriter()  # Currently hardcoded, could be dynamic
            file_writer.configure(output_config)
            file_writer.output(relevant_papers)
            output_file_path = file_writer.output_file  # Get the actual path used
        else:
            logger.info("ℹ️ No relevant papers to save.")
            # Still get the configured default output path for email reference
            output_file_path = config.get("output", {}).get("file", FileWriter.DEFAULT_FILENAME)

        # 6. Send summary notification (e.g., email)
        run_end_time = datetime.now()
        run_duration = (run_end_time - run_start_time).total_seconds()
        try:
            # Check if email sending is enabled in config
            if config.get("notifications", {}).get("send_email_summary", False):
                email_sender = EmailSender(config)
                email_sender.send_summary_email(
                    num_fetched=num_fetched,
                    relevant_papers=relevant_papers,
                    run_duration_secs=run_duration,
                    checking_method=checking_method,
                )
            else:
                logger.info("Email summary notification is disabled in config.")
        except Exception as mail_e:
            logger.error(f"Failed to send summary email: {mail_e}", exc_info=True)

    except Exception as e:
        # Catch-all for unexpected errors during the entire job execution
        logger.error(f"❌ An unexpected error occurred during job execution: {e}", exc_info=True)
        # Consider sending a failure notification here if critical


# --- Script Entry Point ---
if __name__ == "__main__":
    print_separator("*")
    logger.info("✨ Initializing ArXiv Paper Monitor ✨")
    print_separator("*")

    # Load configuration
    logger.info("Loading configuration from 'config.yaml'...")
    config_data = load_config("config.yaml")
    if not config_data:
        logger.error("❌ Critical error: Failed to load configuration. Please check 'config.yaml'. Exiting.")
        sys.exit(1)
    logger.info("Configuration loaded successfully.")

    # Log the chosen relevance checking method for visibility on startup
    checking_method_log = config_data.get("relevance_checking_method", "keyword").lower()
    logger.info(f"Relevance checking method set to: '{checking_method_log}'")

    # Prepare the job function with its required configuration
    # This lambda ensures the check_papers function receives the loaded config when called by the scheduler.
    # Type hint validated_config to ensure it's treated as Dict, not Optional[Dict]
    validated_config: Dict[str, Any] = config_data
    job_with_config = lambda: check_papers(validated_config)

    # Initialize and run the scheduler
    logger.info("Initializing scheduler...")
    try:
        scheduler = Scheduler(validated_config, job_with_config)
        logger.info("Starting scheduler main loop...")
        scheduler.run()  # This enters the blocking loop
    except Exception as e:
        # Catch errors during scheduler setup or its main loop execution
        logger.error(f"❌ Critical error during scheduler setup or execution: {e}", exc_info=True)
        logger.error("Application will exit.")
        sys.exit(1)

    # This part is reached only if the scheduler loop exits gracefully (e.g., KeyboardInterrupt)
    logger.info("🛑 ArXiv Paper Monitor stopped.")
    print_separator("*")


def create_relevance_checker(
    config: Dict[str, Any],
) -> Optional[GroqChecker]:
    """Factory function to create an LLM relevance checker instance based on config.

    Reads settings from config['relevance_checker']['llm'].
    Currently supports 'groq'. Returns None if configuration is invalid,
    the provider is unsupported, or initialization fails.

    Args:
        config: The main application configuration dictionary.

    Returns:
        An initialized GroqChecker instance or None on failure.
    """
    # Decision to call this function is made in check_papers
    llm_config = config.get("relevance_checker", {}).get("llm", {})
    provider = llm_config.get("provider")

    if provider == "groq":
        groq_config = llm_config.get("groq", {})
        api_key = groq_config.get("api_key")
        if not api_key:
            logger.error("Groq provider selected, but API key (relevance_checker.llm.groq.api_key) is missing.")
            return None

        try:
            # Pass only required parameters (currently just api_key based on implementation)
            checker_instance = GroqChecker(api_key=api_key)
            # Log the actual model used by the checker instance if accessible
            actual_model = getattr(checker_instance, "model", "[Not Exposed]")  # Safely get model if attr exists
            logger.info(f"Groq relevance checker initialized successfully (Model: {actual_model}).")
            return checker_instance
        except Exception as e:
            logger.error(f"Failed to initialize GroqChecker: {e}", exc_info=True)
            return None

    # elif provider == "anthropic": # Example for future extension
    #     anthropic_config = llm_config.get("anthropic", {})
    #     # ... get API key, model, etc. ...
    #     try:
    #         # return AnthropicChecker(...)
    #     except Exception as e:
    #         logger.error(f"Failed to initialize AnthropicChecker: {e}", exc_info=True)
    #         return None

    else:
        if provider:
            logger.error(
                f"LLM relevance checking selected, but unknown or unsupported provider specified: '{provider}'"
            )
        else:
            logger.error(
                "LLM relevance checking selected, but no provider specified under relevance_checker.llm.provider."
            )
        return None  # Return None if provider is missing, unknown, or unsupported
