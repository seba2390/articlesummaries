# 📄 arXiv Paper Monitor

## 📝 Description

This project provides a configurable Python application to monitor publications on arXiv. It automatically fetches papers submitted or updated within the last 24 hours across specified categories, filters them based on relevance (using keyword matching or LLM-based relevance checking via Groq), and appends the details of relevant papers to an output file.

The application runs on a daily schedule and is designed with a modular structure, making it easy to extend with new paper sources, LLM providers, or output methods.

## ✨ Features

*   **Configurable Monitoring:** Define arXiv categories, keywords, and fetch limits in `config.yaml`.
*   **Recent Paper Fetching:** Fetches arXiv papers submitted/updated within the last 24 hours.
*   **Keyword Filtering:** Filters papers based on keywords in the title/abstract (default).
*   **LLM Relevance Checking:** Optionally uses Groq's API (requires API key) for advanced relevance assessment based on a custom prompt.
*   **Groq Batch Processing:** Leverages Groq's batch API internally for efficient LLM processing when multiple papers are fetched.
*   **Flexible Output:** Outputs relevant paper details to a configurable file in Markdown or plain text format.
*   **Daily Scheduling:** Runs automatically at a configurable time using the `schedule` library.
*   **Structured Logging:** Provides clear console output during execution.
*   **Modular Design:** Easily extensible with new paper sources or LLM checkers using Abstract Base Classes (ABCs).
*   **Tested:** Includes a `pytest` test suite.

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
├── relevant_papers.txt     # Default output file (created/appended)
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── __init__.py
│   ├── config_loader.py    # Handles loading config.yaml
│   ├── filtering/          # Modules for filtering papers
│   │   ├── __init__.py
│   │   ├── base_filter.py  # ABC for filters
│   │   └── keyword_filter.py # Keyword filtering implementation
│   ├── llm/                # Modules for LLM relevance checking
│   │   ├── __init__.py
│   │   ├── base_checker.py # ABC for LLM checkers
│   │   └── groq_checker.py # Groq implementation
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
│   ├── llm/
│   │   ├── __init__.py
│   │   └── test_groq_checker.py # (Example test location)
│   ├── output/
│   │   ├── __init__.py
│   │   └── test_file_writer.py
│   ├── paper_sources/
│   │   ├── __init__.py
│   │   └── test_arxiv_source.py
│   ├── test_config_loader.py
│   ├── test_main.py
│   └── test_scheduler.py
└── venv/                   # Virtual environment (if created)
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

## ⚙️ Configuration (`config.yaml`)

This file controls the application's behavior.

```yaml
# --- Paper Source Configuration (Currently only arXiv) ---
categories: ["cs.AI", "cs.LG"]  # List of arXiv category identifiers (e.g., cs.AI, math.AP). Find categories [here](https://arxiv.org/category_taxonomy).
max_total_results: 100        # Max papers to fetch from arXiv per run (before date filtering).

# --- Relevance Checking Configuration ---
relevance_checker:
  type: "keyword" # Options: "keyword" or "llm"

  # Settings for 'type: "keyword"'
  # Uses the keywords below to filter papers fetched by ArxivSource.
  keywords: ["machine learning", "neural network", "deep learning"] # List of keywords (case-insensitive) to match in title/abstract.

  # Settings for 'type: "llm"'
  llm:
    # Currently only "groq" provider is implemented.
    provider: "groq"

    # Settings specific to the "groq" provider
    groq:
      # REQUIRED if provider is "groq". Get from https://console.groq.com/keys
      api_key: "YOUR_GROQ_API_KEY"
      # Optional: Specify a Groq model. Defaults internally to a suitable model like llama-3.1-8b-instant.
      # model: "llama-3.1-8b-instant"
      # The prompt used to ask the LLM about relevance.
      prompt: "Based on the abstract, is this paper relevant to the field of generative AI models?"
      # Minimum confidence score (0.0 to 1.0) from the LLM to consider a paper relevant.
      confidence_threshold: 0.7

# --- Output Configuration ---
output:
  # Path to the file where relevant paper details will be appended.
  file: "relevant_papers.txt"
  # Format for the output file. Options: "markdown" or "plain"
  format: "markdown"
  # Only applies if relevance_checker.type is "llm".
  include_confidence: true
  # Only applies if relevance_checker.type is "llm".
  include_explanation: true

# --- Scheduling Configuration ---
schedule:
  # Time of day (HH:MM format, 24-hour clock) to run the check automatically.
  run_time: "09:00"
  # Optional: Timezone for the run_time. Defaults to system local time if omitted.
  # Examples: "UTC", "America/New_York". See Python's zoneinfo or pytz library for names.
  # timezone: "UTC"
```

**Configuration Details:**

*   **`categories`**: Defines which arXiv categories to monitor. (Required)
*   **`max_total_results`**: Limits how many recent papers arXiv returns *before* date filtering. Acts as a safety net. (Default: 500 in code if not set, example uses 100)
*   **`relevance_checker.type`**: Determines the filtering method.
    *   `"keyword"`: Uses the `relevance_checker.keywords` list to filter papers fetched by `ArxivSource`.
    *   `"llm"`: Uses the configured LLM provider (currently only Groq) to check relevance.
*   **`relevance_checker.keywords`**: List of case-insensitive keywords used *only* when `type` is `"keyword"`.
*   **`relevance_checker.llm.provider`**: Specifies the LLM service. Currently, only `"groq"` is supported.
*   **`relevance_checker.llm.groq.api_key`**: Your API key for Groq. **Required** if `provider` is `"groq"`.
*   **`relevance_checker.llm.groq.model`**: (Optional) Specify a Groq model. If omitted, the `GroqChecker` class uses a default (e.g., `llama-3.1-8b-instant`).
*   **`relevance_checker.llm.groq.prompt`**: The question/instruction given to the LLM for each paper's abstract.
*   **`relevance_checker.llm.groq.confidence_threshold`**: The minimum confidence score (0.0-1.0) required from the LLM response for a paper to be considered relevant.
*   **`output.file`**: Path where results are appended. (Default: `relevant_papers.txt`)
*   **`output.format`**: Style of the output file (`"markdown"` or `"plain"`).
*   **`output.include_confidence` / `include_explanation`**: Whether to include LLM metadata in the output (only applies when `relevance_checker.type` is `"llm"`).
*   **`schedule.run_time`**: Time for the daily automatic run. (Default: "08:00" in code if not set, example uses "09:00")
*   **`schedule.timezone`**: (Optional) Specifies the timezone for `run_time`. If omitted, the system's local timezone is used by the `schedule` library.

## ▶️ Usage

Run the main script from the project's root directory:

```bash
python main.py
```

The script will perform an initial check upon starting and then run daily at the time specified in `config.yaml`. It logs progress to the console. Press `Ctrl+C` to stop.

## ✅ Testing

1.  Ensure development dependencies are installed: `pip install -r requirements.txt` (includes `pytest`, `pytest-mock`).
2.  Run `pytest` from the project root:
    ```bash
    pytest
    ```
    Or for more detailed output: `pytest -v`

## 🚀 Extensibility

The application uses Abstract Base Classes (ABCs) for modularity.

### Adding a New Paper Source

*(Currently, the main script is hardcoded to use `ArxivSource`. Future improvements could make this configurable.)*

1.  **Create Source Class:** In `src/paper_sources/`, create `your_source.py` inheriting from `BasePaperSource`:
    ```python
    # src/paper_sources/your_source.py
    import logging
    from typing import Any, Dict, List
    from src.paper import Paper
    from .base_source import BasePaperSource

    logger = logging.getLogger(__name__)

    class YourSource(BasePaperSource):
        def configure(self, config: Dict[str, Any]):
            # Read source-specific config, e.g., config['paper_source']['your_source']
            logger.info("Configuring YourSource...")
            # self.api_endpoint = config['paper_source']['your_source']['endpoint']

        def fetch_papers(self) -> List[Paper]:
            logger.info("Fetching papers from YourSource...")
            papers = []
            # --- Add logic to fetch data from your source ---
            # Example: fetched_data = requests.get(self.api_endpoint).json()
            # for item in fetched_data:
            #     papers.append(Paper(id=..., title=..., ... source="your_source"))
            return papers
    ```
2.  **Update `__init__.py`:** Add your class to `src/paper_sources/__init__.py`:
    ```python
    # src/paper_sources/__init__.py
    from .base_source import BasePaperSource
    from .arxiv_source import ArxivSource
    from .your_source import YourSource # Add this

    __all__ = ["BasePaperSource", "ArxivSource", "YourSource"] # Add here
    ```
3.  **(Future Step)** Modify `main.py` to instantiate and use your source based on `config.yaml`.

### Adding a New LLM Checker

*(Currently, `main.py` directly instantiates `GroqChecker` if type is "llm". Future improvements could make the provider selection dynamic based on config.)*

1.  **Create Checker Class:** In `src/llm/`, create `your_checker.py` inheriting from `BaseLLMChecker`:
    ```python
    # src/llm/your_checker.py
    import logging
    from typing import Any, Dict, List
    from .base_checker import BaseLLMChecker, LLMResponse

    logger = logging.getLogger(__name__)

    class YourChecker(BaseLLMChecker):
        def __init__(self, api_key: str, model: str | None = None): # Adapt args as needed
            logger.info(f"Initializing YourChecker with model: {model or 'default'}")
            self.api_key = api_key
            # --- Initialize your LLM client ---
            # self.client = YourLLMClient(api_key=api_key, model=model)

        def check_relevance(self, abstract: str, prompt: str) -> LLMResponse:
            logger.debug("Checking single relevance with YourChecker")
            # --- Call your LLM API for a single abstract ---
            # Example: response = self.client.generate(...)
            is_relevant = True # Parse from response
            confidence = 0.9 # Parse from response
            explanation = "Explanation from YourChecker" # Parse from response
            return LLMResponse(is_relevant, confidence, explanation)

        def check_relevance_batch(self, abstracts: List[str], prompt: str) -> List[LLMResponse]:
            logger.debug(f"Checking batch relevance ({len(abstracts)} abstracts) with YourChecker")
            responses = []
            # --- Call your LLM API for a batch of abstracts ---
            # If your API supports batching, implement it here.
            # Otherwise, loop and call check_relevance:
            for abstract in abstracts:
                responses.append(self.check_relevance(abstract, prompt))
            return responses
    ```
2.  **Update `__init__.py`:** Add your class to `src/llm/__init__.py`:
    ```python
    # src/llm/__init__.py
    from .base_checker import BaseLLMChecker, LLMResponse
    from .groq_checker import GroqChecker
    from .your_checker import YourChecker # Add this

    __all__ = ["BaseLLMChecker", "LLMResponse", "GroqChecker", "YourChecker"] # Add here
    ```
3.  **Update Configuration:** Add settings for your checker in `config.yaml`:
    ```yaml
    relevance_checker:
      type: "llm"
      llm:
        provider: "your_checker" # Use a unique name
        your_checker: # Match the provider name
          api_key: "YOUR_CHECKER_API_KEY"
          model: "your-model-name" # Optional model setting
          # Add other specific settings if needed
    ```
4.  **(Future Step)** Modify `main.py` in `create_relevance_checker` to instantiate `YourChecker` when `provider` is `"your_checker"`.

### Adding a New Output Handler

*(Similar process: create class inheriting `BaseOutput` in `src/output/`, update `__init__.py`, modify `main.py`.)*

## 📦 Dependencies

*   **Runtime:**
    *   [arxiv](https://pypi.org/project/arxiv/): Python wrapper for the arXiv API.
    *   [schedule](https://pypi.org/project/schedule/): Human-friendly Python job scheduling.
    *   [PyYAML](https://pypi.org/project/PyYAML/): YAML parser/emitter.
    *   [requests](https://pypi.org/project/requests/): HTTP library (used by Groq checker).
    *   [groq](https://pypi.org/project/groq/): Python client for Groq API.
*   **Testing:**
    *   [pytest](https://pypi.org/project/pytest/): Testing framework.
    *   [pytest-mock](https://pypi.org/project/pytest-mock/): Pytest fixture for mocking.

---
_README updated April 2024._
