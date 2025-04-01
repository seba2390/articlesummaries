"""Loads application configuration from a YAML file.

Provides a function to safely load and perform basic validation
on the configuration file (typically `config.yaml`).
"""

import logging
import os  # Import os for path checking
from typing import Any, Dict, Optional

import yaml  # Library for parsing YAML files

# Logger for this module
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Optional[Dict[str, Any]]:
    """Loads and performs basic validation on a YAML configuration file.

    Attempts to read the specified YAML file, parse its content, and perform
    minimal validation (checks if it exists, is readable, not empty, and contains a dictionary).

    Args:
        config_path: The path to the YAML configuration file.
                     Defaults to 'config.yaml' in the current working directory.

    Returns:
        A dictionary containing the configuration if loading and validation
        are successful, otherwise None.
    """
    # Check if the file exists before attempting to open
    if not os.path.exists(config_path):
        logger.error(f"Configuration file error: '{config_path}' not found.")
        return None

    try:
        # Open and read the YAML file, ensuring UTF-8 encoding
        with open(config_path, "r", encoding="utf-8") as f:
            # Use yaml.safe_load to prevent arbitrary code execution from malicious YAML
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded successfully from '{config_path}'")

        # Validation 1: Handle empty or effectively empty files (PyYAML loads these as None)
        if config is None:
            logger.error(f"Configuration file error: '{config_path}' is empty or contains only comments/whitespace.")
            return None

        # Validation 2: Ensure the top-level structure is a dictionary (key-value pairs)
        if not isinstance(config, dict):
            logger.error(
                f"Configuration file error: Content of '{config_path}' is not a valid dictionary (key-value structure). "
                f"Loaded type: {type(config).__name__}"
            )
            return None

        # Basic validation passed
        return config

    except yaml.YAMLError as e:
        # Error during YAML parsing (syntax errors, etc.)
        logger.error(f"Configuration file error: Error parsing YAML syntax in '{config_path}'. Details: {e}")
        return None
    except IOError as e:
        # Error during file I/O (e.g., permissions, read errors)
        logger.error(f"Configuration file error: Could not read file '{config_path}'. Details: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during loading/parsing
        logger.error(
            f"An unexpected error occurred while loading/parsing configuration from '{config_path}': {e}",
            exc_info=True,  # Include traceback information for debugging
        )
        return None
