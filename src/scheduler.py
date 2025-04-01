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

# Set up logger for this module first
logger = logging.getLogger(__name__)

# Try importing timezone utilities
try:
    # Use zoneinfo available in Python 3.9+
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    _pytz_available = False
except ImportError:
    try:
        # Fallback to pytz if available
        from pytz import UnknownTimeZoneError as ZoneInfoNotFoundError
        from pytz import timezone as ZoneInfo

        _pytz_available = True
        logger.info("Using pytz for timezone support.")
    except ImportError:
        ZoneInfo = None
        ZoneInfoNotFoundError = Exception  # Base Exception for except block
        _pytz_available = False
        logger.warning("Neither zoneinfo (Python 3.9+) nor pytz found. Timezone support is disabled.")


class Scheduler:
    """Handles scheduling and running of the main monitoring job."""

    def __init__(self, config: Dict[str, Any], job_func: Callable):
        """Initializes the Scheduler.

        Args:
            config: The application configuration dictionary. Reads:
                    - config['schedule']['run_time']
                    - config['schedule']['timezone'] (optional)
            job_func: The function (job) to be scheduled and executed.
        """
        self.config = config
        self.job_func = job_func

        schedule_config = config.get("schedule", {})
        self.run_time = schedule_config.get("run_time", "08:00")  # Default to 08:00
        self.timezone_str = schedule_config.get("timezone")
        # self.timezone_info = None # Removed, schedule library handles tz string directly

        # Validate timezone string if provided and library exists
        if self.timezone_str and ZoneInfo:
            try:
                # Attempt to load the timezone to check validity
                _ = ZoneInfo(self.timezone_str)
                logger.info(f"Scheduler will use timezone: {self.timezone_str}")
            except ZoneInfoNotFoundError:
                logger.error(
                    f"Invalid timezone '{self.timezone_str}' specified in config. Falling back to system local time."
                )
                self.timezone_str = None  # Clear invalid timezone
            except Exception as e:
                logger.error(f"Error loading timezone '{self.timezone_str}': {e}. Falling back to system local time.")
                self.timezone_str = None
        elif self.timezone_str:
            logger.warning(
                "Timezone specified in config, but timezone library (zoneinfo/pytz) not available. Using system local time."
            )
            self.timezone_str = None  # Cannot use it if library missing

        tz_msg = f" ({self.timezone_str})" if self.timezone_str else " (local time)"
        logger.info(f"Scheduler initialized. Daily run time: {self.run_time}{tz_msg}")

    def run(self):
        """Sets up the daily schedule and runs the main execution loop.

        This method configures the job to run daily at the specified time.
        It performs one immediate run upon startup and then enters a loop,
        periodically checking for and running pending scheduled jobs.
        The loop continues until interrupted (e.g., by KeyboardInterrupt).
        """
        logger.info(
            f"Scheduling job to run daily at {self.run_time}{' (' + self.timezone_str + ')' if self.timezone_str else ' (local time)'}..."
        )
        try:
            # Pass the timezone string directly to schedule if available
            schedule.every().day.at(self.run_time, self.timezone_str).do(self.job_func)
            logger.info("Job scheduled successfully.")
        except TypeError as e:
            # Handle potential TypeError if schedule doesn't support tz parameter (older versions?)
            if "unexpected keyword argument 'tz'" in str(e) or "got an unexpected keyword argument 'tzinfo'" in str(e):
                logger.warning(
                    f"Installed 'schedule' library version might not support timezones. Scheduling in local time for {self.run_time}."
                )
                schedule.every().day.at(self.run_time).do(self.job_func)
            else:
                logger.error(f"TypeError scheduling job at '{self.run_time}': {e}", exc_info=True)
                logger.error("Scheduler cannot start. Exiting.")
                return
        except Exception as e:
            logger.error(f"Failed to schedule job at '{self.run_time}'. Error: {e}", exc_info=True)
            logger.error("Scheduler cannot start. Exiting.")
            return

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
                    # Use schedule.get_jobs() to get timezone info if needed for comparison
                    # Or rely on schedule library internal comparison
                    now = datetime.now()  # Use local time for comparison logic for simplicity
                    # More robust: Use timezone-aware now if next_run is aware
                    # if next_run_time.tzinfo:
                    #    now = datetime.now(next_run_time.tzinfo)

                    # Calculate time until next run in seconds
                    wait_seconds = (next_run_time - now).total_seconds()

                    if wait_seconds > 0:
                        # Sleep for half the duration until the next job,
                        # but at least 1 second and at most the default 60 seconds.
                        calculated_sleep = max(1, wait_seconds / 2)
                        sleep_duration = min(calculated_sleep, 60)
                        logger.debug(f"Next job at {next_run_time}. Sleeping for {sleep_duration:.1f}s.")
                    else:
                        # Job is due or overdue, check more frequently
                        sleep_duration = 1
                        logger.debug("Next job is due or overdue. Sleeping for 1s.")
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
