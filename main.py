import logging
import sys
from datetime import datetime

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
from src.output.file_writer import FileWriter
from src.paper_sources.arxiv_source import ArxivSource
from src.scheduler import Scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)  # Ensure logs go to stdout
    ],
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger()


def print_separator(char="=", length=70):
    """Prints a separator line to the console."""
    print(char * length)


def main_job(config):
    """Defines the main job to fetch, filter, and output papers."""
    run_start_time = datetime.now()
    print_separator()
    logger.info("🚀 Starting Daily Paper Check...")
    print_separator()

    # --- Instantiate components ---
    logger.debug("Instantiating components...")
    paper_source = ArxivSource()
    paper_filter = KeywordFilter()
    output_handler = FileWriter()

    # --- Configure components ---
    logger.debug("Configuring components...")
    try:
        paper_source.configure(config)
        paper_filter.configure(config)
        output_handler.configure(config)
    except KeyError as e:
        logger.error(f"Configuration error: Missing key {e}")
        return  # Stop job if config is bad
    except Exception as e:
        logger.error(f"Error configuring components: {e}", exc_info=True)
        return

    # --- Execute workflow ---
    try:
        # 1. Fetching
        print_separator("-")
        logger.info("🔎 Fetching papers from configured sources...")
        fetch_start_time = datetime.now()
        papers = paper_source.fetch_papers()
        fetch_duration = datetime.now() - fetch_start_time
        if not papers:
            logger.info(
                f"-> No new papers found matching the criteria (last 24h) in {fetch_duration.total_seconds():.2f} seconds."
            )
        else:
            logger.info(
                f"-> Fetched and date-filtered {len(papers)} papers in {fetch_duration.total_seconds():.2f} seconds."
            )

        # 2. Filtering (only if papers were found after date filtering)
        relevant_papers = []
        if papers:
            print_separator("-")
            logger.info("🔍 Filtering fetched papers by keywords...")
            filter_start_time = datetime.now()
            relevant_papers = paper_filter.filter(papers)
            filter_duration = datetime.now() - filter_start_time
            logger.info(
                f"-> Found {len(relevant_papers)} relevant papers in {filter_duration.total_seconds():.2f} seconds."
            )
        else:
            logger.info("-> Skipping keyword filtering as no papers matched date criteria.")

        # 3. Outputting (only if relevant papers were found)
        if relevant_papers:
            print_separator("-")
            logger.info("💾 Processing output for relevant papers...")
            output_start_time = datetime.now()
            output_handler.output(relevant_papers)
            output_duration = datetime.now() - output_start_time
            logger.info(f"-> Output processed in {output_duration.total_seconds():.2f} seconds.")
        else:
            logger.info("-> No relevant papers to output.")

        run_duration = datetime.now() - run_start_time
        print_separator()
        logger.info(f"✅ Daily Paper Check Finished. Total duration: {run_duration.total_seconds():.2f} seconds.")
        print_separator()

    except Exception as e:
        logger.error(f"❌ An error occurred during the main job execution: {e}", exc_info=True)
        print_separator("!")
        logger.error("❗ Job execution failed.")
        print_separator("!")


if __name__ == "__main__":
    print_separator("*")
    logger.info("✨ Initializing ArXiv Paper Monitor ✨")
    print_separator("*")

    # Load configuration
    logger.info("Loading configuration from 'config.yaml'...")
    config = load_config("config.yaml")
    if not config:
        logger.error("❌ Failed to load configuration. Please check 'config.yaml'. Exiting.")
        sys.exit(1)
    logger.info("Configuration loaded successfully.")

    # --- Prepare the job function with the loaded config ---
    job_with_config = lambda: main_job(config)

    # --- Initialize and run the scheduler ---
    scheduler = Scheduler(config, job_with_config)
    scheduler.run()

    logger.info("🛑 ArXiv Paper Monitor stopped.")
    print_separator("*")
