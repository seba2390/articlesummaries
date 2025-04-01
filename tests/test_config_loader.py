import pytest
import yaml
import os
from pathlib import Path # For type hinting tmp_path
from typing import Any, Dict, Callable, List # For type hinting

from src.config_loader import load_config

# --- Fixture for Temporary Config Files ---

@pytest.fixture
def temp_config_file(tmp_path: Path) -> Callable[[Dict[str, Any], str], str]:
    """Fixture to create temporary YAML config files for testing.

    Args:
        tmp_path: pytest fixture providing a temporary directory path.

    Returns:
        A function that takes YAML content (dict) and an optional filename,
        writes it to the temporary directory, and returns the file path as a string.
    """
    def _create_config(content: Dict[str, Any], filename: str = "config.yaml") -> str:
        """Creates a YAML file in the tmp_path directory."""
        config_path: Path = tmp_path / filename
        config_path.write_text(yaml.dump(content), encoding='utf-8')
        return str(config_path)
    return _create_config

# --- Test Cases for load_config ---

def test_load_valid_config(temp_config_file: Callable[[Dict[str, Any], str], str]):
    """Tests loading a structurally valid YAML configuration file."""
    # Arrange: Define valid YAML content
    valid_content: Dict[str, Any] = {
        'paper_source': {'arxiv': {'categories': ['cs.AI']}},
        'relevance_checker': {'type': 'keyword', 'keywords': ['test']},
        'scheduler': {'run_time_daily': '10:00'},
        'output': {'file': {'file': 'out.txt'}}
        # Using a nested structure closer to the real config
    }
    # Arrange: Create the temporary config file
    config_path: str = temp_config_file(valid_content)

    # Act: Load the configuration
    config = load_config(config_path)

    # Assert: Check that the loaded config matches the original content
    assert config is not None
    assert config == valid_content

def test_load_missing_file():
    """Tests that loading a non-existent configuration file returns None and logs an error (implicitly)."""
    # Arrange: Define a path that does not exist
    non_existent_path = "non_existent_config.yaml"
    # Ensure the file doesn't exist (though unlikely in test environment)
    if os.path.exists(non_existent_path):
        os.remove(non_existent_path)

    # Act: Attempt to load the non-existent file
    config = load_config(non_existent_path)

    # Assert: The function should return None
    assert config is None

def test_load_invalid_yaml(tmp_path: Path):
    """Tests that loading a file with invalid YAML syntax returns None and logs an error (implicitly)."""
    # Arrange: Create content with incorrect YAML syntax (missing colon)
    invalid_yaml_content = "categories: [cs.AI\nkeywords test" # Missing colon after keywords
    config_path: Path = tmp_path / "invalid.yaml"
    config_path.write_text(invalid_yaml_content)

    # Act: Attempt to load the invalid YAML file
    config = load_config(str(config_path))

    # Assert: The function should return None
    assert config is None

def test_load_not_a_dictionary(temp_config_file: Callable[[Dict[str, Any], str], str]):
    """Tests loading a YAML file where the top-level content is not a dictionary.

    The `load_config` expects a dictionary structure.
    """
    # Arrange: Create content that is a list, not a dictionary
    not_a_dict_content: List[str] = ["item1", "item2"]
    config_path: str = temp_config_file(not_a_dict_content, "list_config.yaml")

    # Act: Attempt to load the file
    config = load_config(config_path)

    # Assert: The function should return None as the root is not a dict
    assert config is None

def test_load_empty_file(tmp_path: Path):
    """Tests loading an empty file.

    PyYAML parses an empty file as None, which `load_config` should handle gracefully.
    """
    # Arrange: Create an empty file
    config_path: Path = tmp_path / "empty.yaml"
    config_path.touch()

    # Act: Load the empty file
    config = load_config(str(config_path))

    # Assert: The function should return None
    assert config is None
