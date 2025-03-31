import logging
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Optional[Dict[str, Any]]:
    """Loads configuration from a YAML file."""
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from {config_path}")
        # Basic validation (can be expanded)
        if not isinstance(config, dict):
            logger.error(f"Error: Configuration file '{config_path}' content is not a dictionary.")
            return None
        return config
    except FileNotFoundError:
        logger.error(f"Error: Configuration file '{config_path}' not found.")
        return None
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config: {e}")
        return None
