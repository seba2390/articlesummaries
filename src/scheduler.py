import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict

import schedule

logger = logging.getLogger(__name__)


class Scheduler:
    """Handles scheduling and running of the main job."""

    def __init__(self, config: Dict[str, Any], job_func: Callable):
        """
        Initializes the Scheduler.

        Args:
            config: The application configuration dictionary.
            job_func: The function to be scheduled and run.
        """
        self.config = config
        self.job_func = job_func
        self.run_time = config.get("run_time_daily", "08:00")

    def run(self):
        """Sets up the schedule and runs the job loop."""
        logger.info(f"Scheduling job daily at {self.run_time}")
        schedule.every().day.at(self.run_time).do(self.job_func)

        # Run once immediately on startup (optional, consider making configurable)
        logger.info("Running initial check on startup...")
        try:
            self.job_func()
            logger.info("Initial check complete. Waiting for scheduled time...")
        except Exception as e:
            logger.error(f"Error during initial job execution: {e}", exc_info=True)
            # Decide if we should exit or continue waiting for schedule

        # Keep the script running
        while True:
            try:
                schedule.run_pending()
                # Sleep for a longer interval if possible to reduce CPU usage
                next_run_candidate = schedule.next_run
                # Check if it's actually a datetime object before using it
                if isinstance(next_run_candidate, datetime):
                    next_run_time: datetime = next_run_candidate  # Now we know it's a datetime
                    # Ensure calculation happens only when next_run_time is a datetime object
                    sleep_duration = max(1, (next_run_time - datetime.now()).total_seconds() / 2)  # Sleep half way
                    sleep_duration = min(sleep_duration, 60)  # Max sleep 60 seconds
                else:
                    # Handle cases where next_run is None or something else (like a function?)
                    sleep_duration = 60  # Default if no valid next run time
                time.sleep(sleep_duration)
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user (KeyboardInterrupt).")
                break
            except Exception as e:
                logger.error(f"An error occurred in the scheduler loop: {e}", exc_info=True)
                # Avoid busy-looping on persistent errors
                time.sleep(60)
