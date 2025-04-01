# 📄 arXiv Paper Monitor

## 📝 Description

This project provides a configurable Python application to monitor publications on arXiv. It automatically fetches papers submitted or updated within the last 24 hours across specified categories, filters them based on relevance (using keyword matching or LLM-based relevance checking), and appends the details of relevant papers to an output file.

The application runs on a daily schedule and is designed with a modular structure, making it easy to extend with new paper sources, different filtering mechanisms, or alternative output methods.

## ✨ Features

*   **Configurable Monitoring:** Define arXiv categories, keywords, and fetch limits in a simple `config.yaml` file.
*   **Recent Paper Fetching:** Focuses on papers submitted/updated within the last 24 hours (relative to script run time).
*   **Total Results Limit:** Set a maximum total number of papers to fetch (`max_total_results`) as a safeguard.
*   **Daily Scheduling:** Automatically checks for new papers at a configurable time each day using the `schedule` library.
*   **Flexible Filtering:** Choose between keyword-based filtering or LLM-based relevance checking using Groq's API.
*   **Batch Processing:** Option to process papers in batches for improved efficiency with LLM-based checking.
*   **File Output:** Appends details of relevant papers (ID, Title, Authors, URL, Abstract, Updated Date) to a specified text file.
*   **Structured Console Output:** Provides clear, formatted logging during execution.
*   **Modular Design:** Easily extensible with new paper sources, filters, or output handlers using Abstract Base Classes (ABCs).
*   **Tested:** Includes a `pytest` test suite for verifying functionality.

## 📁 Project Structure

```
articlesummaries/
├── .git/                   # Git repository data
├── .gitignore              # Files/directories ignored by Git
├── .pytest_cache/          # Pytest cache directory
├── __pycache__/            # Python bytecode cache
├── config.yaml             # Configuration file
├── main.py                 # Main script to run the monitor
├── pytest.ini              # Pytest configuration
├── README.md               # This file
├── relevant_papers.txt     # Default output file (created/appended by the script)
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── __init__.py
│   ├── config_loader.py    # Handles loading config.yaml
│   │   ├── __init__.py
│   │   ├── base_filter.py  # ABC for filters
│   │   └── keyword_filter.py # Keyword filtering implementation
│   ├── llm_relevance.py    # LLM-based relevance checking
│   ├── output/             # Modules for handling output
│   │   ├── __init__.py
│   │   ├── base_output.py  # ABC for output handlers
│   │   └── file_writer.py  # File writing implementation
│   ├── paper_sources/      # Modules for fetching papers
│   │   ├── __init__.py
│   │   ├── base_source.py  # ABC for paper sources
│   │   └── arxiv_source.py # arXiv implementation
│   ├── paper.py            # Defines the Paper data structure
│   └── scheduler.py        # Handles job scheduling
├── tests/                  # Test suite directory
│   ├── __init__.py
│   ├── filtering/
│   │   ├── __init__.py
│   │   └── test_keyword_filter.py
│   ├── output/
│   │   ├── __init__.py
│   │   └── test_file_writer.py
│   ├── paper_sources/
│   │   ├── __init__.py
│   │   └── test_arxiv_source.py
│   ├── test_config_loader.py
│   ├── test_main.py
│   └── test_scheduler.py
└── venv/                   # Virtual environment (if created according to setup)
```
*Note: Cache, venv, and output files might be generated during setup/runtime.*

## 🛠️ Setup and Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <your-repo-url>
    cd articlesummaries
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # For Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Configuration

The `config.yaml` file controls all aspects of the application. Here's a detailed breakdown of all available settings:

### Paper Source Configuration
```yaml
paper_source:
  arxiv:
    categories: ["cs.AI", "cs.LG"]  # List of arXiv categories to monitor
    keywords: ["machine learning", "neural networks"]  # Keywords for filtering
    max_total_results: 100  # Maximum papers to fetch per run
    sort_by: "submittedDate"  # Sort papers by submission date
    sort_order: "descending"  # Get newest papers first
```

### Relevance Checking Configuration
```yaml
relevance_checker:
  type: "keyword"  # or "llm"

  # For keyword-based checking (type: "keyword")
  keywords: ["machine learning", "neural networks"]  # Keywords to match

  # For LLM-based checking (type: "llm")
  llm:
    provider: "groq"  # Currently supports "groq" or "custom"
    api_key: "your-groq-api-key"  # Required for Groq
    model: "llama-3.1-8b-instant"  # Groq model to use
    prompt: "Is this paper relevant to machine learning research?"  # Custom prompt
    confidence_threshold: 0.7  # Minimum confidence (0-1) to consider relevant

    # For custom LLM provider
    custom:
      module_path: "path.to.your.module"  # Python module path
      class_name: "YourLLMChecker"  # Class name in the module
```

### Output Configuration
```yaml
output:
  file: "relevant_papers.txt"  # Output file path
  format: "markdown"  # or "plain"
  include_confidence: true  # Include LLM confidence scores
  include_explanation: true  # Include LLM explanations
```

### Scheduling Configuration
```yaml
schedule:
  run_time: "09:00"  # Daily run time (24-hour format)
  timezone: "UTC"  # Timezone for run time
```

## 🚀 Extensibility

The application is designed to be easily extended with new paper sources and LLM checkers. Here's how to add your own implementations:

### Adding a New Paper Source

1. Create a new file in `src/paper_sources/` (e.g., `custom_source.py`):
```python
from .base_source import BasePaperSource
from ..paper import Paper

class CustomPaperSource(BasePaperSource):
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the source with settings from config.yaml."""
        self.settings = config["paper_source"]["custom"]

    def fetch_papers(self) -> List[Paper]:
        """Fetch papers from your custom source."""
        # Implement your paper fetching logic here
        papers = []
        # ... fetch papers from your source ...
        return papers
```

2. Update `src/paper_sources/__init__.py`:
```python
from .custom_source import CustomPaperSource

__all__ = ["ArxivSource", "CustomPaperSource"]
```

3. Add configuration in `config.yaml`:
```yaml
paper_source:
  custom:
    # Your custom source settings
```

### Adding a New LLM Checker

1. Create a new file in `src/llm/` (e.g., `custom_checker.py`):
```python
from .base_checker import BaseLLMChecker, LLMResponse

class CustomLLMChecker(BaseLLMChecker):
    def __init__(self, api_key: str):
        """Initialize your LLM checker."""
        self.api_key = api_key
        # ... setup your LLM client ...

    def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
        """Check relevance using your LLM."""
        # Implement single paper checking
        return LLMResponse(
            is_relevant=True,
            confidence=0.8,
            explanation="Your explanation"
        )

    def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
        """Check relevance for multiple papers."""
        # Implement batch checking
        return [self.check_relevance(abstract, prompt) for abstract in abstracts]
```

2. Update `src/llm/__init__.py`:
```python
from .custom_checker import CustomLLMChecker

__all__ = ["BaseLLMChecker", "LLMResponse", "GroqChecker", "CustomLLMChecker"]
```

3. Add configuration in `config.yaml`:
```yaml
relevance_checker:
  type: "llm"
  llm:
    provider: "custom"
    custom:
      module_path: "src.llm.custom_checker"
      class_name: "CustomLLMChecker"
```

### Testing Your Extensions

1. Create test files in the appropriate `tests/` directory:
```python
# tests/paper_sources/test_custom_source.py
def test_custom_source():
    source = CustomPaperSource()
    # ... test your implementation ...

# tests/llm/test_custom_checker.py
def test_custom_checker():
    checker = CustomLLMChecker("test-key")
    # ... test your implementation ...
```

2. Run the tests:
```bash
pytest tests/paper_sources/test_custom_source.py
pytest tests/llm/test_custom_checker.py
```

## ▶️ Usage

Run the main script from the project's root directory:

```bash
python main.py
```

The script will perform an initial check upon starting and then run daily at the time specified in `config.yaml`. It will log its progress to the console with clear formatting. Press `Ctrl+C` to stop the script gracefully.

## ✅ Testing

The project includes a test suite using `pytest`. To run the tests:

1.  Ensure you have installed the dependencies (including `pytest` and `pytest-mock`) from `requirements.txt`.
2.  Run `pytest` from the project's root directory:
    ```bash
    pytest
    ```
    Or for more detailed output:
    ```bash
    pytest -v
    ```

## 📦 Dependencies

*   **Runtime:**
    *   [arxiv](https://pypi.org/project/arxiv/): Python wrapper for the arXiv API.
    *   [schedule](https://pypi.org/project/schedule/): Human-friendly Python job scheduling.
    *   [PyYAML](https://pypi.org/project/PyYAML/): YAML parser and emitter for Python.
    *   [groq](https://pypi.org/project/groq/): Python client for Groq API (Note: review usage if integrated).
*   **Testing:**
    *   [pytest](https://pypi.org/project/pytest/): Testing framework.
    *   [pytest-mock](https://pypi.org/project/pytest-mock/): Pytest fixture for mocking.

---
_This README reflects the project structure and dependencies as of April 2024._
