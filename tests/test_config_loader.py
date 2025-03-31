import pytest
import yaml
import os
from src.config_loader import load_config

# Helper function to create temporary config files
@pytest.fixture
def temp_config_file(tmp_path):
    def _create_config(content, filename="config.yaml"):
        config_path = tmp_path / filename
        config_path.write_text(yaml.dump(content), encoding='utf-8')
        return str(config_path)
    return _create_config

def test_load_valid_config(temp_config_file):
    """Test loading a structurally valid YAML configuration file."""
    valid_content = {
        'categories': ['cs.AI'],
        'keywords': ['test'],
        'max_total_results': 100,
        'run_time_daily': '10:00',
        'output_file': 'out.txt'
    }
    config_path = temp_config_file(valid_content)
    config = load_config(config_path)
    assert config is not None
    assert config == valid_content

def test_load_missing_file():
    """Test loading a non-existent configuration file."""
    config = load_config("non_existent_config.yaml")
    assert config is None

def test_load_invalid_yaml(temp_config_file, tmp_path):
    """Test loading a file with invalid YAML syntax."""
    invalid_yaml_content = "categories: [cs.AI\nkeywords: test"
    config_path = tmp_path / "invalid.yaml"
    config_path.write_text(invalid_yaml_content)
    config = load_config(str(config_path))
    assert config is None

def test_load_not_a_dictionary(temp_config_file):
    """Test loading a YAML file whose content is not a dictionary."""
    not_a_dict_content = ["item1", "item2"]
    config_path = temp_config_file(not_a_dict_content)
    config = load_config(config_path)
    assert config is None

def test_load_empty_file(temp_config_file, tmp_path):
    """Test loading an empty YAML file."""
    config_path = tmp_path / "empty.yaml"
    config_path.touch()
    config = load_config(str(config_path))
    # PyYAML loads empty file as None, which our loader should handle
    assert config is None
