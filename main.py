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
from src.filtering.base_filter import BaseFilter
from src.filtering.keyword_filter import KeywordFilter
from src.filtering.sentence_transformer_filter import SentenceTransformerFilter
from src.llm import GroqChecker
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


def create_relevance_checker(config: Dict[str, Any]) -> Optional[BaseFilter]:
    """Creates and configures the appropriate relevance checker based on config."""
    method = config.get("relevance_checking_method", "keyword").lower()
    checker: Optional[BaseFilter] = None
    llm_config = config.get("relevance_checker", {}).get("llm", {})  # Base for LLM settings

    logger.info(f"🔍 Relevance checking method selected: '{method}'")

    try:
        if method == "keyword":
            checker = KeywordFilter()
            # KeywordFilter specifically uses the 'paper_source' part of the config
            if "paper_source" in config:
                # Pass only the relevant part for keyword filter configuration
                checker.configure({"paper_source": config["paper_source"]})
            else:
                logger.error("Keyword filtering selected, but 'paper_source' configuration is missing.")
                return None  # Config error
        elif method == "llm":
            llm_provider = llm_config.get("provider", "").lower()
            if llm_provider == "groq":
                # Instantiate GroqChecker correctly, handling potential missing config
                groq_provider_config = llm_config.get("groq", {})
                api_key = os.getenv("GROQ_API_KEY") or groq_provider_config.get("api_key")
                if not api_key:
                    logger.error(
                        "❌ Groq provider selected, but API key is missing. "
                        "Set GROQ_API_KEY env var or relevance_checker.llm.groq.api_key in config."
                    )
                    return None  # Missing API key is critical

                # Extract other Groq settings with defaults if necessary
                model = groq_provider_config.get("model")  # GroqChecker might have internal default
                batch_size_cfg = groq_provider_config.get("batch_size")
                batch_size = int(batch_size_cfg) if batch_size_cfg is not None else None  # Let GroqChecker handle None
                batch_delay_cfg = groq_provider_config.get("batch_delay_seconds")
                batch_delay = (
                    float(batch_delay_cfg) if batch_delay_cfg is not None else None
                )  # Let GroqChecker handle None

                # Assume GroqChecker is compatible with BaseFilter or fix its inheritance
                # For now, instantiate and let configure handle detailed setup
                checker = GroqChecker(
                    api_key=api_key, model=model, batch_size=batch_size, batch_delay_seconds=batch_delay
                )
                # Configure immediately after instantiation inside this block
                checker.configure(config)
            # Add elif for other LLM providers here
            else:
                logger.error(f"❌ Unknown or unsupported LLM provider specified: '{llm_provider}'")
                return None
        elif method == "local_sentence_transformer":  # Correct identifier used here
            checker = SentenceTransformerFilter()
            # SentenceTransformerFilter expects the full config to find its nested section
            checker.configure(config)
        elif method == "none":
            logger.info("Relevance checking method set to 'none'. All papers will be considered relevant.")
            return None  # No checker needed
        else:
            # This error should now only trigger if the value is truly unknown
            logger.error(f"❌ Unknown relevance_checking_method specified: '{method}'. Defaulting to no check.")
            return None  # Unknown method

        # Log success if checker was created and configured without error above
        if checker:
            actual_model_info = ""
            if isinstance(checker, GroqChecker):
                actual_model_info = f"(Model: {getattr(checker, 'model', '[Not Exposed]')})"
            elif isinstance(checker, SentenceTransformerFilter):
                actual_model_info = f"(Model: {checker.model_name})"
            logger.info(
                f"✅ Successfully created and configured relevance checker: {checker.__class__.__name__} {actual_model_info}"
            )
            return checker
        elif method not in [
            "none",
            "keyword",
            "llm",
            "local_sentence_transformer",
        ]:  # Avoid logging failure for explicitly 'none' or already handled config errors
            logger.error(f"❌ Failed to configure relevance checker for method '{method}'")
            return None  # Configuration failed

    except Exception as e:
        logger.error(
            f"❌ Failed during creation/configuration of relevance checker for method '{method}': {e}", exc_info=True
        )
        return None

    return None  # Fallback


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

        # 4. Determine and Perform Relevance Checking (Refactored)
        checking_method = config.get("relevance_checking_method", "keyword").lower()
        relevant_papers: List[Paper] = []

        if not all_fetched_papers:
            logger.info("ℹ️ No papers fetched from any source, skipping relevance check.")
        else:
            # --- Create and Use the Relevance Checker ---
            # Headline for Relevance Check
            title = "Relevance Checking"
            padding = (80 - len(title) - 2) // 2
            print(f"\x1b[37m{'=' * padding} {title} {'=' * (80 - padding - len(title) - 2)}\x1b[0m")

            relevance_filter = create_relevance_checker(config)

            if relevance_filter:
                logger.info(f"⚙️ Using {relevance_filter.__class__.__name__} to filter {total_fetched} papers...")
                filter_start_time = time.time()
                try:
                    relevant_papers = relevance_filter.filter(all_fetched_papers)
                    filter_duration = time.time() - filter_start_time
                    logger.info(f"Filter processing completed in {filter_duration:.2f} seconds.")
                except Exception as filter_e:
                    logger.error(
                        f"❌ Error during filtering with {relevance_filter.__class__.__name__}: {filter_e}",
                        exc_info=True,
                    )
                    # Fallback: Treat all as relevant? Or none? Let's treat as none if filter fails.
                    relevant_papers = []
                    logger.error("Filter failed, treating no papers as relevant.")

            elif checking_method == "none":
                # Explicitly handle the 'none' case where create_relevance_checker returns None
                logger.info(
                    "ℹ️ No specific relevance check performed (method was 'none'). Treating all fetched papers as relevant."
                )
                relevant_papers = all_fetched_papers
            else:
                # Handle cases where create_relevance_checker returned None due to error or unknown method
                logger.warning(
                    f"⚠️ Relevance checker for method '{checking_method}' could not be created or configured. Defaulting to treating all papers as relevant."
                )
                # Fallback: Treat all fetched papers as relevant if checker failed.
                relevant_papers = all_fetched_papers
            # --- End Relevance Check Logic ---

        # AFTER relevance checking logic:
        # Headline for Relevance Summary
        title = "Relevance Check Summary"
        padding = (80 - len(title) - 2) // 2
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
                        # Check if the handler has the attribute, works for real instances and mocks
                        if hasattr(handler, "output_file"):
                            output_file_path = handler.output_file  # type: ignore
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
