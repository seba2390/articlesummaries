"""Loads application configuration from a YAML file.

Provides a function to safely load and perform basic validation
on the configuration file (typically `config.yaml`).
"""

import logging
import os  # Import os for path checking
from typing import Any, Dict, List, Optional

import yaml  # Library for parsing YAML files

# Logger for this module
logger = logging.getLogger(__name__)

# Default directories and filenames
CONFIGS_DIR = "configs"
MAIN_CONFIG_FILENAME = "main_config.yaml"
EMAIL_CONFIG_FILENAME = "email_config.yaml"
PAPER_SOURCES_CONFIG_SUBDIR = "paper_sources_configs"
LLM_CONFIG_SUBDIR = "llm_configs"


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


def load_config(
    main_config_path: str = MAIN_CONFIG_FILENAME,
    configs_dir: str = CONFIGS_DIR,
    email_config_filename: str = EMAIL_CONFIG_FILENAME,
    paper_sources_subdir: str = PAPER_SOURCES_CONFIG_SUBDIR,
    llm_config_subdir: str = LLM_CONFIG_SUBDIR,
) -> Optional[Dict[str, Any]]:
    """Loads the main configuration and merges in source-specific, LLM, and notification configurations.

    1. Loads the main configuration file (`main_config.yaml` by default).
    2. Identifies active sources from the main config.
    3. Loads the corresponding `<source_name>_config.yaml` files from `configs/paper_sources_configs/`.
    4. Identifies the LLM provider (if `relevance_checking_method` is `llm`).
    5. Loads the corresponding `<provider>_llm_config.yaml` from `configs/llm_configs/`.
    6. Loads the email configuration (`email_config.yaml` by default) from `configs/`.
    7. Merges the source configurations under `main_config['paper_source']`.
    8. Merges the LLM provider configuration into `main_config['relevance_checker']['llm']`.
    9. Merges the email configuration under `main_config['notifications']`.

    Args:
        main_config_path: Path to the main configuration file.
        configs_dir: Path to the base directory containing subdirectories for configs.
        email_config_filename: Filename for the email configuration within `configs_dir`.
        paper_sources_subdir: Subdirectory within `configs_dir` for paper source configs.
        llm_config_subdir: Subdirectory within `configs_dir` for LLM configs.

    Returns:
        A dictionary containing the merged configuration if loading is successful,
        otherwise None.
    """
    # 1. Load main configuration
    main_config = _load_single_config(main_config_path)
    if main_config is None:
        logger.critical(f"Failed to load main configuration from '{main_config_path}'. Cannot proceed.")
        return None

    # Ensure required top-level keys exist, even if empty from main load
    main_config.setdefault("paper_source", {})
    main_config.setdefault("notifications", {})  # Ensure notifications key exists
    main_config.setdefault("relevance_checker", {}).setdefault("llm", {})  # Ensure llm key exists for merging

    # 2. Identify active sources
    active_sources: List[str] = main_config.get("active_sources", [])
    if not isinstance(active_sources, list):
        logger.error(f"'active_sources' in '{main_config_path}' is not a list. Cannot load source configs.")
        # Proceed without source configs, might be intended? Or return None? Let's log and proceed for now.
        active_sources = []
    else:
        logger.info(f"Identified active sources for config loading: {active_sources}")

    # 3. Load source-specific configurations from the subdirectory
    source_configs_path = os.path.join(configs_dir, paper_sources_subdir)
    for source_name in active_sources:
        source_config_filename = f"{source_name}_config.yaml"
        source_config_path = os.path.join(source_configs_path, source_config_filename)  # Use subdir path
        source_config = _load_single_config(source_config_path)

        if source_config is None:
            logger.error(
                f"Failed to load configuration for source '{source_name}' from '{source_config_path}'. Skipping this source."
            )
            # Optionally, remove source from active_sources? For now, just skip loading its config.
            continue
        elif not isinstance(source_config.get(source_name), dict):
            logger.error(
                f"Expected key '{source_name}' with dictionary value in '{source_config_path}', but found {type(source_config.get(source_name)).__name__}. Skipping merge for this source."
            )
            continue

        # 5. Merge source config into main config under 'paper_source'
        # Expecting structure: { 'source_name': { ... settings ...} } in the source file
        if source_name in source_config:
            # Only merge if the top-level key matches the source name
            main_config["paper_source"][source_name] = source_config[source_name]
            logger.debug(f"Merged config for source: {source_name}")
        else:
            logger.warning(
                f"Source config file '{source_config_path}' loaded, but did not contain expected top-level key '{source_name}'."
            )

    # 4. Load LLM provider configuration (if applicable)
    if main_config.get("relevance_checking_method") == "llm":
        llm_provider = main_config.get("relevance_checker", {}).get("llm", {}).get("provider")
        if llm_provider:
            llm_config_filename = f"{llm_provider}_llm_config.yaml"
            llm_configs_path = os.path.join(configs_dir, llm_config_subdir)
            llm_config_filepath = os.path.join(llm_configs_path, llm_config_filename)
            provider_config = _load_single_config(llm_config_filepath)

            if provider_config is None:
                logger.error(
                    f"Failed to load LLM config for provider '{llm_provider}' from '{llm_config_filepath}'. LLM checking might fail."
                )
            elif llm_provider not in provider_config:
                logger.error(
                    f"LLM config file '{llm_config_filepath}' is missing the top-level '{llm_provider}' key. Cannot merge settings."
                )
            elif not isinstance(provider_config[llm_provider], dict):
                logger.error(
                    f"'{llm_provider}' key in '{llm_config_filepath}' does not contain a dictionary. Cannot merge settings."
                )
            else:
                # 8. Merge LLM provider config into main config
                # Ensure the llm key exists before trying to update
                main_config.setdefault("relevance_checker", {}).setdefault("llm", {}).update(provider_config)
                logger.info(
                    f"Successfully merged LLM configuration for provider '{llm_provider}' from '{llm_config_filepath}'."
                )
        else:
            logger.warning("Relevance checking method is 'llm', but no provider specified in main_config.yaml.")

    # 5. Load email configuration (path remains relative to configs_dir)
    email_config_path = os.path.join(configs_dir, email_config_filename)
    email_config = _load_single_config(email_config_path)

    if email_config is None:
        logger.error(f"Failed to load email configuration from '{email_config_path}'. Email notifications might fail.")
        # Proceed without email config? Or make it critical? For now, log and proceed.
    elif "notifications" not in email_config:
        logger.error(
            f"Email config file '{email_config_path}' is missing the top-level 'notifications' key. Cannot merge email settings."
        )
    elif not isinstance(email_config["notifications"], dict):
        logger.error(
            f"'notifications' key in '{email_config_path}' does not contain a dictionary. Cannot merge email settings."
        )
    else:
        # 9. Merge email config into main config under 'notifications'
        # Merge carefully: update existing 'notifications' dict without overwriting other potential keys
        main_config["notifications"].update(email_config["notifications"])
        logger.info(f"Successfully merged email configuration from '{email_config_path}'.")

    # Final combined configuration
    return main_config
