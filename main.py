"""Main execution script for the arXiv Paper Monitor.

This script orchestrates the application flow:
1. Initializes logging.
2. Loads configuration from `config.yaml`.
3. Sets up the main monitoring job (`main_job`).
4. Initializes the scheduler (`src.scheduler.Scheduler`).
5. Starts the scheduler to run the job periodically.
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import colorlog

from src.config_loader import load_config
from src.filtering.keyword_filter import KeywordFilter
from src.llm import GroqChecker
from src.llm.base_checker import BaseLLMChecker
from src.notifications.email_sender import EmailSender
from src.output.base_output import BaseOutput
from src.output.file_writer import FileWriter
from src.paper import Paper
from src.paper_sources.arxiv_source import ArxivSource
from src.paper_sources.base_source import BasePaperSource
from src.paper_sources.biorxiv_source import BiorxivSource
from src.paper_sources.medrxiv_source import MedrxivSource
from src.scheduler import Scheduler

# --- Logging Configuration ---
# Use colorlog handler
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
)

# Get the root logger and configure it
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)

# Use a specific logger for main, inheriting the root configuration
logger = logging.getLogger("main")

# Remove the old basicConfig call if it exists (idempotent)
# Ensure no duplicate handlers if script is re-run in some environments
for h in logging.root.handlers[:]:
    if isinstance(h, logging.StreamHandler) and not isinstance(h, colorlog.StreamHandler):
        logging.root.removeHandler(h)


# --- Utility Functions ---
def print_separator(char="=", length=70):
    """Prints a separator line to the console for better visual structure."""
    print(char * length)


# --- Factory Functions ---


def create_paper_source(source_name: str, config: Dict[str, Any]) -> Optional[BasePaperSource]:
    """Factory function to create a paper source instance based on name and config.

    Args:
        source_name: The name of the source (e.g., 'arxiv', 'biorxiv').
        config: The main application configuration dictionary.

    Returns:
        An initialized BasePaperSource instance or None if the source is unknown
        or configuration fails.
    """
    source_name_lower = source_name.lower()
    logger.debug(f"Attempting to create paper source: {source_name_lower}")

    source_instance: Optional[BasePaperSource] = None

    try:
        if source_name_lower == "arxiv":
            source_instance = ArxivSource()
        elif source_name_lower == "biorxiv":
            source_instance = BiorxivSource()
        elif source_name_lower == "medrxiv":
            source_instance = MedrxivSource()
        # elif source_name_lower == "chemrxiv": # Remove chemrxiv case
        #     source_instance = ChemrxivSource()
        # Add other sources here with elif source_name_lower == "other_source":
        else:
            logger.error(f"❌ Unknown paper source specified: '{source_name}'")
            return None

        # Configure the created instance only if it was successfully created
        if source_instance:
            # Pass the entire config; the instance's configure method
            # should know how to extract its relevant section.
            source_instance.configure(config, source_name_lower)
            logger.info(f"✅ Successfully created and configured paper source: {source_name}")
            return source_instance
        else:
            # This case should theoretically not be reached if the logic above is correct,
            # but handles potential unexpected states.
            logger.error(f"❌ Source instance for '{source_name}' was not created, cannot configure.")
            return None

    except Exception as e:
        logger.error(
            f"❌ Failed to create or configure paper source '{source_name}': {e}",
            exc_info=True,  # Include stack trace for debugging
        )
        return None


def create_relevance_checker(
    config: Dict[str, Any],
) -> Optional[BaseLLMChecker]:
    """Factory function to create an LLM relevance checker instance based on config.

    Reads settings from config['relevance_checker']['llm'].
    Currently supports 'groq'. Returns None if configuration is invalid,
    the provider is unsupported, or initialization fails.

    Args:
        config: The main application configuration dictionary.

    Returns:
        An initialized BaseLLMChecker instance or None on failure.
    """
    llm_config = config.get("relevance_checker", {}).get("llm", {})
    provider = llm_config.get("provider")

    if provider == "groq":
        groq_config = llm_config.get("groq", {})
        api_key = os.getenv("GROQ_API_KEY") or groq_config.get("api_key")

        if not api_key:
            logger.error(
                "❌ Groq provider selected, but API key is missing. "
                "Set GROQ_API_KEY env var or relevance_checker.llm.groq.api_key in config."
            )
            return None

        try:
            model = groq_config.get("model")
            batch_size_cfg = groq_config.get("batch_size")
            batch_size = int(batch_size_cfg) if batch_size_cfg is not None else None
            batch_delay_cfg = groq_config.get("batch_delay_seconds")
            batch_delay = float(batch_delay_cfg) if batch_delay_cfg is not None else None

            checker_instance = GroqChecker(
                api_key=api_key, model=model, batch_size=batch_size, batch_delay_seconds=batch_delay
            )
            actual_model = getattr(checker_instance, "model", "[Not Exposed]")
            logger.info(f"✅ Groq relevance checker initialized successfully (Model: {actual_model}).")
            return checker_instance  # Return the instance
        except Exception as e:
            logger.error(f"❌ Failed to initialize GroqChecker: {e}", exc_info=True)
            return None
    # elif provider == "other_provider": ...
    else:
        if provider:
            logger.error(f"❌ LLM checking selected, but unknown provider: '{provider}'")
        else:
            logger.error("❌ LLM checking selected, but no provider specified.")
        return None


def create_output_handlers(config: Dict[str, Any]) -> List[BaseOutput]:
    """Creates and configures output handlers based on the config.

    Currently hardcoded to create only a FileWriter.
    Could be extended to support multiple output types (e.g., database, console).

    Args:
        config: The main application configuration dictionary.

    Returns:
        A list containing configured BaseOutput instances.
    """
    handlers = []
    output_config = config.get("output", {})

    # For now, always try to create a FileWriter
    try:
        file_writer = FileWriter()
        file_writer.configure(output_config)
        handlers.append(file_writer)
        logger.info(f"💾 File output handler configured for path: {file_writer.output_file}")
    except Exception as e:
        logger.error(f"❌ Failed to create or configure FileWriter output handler: {e}", exc_info=True)

    # Add logic for other handlers here if needed

    return handlers


# --- Main Job Definition ---
def check_papers(config: Dict[str, Any]) -> None:
    """Fetches papers from active sources, checks relevance, saves, and notifies.

    This is the core function executed by the scheduler.

    Args:
        config: The application configuration dictionary.
    """
    run_start_time = datetime.now()
    total_fetched = 0
    total_relevant = 0
    all_fetched_papers: List[Paper] = []  # Store papers from all sources
    source_stats: Dict[str, Dict[str, Any]] = {}  # Store detailed stats per source

    try:
        # 1. Get active sources from config
        active_sources = config.get("active_sources", [])
        if not active_sources or not isinstance(active_sources, list):
            logger.error(
                "❌ No active paper sources specified or format is invalid in config ('active_sources'). Cannot proceed."
            )
            return

        # logger.info(f"🚀 Starting check for active sources: {active_sources}") # Keep this log
        # print_separator("=", 80) # Replaced by headline below

        # 2. Initialize paper sources
        source_instances: Dict[str, BasePaperSource] = {}
        for source_name in active_sources:
            instance = create_paper_source(source_name, config)
            if instance:
                source_instances[source_name] = instance
            else:
                logger.warning(f"⚠️ Failed to create paper source: {source_name}")

        if not source_instances:
            logger.error("❌ No active paper sources were successfully initialized. Exiting job.")
            return

        # Headline added before the fetch loop starts
        title = "Starting Paper Fetch"
        padding = (80 - len(title) - 2) // 2
        # Use print with ANSI codes for light grey color
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")

        # 3. Fetch papers from each source
        run_start_time = datetime.now(timezone.utc)

        for name, instance in source_instances.items():
            print_separator("-", 80)  # Keep the simple separator between sources
            logger.info(f"--- Starting Fetch: {name.capitalize()} ---")
            logger.info(f"📡 Fetching from {name} (window: {instance.fetch_window_days} days)... ")
            end_time_utc = run_start_time
            start_time_utc = end_time_utc - timedelta(days=instance.fetch_window_days)

            try:
                fetched_papers: List[Paper] = instance.fetch_papers(start_time_utc, end_time_utc)
                count = len(fetched_papers)
                logger.info(f"🔢 -> Fetched {count} papers from {name}.")
                all_fetched_papers.extend(fetched_papers)
                # Store detailed stats including the times used for this fetch
                source_stats[name] = {
                    "fetched": count,
                    "instance": instance,
                    "start_time": start_time_utc,
                    "end_time": end_time_utc,
                }
                logger.info(
                    f"--- Finished Fetch: {name.capitalize()} ({'Error' if 'error' in source_stats[name] else count}) ---"
                )  # Simplified finished log
            except Exception as fetch_e:
                logger.error(f"❌ Error fetching papers from {name}: {fetch_e}", exc_info=True)
                # Store failure info or default values?
                source_stats[name] = {
                    "fetched": 0,
                    "instance": instance,  # Keep instance to report window days
                    "start_time": start_time_utc,
                    "end_time": end_time_utc,
                    "error": str(fetch_e),
                }
                logger.info(f"--- Finished Fetch: {name.capitalize()} (Error) ---")

        # AFTER the fetch loop:
        # Headline for Fetch Summary
        title = "Fetch Summary"
        padding = (80 - len(title) - 2) // 2
        # Use print with ANSI codes for light grey color
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
        total_fetched = sum(stats["fetched"] for stats in source_stats.values())
        logger.info(f"📚 Total papers fetched across all sources: {total_fetched}")

        # 4. Determine the relevance checking method
        checking_method = config.get("relevance_checking_method", "keyword").lower()
        llm_checker = None
        keyword_filter = None  # Initialize keyword filter
        relevant_papers: List[Paper] = []

        if not all_fetched_papers:
            logger.info("ℹ️ No papers fetched from any source, skipping relevance check.")
        else:
            if checking_method == "llm":
                llm_checker = create_relevance_checker(config)
                if llm_checker:
                    logger.info(f"🤖🔍 Checking relevance of {total_fetched} papers using LLM...")
                    # --- LLM Check Path ---
                    # LLM provider specific config is now nested under the provider name
                    llm_provider_config = (
                        config.get("relevance_checker", {}).get("llm", {}).get(llm_checker.provider_name, {})
                    )
                    prompt = llm_provider_config.get("prompt", "Is this paper relevant?")
                    confidence_threshold = llm_provider_config.get("confidence_threshold", 0.7)
                    abstracts = [p.abstract for p in all_fetched_papers if p.abstract]  # Ensure abstract exists
                    papers_with_abstracts = [p for p in all_fetched_papers if p.abstract]
                    if abstracts:
                        llm_batch_start_time = time.time()
                        try:
                            responses = llm_checker.check_relevance_batch(abstracts, prompt)
                            duration = time.time() - llm_batch_start_time
                            logger.info(f"LLM batch processing completed in {duration:.2f} seconds.")
                            for paper, response in zip(papers_with_abstracts, responses):
                                if response.is_relevant and response.confidence >= confidence_threshold:
                                    paper.relevance = {
                                        "confidence": response.confidence,
                                        "explanation": response.explanation,
                                    }
                                    relevant_papers.append(paper)
                                else:
                                    logger.debug(f"Paper {paper.id} ({paper.source}) not relevant via LLM.")
                        except Exception as llm_e:
                            logger.error(f"❌ Error during LLM batch relevance check: {llm_e}", exc_info=True)
                    else:
                        logger.warning("⚠️ No abstracts found in fetched papers for LLM checking.")
                else:
                    logger.warning("⚠️ LLM checking selected, but checker failed. Falling back to no check.")
                    checking_method = "none"  # Fallback

            if checking_method == "keyword":  # Check again in case LLM failed
                # --- Keyword Check Path ---
                logger.info(f"🔑🔍 Filtering {total_fetched} papers using keywords defined per source...")
                # Create ONE filter instance, but configure it differently for each source's papers
                keyword_filter = KeywordFilter()  # Create instance outside the loop
                filtered_by_source = []

                # Group papers by source first
                papers_by_source: Dict[str, List[Paper]] = {}
                for paper in all_fetched_papers:
                    papers_by_source.setdefault(paper.source, []).append(paper)

                # Filter papers for each source using its specific keywords
                for source_name, papers_from_source in papers_by_source.items():
                    source_config = config.get("paper_source", {}).get(source_name, {})
                    source_keywords = source_config.get("keywords", [])

                    if not source_keywords:
                        logger.warning(
                            f"⚠️ No keywords found for source '{source_name}'. Skipping keyword filtering for these papers."
                        )
                        # If no keywords, treat all papers from this source as relevant for keyword check?
                        # Or skip them? For now, let's skip adding them if keywords are expected.
                        # If you want all papers when keywords are missing, add: filtered_by_source.extend(papers_from_source)
                        continue  # Skip to next source

                    # Configure the filter *specifically* for this source's keywords
                    temp_config_for_filter = {"paper_source": {source_name: {"keywords": source_keywords}}}
                    keyword_filter.configure(temp_config_for_filter)

                    # Filter only the papers from the current source
                    relevant_from_source = keyword_filter.filter(papers_from_source)
                    logger.info(
                        f" -> Source '{source_name}': Found {len(relevant_from_source)} papers matching keywords: {source_keywords}"
                    )
                    filtered_by_source.extend(relevant_from_source)

                relevant_papers = filtered_by_source  # Assign the final list

            if checking_method == "none":  # Handle explicit 'none' or fallback
                logger.info("ℹ️ No specific relevance check performed. Treating all fetched papers as relevant.")
                relevant_papers = all_fetched_papers

        # AFTER relevance checking logic:
        # Headline for Relevance Summary
        title = "Relevance Check Summary"
        padding = (80 - len(title) - 2) // 2
        # Use print with ANSI codes for light grey color
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
        total_relevant = len(relevant_papers)
        logger.info(f"✅ Found {total_relevant} relevant papers across all sources after checking.")

        # 5. Output relevant papers
        # Headline for Output Section
        title = "Outputting Relevant Papers"
        padding = (80 - len(title) - 2) // 2
        # Use print with ANSI codes for light grey color
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
        output_file_path = None
        if relevant_papers:
            output_handlers = create_output_handlers(config)  # Create handlers only if there are papers
            if not output_handlers:
                logger.warning("⚠️ Relevant papers found, but failed to create any output handlers.")
            else:
                for handler in output_handlers:
                    try:
                        logger.info(f"💾 Writing {len(relevant_papers)} papers using {type(handler).__name__}...")
                        handler.output(relevant_papers)
                        # Try to get output path from file writer specifically
                        if isinstance(handler, FileWriter):
                            output_file_path = handler.output_file
                            logger.info(f"📄 -> Output successful to {output_file_path}")
                    except Exception as out_e:
                        logger.error(f"❌ Error using output handler {type(handler).__name__}: {out_e}", exc_info=True)
        else:
            logger.info("ℹ️ No relevant papers to output.")
            # If no relevant papers, still get the *configured* path for the email summary
            output_file_path = config.get("output", {}).get("file", FileWriter.DEFAULT_FILENAME)

        # AFTER output logic:
        if not relevant_papers:
            output_file_path = config.get("output", {}).get("file", FileWriter.DEFAULT_FILENAME)

        # 6. Send summary notification
        # Headline for Notification Section
        title = "Sending Notifications"
        padding = (80 - len(title) - 2) // 2
        # Use print with ANSI codes for light grey color
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
        run_end_time = datetime.now(timezone.utc)  # Make timezone-aware
        run_duration = (run_end_time - run_start_time).total_seconds()
        # Directly check config and instantiate EmailSender if needed
        notification_handler = None
        # Check the TOP-LEVEL key for enabling email summary, as defined in main_config.yaml
        if config.get("send_email_summary", False):
            try:
                # Add the missing EmailSender instantiation
                notification_handler = EmailSender(config)
                logger.info("📧 Email notification handler initialized.")

                # Prepare run_stats dictionary
                # Extract source details for the summary section
                sources_summary_for_email = {}
                for name, stats in source_stats.items():
                    source_instance = stats.get("instance")
                    fetch_window = source_instance.fetch_window_days if source_instance else "N/A"
                    sources_summary_for_email[name] = {
                        "fetched": stats.get("fetched", "Error"),
                        "fetch_window_days": fetch_window,
                        "start_time": stats.get("start_time"),  # Pass through the actual times
                        "end_time": stats.get("end_time"),
                    }

                run_stats = {
                    "total_fetched": total_fetched,
                    "total_relevant": total_relevant,
                    "run_duration_secs": run_duration,
                    "checking_method": checking_method,
                    "sources_summary": sources_summary_for_email,  # Use the detailed summary
                    # Removed overall_start_time and overall_end_time
                    "output_file_path": output_file_path,
                    "run_completed_time": run_end_time,  # Add actual completion time
                }

                # EmailSender expects send_summary_email, let's call that directly if it's the only handler
                if notification_handler is not None and hasattr(notification_handler, "send_summary_email"):
                    logger.info("📧 Sending email summary to configured recipients...")
                    notification_handler.send_summary_email(relevant_papers=relevant_papers, run_stats=run_stats)
                    logger.info("📧 -> Email summary sent successfully.")

            except Exception as mail_e:
                logger.error(f"❌ Failed to send notification: {mail_e}", exc_info=True)

    except Exception as e:
        logger.error(f"❌ An unexpected error occurred during the main check_papers job: {e}", exc_info=True)
        # Headline for Job Error - print in light grey
        title = "Job Error"
        padding = (80 - len(title) - 2) // 2
        print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")


# --- Script Entry Point ---
if __name__ == "__main__":
    # Fancy main headline v3 in light grey (adjusted padding)
    width = 80
    top_border = f"\x1b[37m╔{'═' * (width - 2)}╗\x1b[0m"
    bottom_border = f"\x1b[37m╚{'═' * (width - 2)}╝\x1b[0m"
    empty_line = f"\x1b[37m║{' ' * (width - 2)}║\x1b[0m"
    title_text = "✨📰 Multi-Source Paper Monitor 🚀✨"

    # Estimate visual width and calculate padding explicitly
    estimated_visual_width = 36  # Recalculated based on emojis=2, text=26, spaces=2
    total_padding = width - estimated_visual_width - 2  # width=80, total_padding=42
    left_padding = total_padding // 2  # left_padding=21
    right_padding = total_padding - left_padding  # right_padding=21

    title_line = f"\x1b[37m║{' ' * left_padding}{title_text}{' ' * right_padding}║\x1b[0m"

    print(top_border)
    print(empty_line)
    print(title_line)
    print(empty_line)
    print(bottom_border)
    print()  # Add a blank line for spacing

    # Load configuration
    title = "Configuration Loading"
    padding = (80 - len(title) - 2) // 2
    # Use print with ANSI codes for light grey color
    print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
    logger.info("⚙️ Loading configuration from main_config.yaml and configs directory...")  # Keep logs green
    config_data = load_config()
    if not config_data:
        logger.critical("❌ Critical error: Failed to load configuration. Exiting.")
        sys.exit(1)
    logger.info("✅ Configuration loaded successfully.")  # Keep logs green

    # Log active sources and checking method
    title = "Application Settings"
    padding = (80 - len(title) - 2) // 2
    # Use print with ANSI codes for light grey color
    print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
    active_sources_log = config_data.get("active_sources", "[Not Configured]")
    logger.info(f"🔌 Active paper sources: {active_sources_log}")
    checking_method_log = config_data.get("relevance_checking_method", "keyword").lower()
    logger.info(f"🔍 Relevance checking method: '{checking_method_log}'")

    # Validate essential config sections for scheduler
    if "schedule" not in config_data:
        logger.critical("❌ Configuration missing 'schedule' section. Cannot schedule job. Exiting.")
        sys.exit(1)

    # Prepare the job function
    validated_config: Dict[str, Any] = config_data
    job_with_config = lambda: check_papers(validated_config)

    # Initialize and run the scheduler
    title = "Scheduler Setup"
    padding = (80 - len(title) - 2) // 2
    # Use print with ANSI codes for light grey color
    print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")
    logger.info("⏳ Initializing scheduler...")  # Keep logs green
    try:
        scheduler = Scheduler(validated_config, job_with_config)
        logger.info("⏳ Starting scheduler...")  # Keep logs green
        scheduler.run()
    except Exception as e:
        logger.critical(f"❌ Critical error during scheduler setup or run: {e}", exc_info=True)
        # Headline for critical scheduler error - print in light grey with '!'
        title = "Scheduler Critical Error"
        padding = (80 - len(title) - 2) // 2
        print(f"\x1b[37m{'!' * padding} {title} {'!' * (80 - padding - len(title) - 2)}\x1b[0m")
        sys.exit(1)

    # AFTER scheduler stops
    print_separator("*", 80)  # Keep asterisk separators for the end
    logger.info("🛑 Multi-Source Paper Monitor stopped.")
    print_separator("*", 80)
