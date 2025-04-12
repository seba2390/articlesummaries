import pytest
import yaml
import os
from pathlib import Path # For type hinting tmp_path
from typing import Any, Dict, Callable, List, Optional
import shutil # For removing directory
from unittest.mock import patch
import logging

from src.config_loader import (
    load_config,
    # _load_single_config, # Avoid importing private helper for tests
    # Import necessary constants
    DEFAULT_MAIN_CONFIG,
    DEFAULT_CONFIGS_DIR,
    DEFAULT_SOURCES_SUBDIR,
    DEFAULT_EMAIL_CONFIG,
    DEFAULT_LLM_SUBDIR,
    DEFAULT_ST_SUBDIR,
    DEFAULT_ST_CONFIG,
    MAIN_CONFIG_FILENAME,
    CONFIGS_DIR,
    EMAIL_CONFIG_FILENAME,
    PAPER_SOURCES_CONFIG_SUBDIR,
    LLM_CONFIG_SUBDIR
)

# --- Fixtures ---

@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory structure for config files."""
    configs_path = tmp_path / CONFIGS_DIR
    (configs_path / PAPER_SOURCES_CONFIG_SUBDIR).mkdir(parents=True)
    (configs_path / LLM_CONFIG_SUBDIR).mkdir(parents=True)
    yield tmp_path # Yield the root temp path
    # Teardown: remove the directory after test
    # shutil.rmtree(tmp_path, ignore_errors=True)

def _create_yaml_file(dir_path: Path, filename: str, content: Dict[str, Any]) -> str:
    """Helper to create a YAML file in a specific directory."""
    file_path = dir_path / filename
    file_path.write_text(yaml.dump(content), encoding='utf-8')
    return str(file_path)

# Define sample config contents
MAIN_CONFIG_CONTENT = {
    'active_sources': ['arxiv', 'biorxiv'],
    'relevance_checking_method': 'keyword',
    'send_email_summary': True,
    'max_total_results': 100,
    'output': {'file': 'out.md', 'format': 'markdown'},
    'relevance_checker': { # Need this structure for LLM loading test
        'llm': {
            'provider': 'groq'
        }
    },
    'notifications': {},
    'schedule': {'run_time': '10:00'}
}

ARXIV_CONFIG_CONTENT = {
    'arxiv': {
        'categories': ['cs.AI', 'cs.LG'],
        'keywords': ['ai', 'ml'],
        'fetch_window': 7
    }
}

BIORXIV_CONFIG_CONTENT = {
    'biorxiv': {
        'server': 'biorxiv',
        'categories': ['Neuroscience'],
        'keywords': ['brain'],
        'fetch_window': 3
    }
}

EMAIL_CONFIG_CONTENT = {
    'notifications': {
        'email_recipients': ['test@example.com'],
        'email_sender': {'address': 'sender@example.com', 'password': 'pass'},
        'smtp': {'server': 'smtp.example.com', 'port': 587}
    }
}

GROQ_LLM_CONFIG_CONTENT = {
    'groq': {
        'api_key': 'test-key',
        'model': 'llama-test',
        'prompt': 'Test prompt?',
        'batch_size': 3,
        'confidence_threshold': 0.6,
        'batch_delay_seconds': 1
    }
}

# Example content for sentence transformer config file
ST_CONFIG_CONTENT = {
    "sentence_transformer_filter": {
        "model_name": "test-st-model",
        "similarity_threshold": 0.77,
        "target_texts": ["st target text"],
        "device": "cpu"
    }
}

# --- Test Cases ---

def test_load_valid_full_config(temp_config_dir: Path):
    """Tests loading a complete and valid set of configuration files."""
    # Arrange: Create all necessary config files in correct subdirs
    # Use a version of main config that enables LLM checking for this test
    main_llm_content = MAIN_CONFIG_CONTENT.copy()
    main_llm_content['relevance_checking_method'] = 'llm'

    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, main_llm_content)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    _create_yaml_file(sources_subdir, 'biorxiv_config.yaml', BIORXIV_CONFIG_CONTENT)
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT)
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act: Load the configuration using the temp paths
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Check that the loaded config is correctly merged
    assert config is not None
    assert config['active_sources'] == ['arxiv', 'biorxiv']
    assert config['relevance_checking_method'] == 'llm'
    assert config['send_email_summary'] is True
    assert config['max_total_results'] == 100
    assert config['output'] == {'file': 'out.md', 'format': 'markdown'}

    # Assert paper_source merging
    assert 'paper_source' in config
    assert 'arxiv' in config['paper_source']
    assert config['paper_source']['arxiv'] == ARXIV_CONFIG_CONTENT['arxiv']
    assert 'biorxiv' in config['paper_source']
    assert config['paper_source']['biorxiv'] == BIORXIV_CONFIG_CONTENT['biorxiv']

    # Assert notifications merging
    assert 'notifications' in config
    # Check a few key notification settings
    assert config['notifications']['email_recipients'] == ['test@example.com']
    assert config['notifications']['smtp']['server'] == 'smtp.example.com'

    # Assert LLM merging
    assert 'relevance_checker' in config
    assert 'llm' in config['relevance_checker']
    assert 'groq' in config['relevance_checker']['llm'] # Check provider key is merged
    assert config['relevance_checker']['llm']['groq'] == GROQ_LLM_CONFIG_CONTENT['groq']
    assert config['relevance_checker']['llm']['provider'] == 'groq' # Provider from main config

def test_load_missing_main_config(temp_config_dir: Path):
    """Tests that loading fails if the main config file is missing."""
    # Arrange: Only create the configs subdir, not the main file
    configs_root = temp_config_dir / CONFIGS_DIR
    # Don't create main_config.yaml

    # Act: Attempt to load
    config = load_config(
        main_config_path=str(temp_config_dir / MAIN_CONFIG_FILENAME), # Non-existent path
    )

    # Assert: Should return None
    assert config is None

def test_load_missing_source_config(temp_config_dir: Path, caplog):
    """Tests loading when an active source's config file is missing."""
    # Arrange: Create main, email, but only one source config
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, MAIN_CONFIG_CONTENT)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    # Missing biorxiv_config.yaml in sources_subdir
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT) # Create LLM config
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config should load, but biorxiv section should be missing/empty
    assert config is not None
    assert 'arxiv' in config['paper_source']
    assert not config['paper_source'].get('biorxiv') # Check if biorxiv has content
    assert f"Configuration file for active source 'biorxiv' not found" in caplog.text # Check new warning

def test_load_missing_email_config(temp_config_dir: Path, caplog):
    """Tests loading when the email config file is missing."""
    # Arrange: Create main and source configs, but not email
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, MAIN_CONFIG_CONTENT)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    _create_yaml_file(sources_subdir, 'biorxiv_config.yaml', BIORXIV_CONFIG_CONTENT)
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT) # Create LLM config
    # Missing email_config.yaml in configs_root

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config should load, email section should be empty
    assert config is not None
    assert 'notifications' in config # Key should still exist from main_config or default
    assert not config['notifications'] # Should be empty as merge failed
    assert "Email configuration file not found" in caplog.text # Check warning

def test_load_invalid_yaml_in_source_config(temp_config_dir: Path, caplog):
    """Tests loading when a source config file has invalid YAML."""
    # Arrange: Create valid main, but invalid source config
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, MAIN_CONFIG_CONTENT)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    invalid_arxiv_path = sources_subdir / 'arxiv_config.yaml'
    invalid_arxiv_path.write_text("arxiv: [cs.AI\n key: val", encoding='utf-8') # Invalid YAML
    _create_yaml_file(sources_subdir, 'biorxiv_config.yaml', BIORXIV_CONFIG_CONTENT)
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT) # Create LLM config
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config loads, but invalid source is skipped
    assert config is not None
    assert not config['paper_source'].get('arxiv')
    assert 'biorxiv' in config['paper_source']
    assert "Failed to load source config" in caplog.text and "arxiv_config.yaml" in caplog.text # Check new log

def test_load_source_config_wrong_structure(temp_config_dir: Path, caplog):
    """Tests loading when a source config file doesn't have the expected top-level key."""
    # Arrange: Create valid main, but source config has wrong top key
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, MAIN_CONFIG_CONTENT)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    wrong_key_content = {'wrong_name': {'categories': ['cs.AI']}}
    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', wrong_key_content)
    _create_yaml_file(sources_subdir, 'biorxiv_config.yaml', BIORXIV_CONFIG_CONTENT)
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT)
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config loads, but source with wrong key is not merged correctly
    assert config is not None
    assert 'arxiv' in config['paper_source']
    assert not config['paper_source']['arxiv'] # Check it's empty

def test_load_email_config_wrong_structure(temp_config_dir: Path, caplog):
    """Tests loading when the email config file doesn't have the 'notifications' key."""
    # Arrange: Create valid main/sources, but email config has wrong top key
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, MAIN_CONFIG_CONTENT)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    _create_yaml_file(sources_subdir, 'biorxiv_config.yaml', BIORXIV_CONFIG_CONTENT)
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', GROQ_LLM_CONFIG_CONTENT)
    wrong_email_content = {'email_settings': {'recipients': ['a@b.com']}}
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, wrong_email_content)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config loads, notifications section remains empty/unmerged
    assert config is not None
    assert 'notifications' in config
    assert not config['notifications']
    assert "Successfully merged email configuration" in caplog.text # This should still appear as the file was loaded

# --- New tests for LLM config loading ---

def test_load_missing_llm_config(temp_config_dir: Path, caplog):
    """Tests loading when the LLM provider's config file is missing."""
    # Arrange: Main config specifies LLM/groq, but file is missing
    main_llm_content = MAIN_CONFIG_CONTENT.copy()
    main_llm_content['relevance_checking_method'] = 'llm'
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, main_llm_content)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    # llm_subdir exists but groq_llm_config.yaml is missing

    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config loads, but LLM section won't have provider details merged
    assert config is not None
    assert 'relevance_checker' in config
    assert 'llm' in config['relevance_checker']
    assert config['relevance_checker']['llm']['provider'] == 'groq'
    assert not config['relevance_checker']['llm'].get('groq')
    assert "LLM configuration file for provider 'groq' not found" in caplog.text # Check new warning

def test_load_llm_config_wrong_structure(temp_config_dir: Path, caplog):
    """Tests loading when LLM config file has the wrong top-level key."""
    # Arrange: Main config specifies LLM/groq, file exists but wrong key
    main_llm_content = MAIN_CONFIG_CONTENT.copy()
    main_llm_content['relevance_checking_method'] = 'llm'
    main_path = _create_yaml_file(temp_config_dir, MAIN_CONFIG_FILENAME, main_llm_content)
    configs_root = temp_config_dir / CONFIGS_DIR
    sources_subdir = configs_root / PAPER_SOURCES_CONFIG_SUBDIR
    llm_subdir = configs_root / LLM_CONFIG_SUBDIR

    wrong_llm_content = {'openai': {'api_key': 'wrong'}}
    _create_yaml_file(llm_subdir, 'groq_llm_config.yaml', wrong_llm_content)
    _create_yaml_file(sources_subdir, 'arxiv_config.yaml', ARXIV_CONFIG_CONTENT)
    _create_yaml_file(configs_root, EMAIL_CONFIG_FILENAME, EMAIL_CONFIG_CONTENT)

    # Act
    config = load_config(
        main_config_path=str(main_path)
    )

    # Assert: Config loads, but LLM section won't have provider details merged correctly
    assert config is not None
    assert 'groq' in config['relevance_checker']['llm']
    assert not config['relevance_checker']['llm']['groq'] # Check it's empty

# Tests for _load_single_config (internal helper)
# These reuse some logic from the original tests

@pytest.fixture
def temp_file(tmp_path: Path) -> Callable[[Optional[Any], str], str]:
    """Fixture to create a temporary file with specific content."""
    def _create_file(content: Optional[Any], filename: str = "temp.yaml") -> str:
        file_path: Path = tmp_path / filename
        if content is None:
            file_path.touch() # Create empty file
        elif isinstance(content, str):
            file_path.write_text(content, encoding='utf-8') # Write raw string for invalid YAML
        else:
            file_path.write_text(yaml.dump(content), encoding='utf-8') # Dump valid structures
        return str(file_path)
    return _create_file

from src.config_loader import _load_single_config

def test_load_single_valid(temp_file: Callable):
    path = temp_file({'key': 'value'})
    assert _load_single_config(path) == {'key': 'value'}

def test_load_single_empty(temp_file: Callable, caplog):
    path = temp_file(None)
    assert _load_single_config(path) == {} # Should return empty dict
    assert "is empty or contains only comments/whitespace" in caplog.text

def test_load_single_missing(caplog):
    assert _load_single_config("non_existent.yaml") is None
    assert "'non_existent.yaml' not found" in caplog.text

def test_load_single_invalid_yaml(temp_file: Callable, caplog):
    path = temp_file("key: value\n another: [")
    assert _load_single_config(path) is None
    assert "Error parsing YAML syntax" in caplog.text

def test_load_single_not_dict(temp_file: Callable, caplog):
    path = temp_file(['list', 'item'])
    assert _load_single_config(path) is None
    assert "is not a valid dictionary" in caplog.text

def test_load_st_config(temp_config_dir: Path):
    """Tests loading when sentence transformer config is used."""
    # Arrange
    main_st_content = MAIN_CONFIG_CONTENT.copy()
    main_st_content['relevance_checking_method'] = 'local_sentence_transformer'
    main_path = _create_yaml_file(temp_config_dir, DEFAULT_MAIN_CONFIG, main_st_content)
    configs_root = temp_config_dir / DEFAULT_CONFIGS_DIR
    st_subdir = configs_root / DEFAULT_ST_SUBDIR
    st_subdir.mkdir(parents=True, exist_ok=True) # Create the subdirectory
    st_config_path = _create_yaml_file(st_subdir, DEFAULT_ST_CONFIG, ST_CONFIG_CONTENT)

    # Act
    config = load_config(main_config_path=str(main_path))

    # Assert
    assert config is not None
    assert "relevance_checker" in config
    assert "sentence_transformer_filter" in config["relevance_checker"]
    st_filter_conf = config["relevance_checker"]["sentence_transformer_filter"]
    assert st_filter_conf["model_name"] == ST_CONFIG_CONTENT["sentence_transformer_filter"]["model_name"]
    assert st_filter_conf["similarity_threshold"] == ST_CONFIG_CONTENT["sentence_transformer_filter"]["similarity_threshold"]
