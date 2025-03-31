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
from datetime import datetime

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
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
    1. Instantiates the paper source, filter, and output handler components.
       (Currently hardcoded to ArxivSource, KeywordFilter, FileWriter).
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
    # TODO: Consider dynamic loading based on config for greater flexibility
    logger.debug("Instantiating components: ArxivSource, KeywordFilter, FileWriter")
    try:
        paper_source = ArxivSource()
        paper_filter = KeywordFilter()
        output_handler = FileWriter()
    except Exception as e:
        logger.error(f"Fatal error instantiating components: {e}", exc_info=True)
        logger.error("Job cannot proceed.")
        return  # Exit job if components can't be created

    # --- Configure components ---
    logger.debug("Configuring components...")
    try:
        # Pass the whole config; components extract their relevant parts.
        paper_source.configure(config)
        paper_filter.configure(config)
        output_handler.configure(config)
        logger.debug("Components configured successfully.")
    except KeyError as e:
        # Catch specific errors if a required config key is missing
        logger.error(f"Configuration error during component setup: Missing key {e}")
        logger.error("Job cannot proceed due to configuration error.")
        return  # Stop job if config is bad
    except Exception as e:
        # Catch other unexpected errors during configuration
        logger.error(f"Unexpected error configuring components: {e}", exc_info=True)
        logger.error("Job cannot proceed due to configuration error.")
        return

    # --- Execute workflow ---
    # Wrap the core logic in a try-except to catch runtime errors
    try:
        # 1. Fetching Papers
        print_separator("-")
        logger.info("🔎 Fetching papers...")
        fetch_start_time = datetime.now()
        papers = paper_source.fetch_papers()
        fetch_duration = datetime.now() - fetch_start_time
        if not papers:
            logger.info(f"-> No new papers found matching criteria. (Duration: {fetch_duration.total_seconds():.2f}s)")
        else:
            logger.info(
                f"-> Fetched {len(papers)} papers matching date criteria. (Duration: {fetch_duration.total_seconds():.2f}s)"
            )

        # 2. Filtering Papers (only if papers were fetched)
        relevant_papers = []
        if papers:
            print_separator("-")
            logger.info("🔍 Filtering papers by keywords...")
            filter_start_time = datetime.now()
            relevant_papers = paper_filter.filter(papers)
            filter_duration = datetime.now() - filter_start_time
            logger.info(
                f"-> Found {len(relevant_papers)} relevant papers. (Duration: {filter_duration.total_seconds():.2f}s)"
            )
        else:
            # Log skipping only if papers were expected but none found
            if paper_source.categories:  # Check if source was configured to fetch anything
                logger.info("-> Skipping keyword filtering as no papers matched date criteria.")
            # If no categories were configured, fetch_papers would log skipping.

        # 3. Outputting Results (only if relevant papers were found)
        if relevant_papers:
            print_separator("-")
            logger.info("💾 Processing output...")
            output_start_time = datetime.now()
            output_handler.output(relevant_papers)
            output_duration = datetime.now() - output_start_time
            # Output handler logs success/details internally
            logger.info(f"-> Output processing finished. (Duration: {output_duration.total_seconds():.2f}s)")
        else:
            # Log skipping only if papers were fetched but none were relevant
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
        # Catch unexpected errors during the fetch-filter-output workflow
        logger.error(f"❌ An unexpected error occurred during job execution: {e}", exc_info=True)
        print_separator("!")
        logger.error("❗ Job execution failed unexpectedly.")
        print_separator("!")


# --- Script Entry Point ---
if __name__ == "__main__":
    print_separator("*")
    logger.info("✨ Initializing ArXiv Paper Monitor ✨")
    print_separator("*")

    # Load configuration
    logger.info("Loading configuration from 'config.yaml'...")
    config = load_config("config.yaml")
    if not config:
        # Error is logged by load_config
        logger.error("❌ Critical error: Failed to load configuration. Please check 'config.yaml'. Exiting.")
        sys.exit(1)
    logger.info("Configuration loaded successfully.")

    # --- Prepare the job function for the scheduler ---
    # Wrap main_job in a lambda to pass the loaded config easily
    job_with_config = lambda: main_job(config)

    # --- Initialize and run the scheduler ---
    logger.info("Initializing scheduler...")
    try:
        scheduler = Scheduler(config, job_with_config)
        logger.info("Starting scheduler main loop...")
        # The scheduler.run() method blocks until interrupted (e.g., Ctrl+C)
        scheduler.run()
    except Exception as e:
        # Catch potential errors during Scheduler initialization or run setup
        logger.error(f"❌ Critical error during scheduler setup or execution: {e}", exc_info=True)
        logger.error("Application will exit.")
        sys.exit(1)

    # This line is typically reached only after graceful shutdown (e.g., Ctrl+C in scheduler loop)
    logger.info("🛑 ArXiv Paper Monitor stopped.")
    print_separator("*")
