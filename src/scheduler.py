"""Manages the scheduling and execution of the main monitoring job.

Uses the `schedule` library to run a provided job function at a configured
daily time. Includes logic for an initial run on startup and a continuous
loop to check for pending jobs.
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict

import schedule

logger = logging.getLogger(__name__)


class Scheduler:
    """Handles scheduling and running of the main monitoring job."""

    def __init__(self, config: Dict[str, Any], job_func: Callable):
        """Initializes the Scheduler.

        Args:
            config: The application configuration dictionary, expected to contain
                    'run_time_daily' for scheduling.
            job_func: The function (job) to be scheduled and executed.
                      This function should ideally handle its own exceptions.
        """
        self.config = config
        self.job_func = job_func
        # Default to 08:00 if not specified in config
        self.run_time = config.get("run_time_daily", "08:00")
        logger.info(f"Scheduler initialized. Daily run time: {self.run_time}")

    def run(self):
        """Sets up the daily schedule and runs the main execution loop.

        This method configures the job to run daily at the specified time.
        It performs one immediate run upon startup and then enters a loop,
        periodically checking for and running pending scheduled jobs.
        The loop continues until interrupted (e.g., by KeyboardInterrupt).
        """
        logger.info(f"Scheduling job to run daily at {self.run_time}...")
        try:
            schedule.every().day.at(self.run_time).do(self.job_func)
            logger.info("Job scheduled successfully.")
        except Exception as e:
            logger.error(f"Failed to schedule job at '{self.run_time}'. Error: {e}", exc_info=True)
            logger.error("Scheduler cannot start. Exiting.")
            return  # Cannot proceed if scheduling fails

        # Optional: Run once immediately on startup.
        # Consider making this behavior configurable in config.yaml.
        logger.info("Performing initial job run on startup...")
        try:
            self.job_func()
            logger.info("Initial job run completed.")
        except Exception as e:
            logger.error(f"Error during initial job execution: {e}", exc_info=True)
            # Continue running the scheduler even if the initial job fails
            logger.warning("Scheduler will continue waiting for the next scheduled run despite initial job error.")

        logger.info("Scheduler started. Waiting for pending jobs... (Press Ctrl+C to stop)")
        # Main execution loop
        while True:
            # Define default sleep duration outside try block to ensure it's always bound
            sleep_duration = 60  # Default sleep interval in seconds
            try:
                # Check and run any jobs that are due
                schedule.run_pending()

                # --- Smart sleep calculation ---
                # Determine how long to sleep until the next job or for a default interval.
                # This prevents constant checking and reduces CPU usage.
                next_run_candidate = schedule.next_run

                if isinstance(next_run_candidate, datetime):
                    next_run_time: datetime = next_run_candidate
                    now = datetime.now()
                    # Calculate time until next run in seconds
                    wait_seconds = (next_run_time - now).total_seconds()

                    # Sleep for half the duration until the next job,
                    # but at least 1 second and at most the default 60 seconds.
                    calculated_sleep = max(1, wait_seconds / 2)
                    sleep_duration = min(calculated_sleep, 60)
                    logger.debug(f"Next job at {next_run_time}. Sleeping for {sleep_duration:.1f}s.")
                else:
                    # No jobs scheduled or next_run is not a datetime
                    logger.debug(f"No upcoming scheduled job found. Sleeping for default {sleep_duration}s.")

                time.sleep(sleep_duration)

            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received. Stopping scheduler...")
                break  # Exit the loop gracefully
            except Exception as e:
                # Catch unexpected errors within the loop itself
                logger.error(f"An unexpected error occurred in the scheduler loop: {e}", exc_info=True)
                # Avoid busy-looping on persistent errors by sleeping for the default interval
                logger.warning(f"Scheduler loop encountered error. Sleeping for {sleep_duration}s before retrying.")
                time.sleep(sleep_duration)

        logger.info("Scheduler stopped.")
