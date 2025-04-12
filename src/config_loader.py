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

# Default directories and filenames
CONFIGS_DIR = "configs"
MAIN_CONFIG_FILENAME = "main_config.yaml"
EMAIL_CONFIG_FILENAME = "email_config.yaml"
PAPER_SOURCES_CONFIG_SUBDIR = "paper_sources_configs"
LLM_CONFIG_SUBDIR = "llm_configs"

# Define default paths relative to the project root
DEFAULT_MAIN_CONFIG = "main_config.yaml"
DEFAULT_CONFIGS_DIR = "configs"
DEFAULT_SOURCES_SUBDIR = "paper_sources_configs"
DEFAULT_EMAIL_CONFIG = "email_config.yaml"
DEFAULT_LLM_SUBDIR = "llm_configs"
DEFAULT_ST_SUBDIR = "local_sentence_transformer_configs"  # New subdir
DEFAULT_ST_CONFIG = "sentence_transformer_config.yaml"  # New default config file


def _load_single_config(file_path: str) -> Optional[Dict[str, Any]]:
    """Loads a single YAML file with basic validation.

    Attempts to read the specified YAML file, parse its content, and perform
    minimal validation (checks if it exists, is readable, not empty, and contains a dictionary).

    Args:
        file_path: The path to the YAML configuration file.

    Returns:
        A dictionary containing the configuration if loading and validation
        are successful, otherwise None.
    """
    # Check if the file exists before attempting to open
    if not os.path.exists(file_path):
        logger.error(f"Configuration file error: '{file_path}' not found.")
        return None

    try:
        # Open and read the YAML file, ensuring UTF-8 encoding
        with open(file_path, "r", encoding="utf-8") as f:
            # Use yaml.safe_load to prevent arbitrary code execution from malicious YAML
            config = yaml.safe_load(f)
        logger.info(f"Configuration section loaded successfully from '{file_path}'")

        # Validation 1: Handle empty or effectively empty files (PyYAML loads these as None)
        if config is None:
            logger.warning(f"Configuration file warning: '{file_path}' is empty or contains only comments/whitespace.")
            return {}  # Return empty dict instead of None for merging

        # Validation 2: Ensure the top-level structure is a dictionary (key-value pairs)
        if not isinstance(config, dict):
            logger.error(
                f"Configuration file error: Content of '{file_path}' is not a valid dictionary. "
                f"Loaded type: {type(config).__name__}"
            )
            return None  # Error case, return None

        return config

    except yaml.YAMLError as e:
        # Error during YAML parsing (syntax errors, etc.)
        logger.error(f"Configuration file error: Error parsing YAML syntax in '{file_path}'. Details: {e}")
        return None
    except IOError as e:
        # Error during file I/O (e.g., permissions, read errors)
        logger.error(f"Configuration file error: Could not read file '{file_path}'. Details: {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during loading/parsing
        logger.error(
            f"An unexpected error occurred while loading/parsing configuration from '{file_path}': {e}",
            exc_info=True,  # Include traceback information for debugging
        )
        return None


def deep_update(source: Dict, overrides: Dict) -> Dict:
    """Deeply update dictionary source with overrides."""
    for key, value in overrides.items():
        if isinstance(value, dict) and key in source and isinstance(source[key], dict):
            source[key] = deep_update(source[key], value)
        else:
            source[key] = value
    return source


def load_config(main_config_path: str = DEFAULT_MAIN_CONFIG) -> Optional[Dict[str, Any]]:
    """Loads the main config and merges configs from subdirectories."""
    if not os.path.exists(main_config_path):
        logger.error(f"Main configuration file not found: {main_config_path}")
        return None

    try:
        with open(main_config_path, "r") as f:
            config: Dict[str, Any] = yaml.safe_load(f)
        logger.info(f"Configuration section loaded successfully from '{main_config_path}'")
    except Exception as e:
        logger.error(f"Failed to load or parse main configuration from {main_config_path}: {e}", exc_info=True)
        return None

    if config is None:
        logger.error(f"Main configuration file {main_config_path} is empty or invalid.")
        return None

    configs_dir = os.path.dirname(main_config_path) or "."  # Get dir of main config or use current
    configs_base_dir = os.path.join(configs_dir, DEFAULT_CONFIGS_DIR)

    # 1. Load Paper Source Configs
    active_sources = config.get("active_sources", [])
    if active_sources:
        logger.info(f"Identified active sources for config loading: {active_sources}")
        sources_config_dir = os.path.join(configs_base_dir, DEFAULT_SOURCES_SUBDIR)
        config["paper_source"] = config.get("paper_source", {})  # Ensure key exists

        for source_name in active_sources:
            source_config_file = f"{source_name}_config.yaml"
            source_config_path = os.path.join(sources_config_dir, source_config_file)
            if os.path.exists(source_config_path):
                try:
                    with open(source_config_path, "r") as f:
                        source_specific_config = yaml.safe_load(f)
                    if source_specific_config and isinstance(source_specific_config, dict):
                        # Merge this source's config under config["paper_source"][source_name]
                        # Ensure the source_name key exists
                        config["paper_source"][source_name] = config["paper_source"].get(source_name, {})
                        config["paper_source"][source_name] = deep_update(
                            config["paper_source"][source_name],
                            source_specific_config.get(source_name, {}),  # Expect settings under source_name key
                        )
                        logger.info(f"Configuration section loaded successfully from '{source_config_path}'")
                    else:
                        logger.warning(f"Source config file {source_config_path} is empty or invalid.")
                except Exception as e:
                    logger.error(f"Failed to load source config {source_config_path}: {e}", exc_info=True)
            else:
                logger.warning(
                    f"Configuration file for active source '{source_name}' not found at {source_config_path}"
                )

    # 2. Load Email Config
    email_config_path = os.path.join(configs_base_dir, DEFAULT_EMAIL_CONFIG)
    if os.path.exists(email_config_path):
        try:
            with open(email_config_path, "r") as f:
                email_config = yaml.safe_load(f)
            if email_config and isinstance(email_config, dict):
                # Merge the 'notifications' section from email config into main config
                main_notifications = config.get("notifications", {})
                if not isinstance(main_notifications, dict):
                    logger.warning("'notifications' in main config is not a dictionary, overriding with email config.")
                    main_notifications = {}
                config["notifications"] = deep_update(main_notifications, email_config.get("notifications", {}))
                logger.info(f"Successfully merged email configuration from '{email_config_path}'.")
            else:
                logger.warning(f"Email config file {email_config_path} is empty or invalid.")
        except Exception as e:
            logger.error(f"Failed to load or merge email config {email_config_path}: {e}", exc_info=True)
    else:
        logger.warning(f"Email configuration file not found at {email_config_path}")

    # 3. Load LLM Config (if applicable)
    checking_method = config.get("relevance_checking_method", "keyword").lower()
    if checking_method == "llm":
        llm_provider = config.get("relevance_checker", {}).get("llm", {}).get("provider")
        if llm_provider:
            llm_config_file = f"{llm_provider}_llm_config.yaml"
            llm_config_path = os.path.join(configs_base_dir, DEFAULT_LLM_SUBDIR, llm_config_file)
            if os.path.exists(llm_config_path):
                try:
                    with open(llm_config_path, "r") as f:
                        llm_specific_config = yaml.safe_load(f)
                    if llm_specific_config and isinstance(llm_specific_config, dict):
                        # Ensure structure exists before merging
                        config["relevance_checker"] = config.get("relevance_checker", {})
                        config["relevance_checker"]["llm"] = config["relevance_checker"].get("llm", {})
                        config["relevance_checker"]["llm"][llm_provider] = config["relevance_checker"]["llm"].get(
                            llm_provider, {}
                        )
                        # Merge provider-specific settings
                        config["relevance_checker"]["llm"][llm_provider] = deep_update(
                            config["relevance_checker"]["llm"][llm_provider], llm_specific_config.get(llm_provider, {})
                        )
                        logger.info(f"Successfully merged LLM provider config from '{llm_config_path}'.")
                    else:
                        logger.warning(f"LLM config file {llm_config_path} is empty or invalid.")
                except Exception as e:
                    logger.error(f"Failed to load LLM config {llm_config_path}: {e}", exc_info=True)
            else:
                logger.warning(f"LLM configuration file for provider '{llm_provider}' not found at {llm_config_path}")
        else:
            logger.warning("LLM checking method selected, but no provider specified in main_config.")

    # 4. Load Sentence Transformer Config (if applicable)
    elif checking_method == "local_sentence_transformer":
        st_config_path = os.path.join(configs_base_dir, DEFAULT_ST_SUBDIR, DEFAULT_ST_CONFIG)
        if os.path.exists(st_config_path):
            try:
                with open(st_config_path, "r") as f:
                    st_config = yaml.safe_load(f)
                if st_config and isinstance(st_config, dict):
                    # Ensure structure exists before merging
                    config["relevance_checker"] = config.get("relevance_checker", {})
                    # Merge the specific filter settings
                    config["relevance_checker"]["sentence_transformer_filter"] = deep_update(
                        config["relevance_checker"].get("sentence_transformer_filter", {}),
                        st_config.get("sentence_transformer_filter", {}),
                    )
                    logger.info(f"Successfully merged Sentence Transformer config from '{st_config_path}'.")
                else:
                    logger.warning(f"Sentence Transformer config file {st_config_path} is empty or invalid.")
            except Exception as e:
                logger.error(f"Failed to load Sentence Transformer config {st_config_path}: {e}", exc_info=True)
        else:
            logger.warning(f"Sentence Transformer config file not found at {st_config_path}")

    return config
