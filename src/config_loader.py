"""Loads application configuration from a YAML file.

Provides a function to safely load and perform basic validation
on the configuration file (typically `config.yaml`).
"""

import logging
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Optional[Dict[str, Any]]:
    """Loads and performs basic validation on a YAML configuration file.

    Args:
        config_path: The path to the YAML configuration file.
                     Defaults to 'config.yaml' in the current directory.

    Returns:
        A dictionary containing the configuration if loading and validation
        are successful, otherwise None.
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:  # Specify encoding
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from '{config_path}'")

        # Handle empty file case (PyYAML loads this as None)
        if config is None:
            logger.error(f"Error: Configuration file '{config_path}' is empty or invalid.")
            return None

        # Basic validation: Ensure it's a dictionary
        if not isinstance(config, dict):
            logger.error(f"Error: Configuration file '{config_path}' content is not structured as a dictionary.")
            return None

        return config

    except FileNotFoundError:
        logger.error(f"Configuration file error: '{config_path}' not found.")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Configuration file error: Error parsing YAML in '{config_path}'. Details: {e}")
        return None
    except IOError as e:
        # Catch potential issues reading the file (e.g., permissions)
        logger.error(f"Configuration file error: Could not read file '{config_path}'. Details: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during loading
        logger.error(
            f"An unexpected error occurred while loading configuration from '{config_path}': {e}", exc_info=True
        )
        return None
