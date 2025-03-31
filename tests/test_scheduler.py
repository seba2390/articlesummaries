import pytest
from unittest.mock import patch, MagicMock, call, PropertyMock
import time
from datetime import datetime, timedelta

# Assume schedule library is available (installed via requirements)
import schedule

from src.scheduler import Scheduler

@pytest.fixture
def mock_config():
    return {'run_time_daily': '10:30'}

@pytest.fixture
def mock_job_func():
    # Simple mock function to track calls
    return MagicMock()

# --- Test Cases ---

# Patch the schedule module methods used by Scheduler.run
@patch('src.scheduler.schedule.every')
@patch('src.scheduler.schedule.run_pending')
# Patch next_run as a property directly
@patch('src.scheduler.schedule.next_run', new_callable=PropertyMock)
@patch('src.scheduler.time.sleep') # Patch time.sleep to avoid actual sleeping
def test_scheduler_run_schedule_and_initial_job(
    mock_sleep, mock_next_run_prop, mock_run_pending, mock_every, mock_config, mock_job_func
):
    """Test that the scheduler configures schedule, runs job initially, and enters loop."""

    # Setup mocks
    # Mock the fluent interface of schedule: every().day.at().do()
    mock_daily = MagicMock()
    mock_at = MagicMock()
    mock_every.return_value.day = mock_daily
    mock_daily.at.return_value = mock_at

    # Simulate the loop running only once then exiting (e.g., via KeyboardInterrupt)
    mock_sleep.side_effect = KeyboardInterrupt # Stop loop after first sleep
    # Simulate next_run property returning a future time
    mock_next_run_prop.return_value = datetime.now() + timedelta(minutes=10)

    scheduler = Scheduler(mock_config, mock_job_func)

    # --- Run the scheduler ---
    # We expect it to run the initial job, then enter the loop once and be interrupted
    scheduler.run()

    # --- Assertions ---
    # 1. Check schedule configuration
    mock_every.assert_called_once_with()
    mock_daily.at.assert_called_once_with('10:30')
    mock_at.do.assert_called_once_with(mock_job_func)

    # 2. Check initial job run
    mock_job_func.assert_called_once()

    # 3. Check loop execution (called once before interrupt)
    mock_run_pending.assert_called_once()
    mock_sleep.assert_called_once() # Called once before KeyboardInterrupt

# Patch schedule and time again
@patch('src.scheduler.schedule.every')
@patch('src.scheduler.schedule.run_pending')
# Patch next_run as a property
@patch('src.scheduler.schedule.next_run', new_callable=PropertyMock)
@patch('src.scheduler.time.sleep')
@patch('src.scheduler.logger') # Mock the logger inside scheduler module
def test_scheduler_run_initial_job_error(
    mock_logger, mock_sleep, mock_next_run_prop, mock_run_pending, mock_every, mock_config, mock_job_func
):
    """Test that an error during the initial job run is logged but scheduler continues."""

    # Setup mocks
    mock_job_func.side_effect = Exception("Initial job failed!")
    mock_sleep.side_effect = KeyboardInterrupt # Stop loop immediately after potential error handling
    mock_next_run_prop.return_value = datetime.now() + timedelta(minutes=10)

    scheduler = Scheduler(mock_config, mock_job_func)
    scheduler.run()

    # Assertions
    mock_job_func.assert_called_once() # Job was attempted
    # Check that the error was logged
    mock_logger.error.assert_called_once()
    assert "Error during initial job execution: Initial job failed!" in mock_logger.error.call_args[0][0]
    # Check that it still tried to enter the loop (run_pending and sleep were called)
    mock_run_pending.assert_called_once()
    mock_sleep.assert_called_once()

# Add more tests for loop errors, different sleep calculations etc. if needed
