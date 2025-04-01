import pytest
from unittest.mock import patch, MagicMock, call, PropertyMock
import time
from datetime import datetime, timedelta
import logging # Import logging

# Assume schedule library is available (installed via requirements)
import schedule

from src.scheduler import Scheduler

@pytest.fixture
def mock_config():
    """Provides a basic mock config dictionary focused on scheduler settings.

    Sets a specific run time ('10:30') for predictable assertions.
    Does not include timezone by default.
    """
    return {
        'schedule': {
            'run_time': '10:30'
            # 'timezone': 'Europe/London' # Example for timezone tests
        }
        # Include other minimal config sections if Scheduler init requires them
    }

@pytest.fixture
def mock_job_func():
    """Provides a simple MagicMock to represent the scheduled job function.

    Allows tracking if the job function was called.
    """
    return MagicMock(name="mock_job_func")

# --- Test Cases for Scheduler Class ---

# Patch dependencies used within the Scheduler.run method
@patch('src.scheduler.schedule.every') # Mock the entry point for schedule setup
@patch('src.scheduler.schedule.run_pending') # Mock the function that runs jobs
@patch('src.scheduler.schedule.next_run', new_callable=PropertyMock) # Mock the property accessing next run time
@patch('src.scheduler.time.sleep') # Mock sleep to prevent delays and control loop exit
@patch('src.scheduler.logger') # Mock the logger within the scheduler module
def test_scheduler_run_success_flow(
    mock_logger, mock_sleep, mock_next_run_prop, mock_run_pending, mock_every, mock_config, mock_job_func
):
    """Tests the main success path of the Scheduler.run() method.

    Verifies that:
    1. The schedule is configured correctly using `schedule.every().day.at().do()`.
    2. The initial job function is executed once upon startup.
    3. The main loop starts, calls `run_pending`, calculates sleep, and calls `time.sleep`.
    4. The loop exits gracefully on KeyboardInterrupt.
    """

    # Arrange: Configure the mocks
    # --- Mocking the fluent interface: schedule.every().day.at().do() ---
    mock_daily = MagicMock()
    mock_at = MagicMock()
    # `schedule.every()` returns a mock, whose `day` attribute is `mock_daily`
    mock_every.return_value.day = mock_daily
    # `mock_daily.at()` returns `mock_at`
    mock_daily.at.return_value = mock_at
    # `mock_at.do()` returns None (or can be mocked further if needed)

    # --- Mocking the main loop control ---
    # Make `time.sleep` raise KeyboardInterrupt to stop the loop after the first iteration
    mock_sleep.side_effect = KeyboardInterrupt
    # Simulate `schedule.next_run` returning a datetime object (needed for sleep calculation)
    mock_next_run_prop.return_value = datetime.now() + timedelta(minutes=10)

    # Arrange: Instantiate the scheduler
    scheduler = Scheduler(mock_config, mock_job_func)

    # Act: Run the scheduler (which should perform setup, initial run, and one loop iteration)
    scheduler.run()

    # Assert: Verify interactions
    # 1. Schedule configuration:
    mock_every.assert_called_once_with() # schedule.every() called
    mock_daily.at.assert_called_once_with('10:30', None) # .day.at('10:30', None) called (no timezone in mock_config)
    mock_at.do.assert_called_once_with(mock_job_func) # .do(mock_job_func) called

    # 2. Initial job execution:
    mock_job_func.assert_called_once() # The job function itself was called once initially

    # 3. Main loop execution (first iteration):
    mock_run_pending.assert_called_once() # schedule.run_pending() was called
    mock_sleep.assert_called_once() # time.sleep() was called before interrupt
    # Optional: Assert the calculated sleep duration if needed
    # mock_sleep.assert_called_with(pytest.approx(expected_sleep_duration, abs=1))

    # 4. Logging (Optional but good): Check for key log messages
    mock_logger.info.assert_any_call("Scheduler initialized. Daily run time: 10:30 (local time)")
    mock_logger.info("Performing initial job run on startup...")
    mock_logger.info("Initial job run completed.")
    mock_logger.info("Scheduler started. Waiting for pending jobs... (Press Ctrl+C to stop)")
    mock_logger.info("KeyboardInterrupt received. Stopping scheduler...")
    mock_logger.info("Scheduler stopped.")


# Patch dependencies again for this test case
@patch('src.scheduler.schedule.every')
@patch('src.scheduler.schedule.run_pending')
@patch('src.scheduler.schedule.next_run', new_callable=PropertyMock)
@patch('src.scheduler.time.sleep')
@patch('src.scheduler.logger')
def test_scheduler_run_initial_job_error(
    mock_logger, mock_sleep, mock_next_run_prop, mock_run_pending, mock_every, mock_config, mock_job_func
):
    """Tests that an error during the initial job run is logged but the scheduler loop still starts.

    Verifies that:
    1. The initial job function is called and raises an error.
    2. The error is logged.
    3. The scheduler loop still attempts to run (calls `run_pending` and `sleep`).
    """
    # Arrange: Configure mocks
    # --- Mock the schedule setup part (needed for scheduler init) ---
    mock_daily = MagicMock()
    mock_at = MagicMock()
    mock_every.return_value.day = mock_daily
    mock_daily.at.return_value = mock_at

    # --- Mock the job function to raise an error ---
    mock_job_func.side_effect = Exception("Initial job failed!")

    # --- Mock the main loop control ---
    mock_sleep.side_effect = KeyboardInterrupt # Stop loop immediately after first iteration
    mock_next_run_prop.return_value = datetime.now() + timedelta(minutes=10)

    # Arrange: Instantiate the scheduler
    scheduler = Scheduler(mock_config, mock_job_func)

    # Act: Run the scheduler
    scheduler.run()

    # Assert: Verify interactions
    # 1. Schedule configuration happened:
    mock_daily.at.assert_called_once_with('10:30', None)
    mock_at.do.assert_called_once_with(mock_job_func)

    # 2. Initial job execution was attempted:
    mock_job_func.assert_called_once()

    # 3. Error during initial job was logged:
    mock_logger.error.assert_called_once()
    assert "Error during initial job execution: Initial job failed!" in mock_logger.error.call_args[0][0]
    mock_logger.warning.assert_called_with("Scheduler will continue waiting for the next scheduled run despite initial job error.")

    # 4. Main loop still started:
    mock_run_pending.assert_called_once()
    mock_sleep.assert_called_once()

# TODO: Consider adding tests for:
# - Timezone handling (requires modifying mock_config and assertions for `at()`)
# - Errors during the `schedule.every().day.at().do()` setup in __init__
# - Errors occurring *within* the `while True` loop (e.g., `run_pending` fails)
# - Different `sleep_duration` calculations based on `schedule.next_run`
