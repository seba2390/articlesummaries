# 📄 arXiv Paper Monitor

## 📝 Description

This project provides a configurable Python application to monitor publications on arXiv. It automatically fetches papers updated on the previous calendar day across specified categories, checks their relevance (using keyword matching or LLM-based assessment via Groq), and can send an email summary containing the details of relevant papers.

The application runs on a daily schedule and is designed with a modular structure.

## ✨ Features

*   **Configurable Monitoring:** Define arXiv categories and fetch limits in `config.yaml`.
*   **Previous Day Fetching:** Fetches arXiv papers last updated on the previous calendar day (UTC).
*   **Flexible Relevance Checking:** Choose the checking method via `relevance_checking_method` in `config.yaml`:
    *   `"keyword"`: Filters papers based on keywords (defined per source) found in the title/abstract.
    *   `"llm"`: Uses Groq's API (requires API key) for advanced relevance assessment based on a custom prompt.
*   **Groq Batch Processing:** Leverages Groq's batch API internally for efficient LLM processing.
*   **Email Summaries:** Optionally sends beautifully formatted HTML email summaries of each run, embedding relevant paper details (title, link, authors, categories, keywords/LLM info, abstract).
*   **Configurable Output File:** Appends relevant paper details to a text file in Markdown or plain text format.
*   **Daily Scheduling:** Runs automatically at a configurable time and timezone.
*   **Progress Indicator:** Uses `tqdm` to show progress during arXiv API result processing.
*   **Structured Logging:** Provides clear console output.
*   **Modular Design:** Extensible with new paper sources or LLM checkers (via ABCs).
*   **Tested:** Includes `pytest` tests.

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
│   │   ├── __init__.py
│   │   └── config_loader.py # Handles loading config.yaml
│   ├── filtering/          # Modules for filtering papers
│   │   ├── __init__.py
│   │   └── filtering/     # Modules for filtering papers
│   │   └── keyword_filter.py # Keyword filtering implementation
│   ├── llm/                # Modules for LLM relevance checking
│   │   ├── __init__.py
│   │   └── llm/           # Modules for LLM relevance checking
│   │   └── groq_checker.py # Groq implementation
│   ├── notifications/      # Modules for sending notifications
│   │   ├── __init__.py     # (optional)
│   │   └── notifications/ # Modules for sending notifications
│   │   └── email_sender.py # Email summary implementation
│   ├── output/             # Modules for handling output
│   │   ├── __init__.py
│   │   └── output/        # Modules for handling output
│   │   └── base_output.py  # ABC for output handlers
│   │   └── file_writer.py  # File writing implementation
│   ├── paper_sources/      # Modules for fetching papers
│   │   ├── __init__.py
│   │   └── paper_sources/ # Modules for fetching papers
│   │   └── base_source.py  # ABC for paper sources
│   │   └── arxiv_source.py # arXiv implementation
│   ├── paper.py            # Defines the Paper data structure
│   └── scheduler.py        # Handles job scheduling
├── tests/                  # Test suite directory
│   ├── __init__.py
│   ├── filtering/
│   │   └── test_keyword_filter.py
│   ├── llm/
│   │   └── test_groq_checker.py
│   ├── notifications/
│   │   └── test_email_sender.py # (Example test location)
│   ├── output/
│   │   └── test_file_writer.py
│   ├── paper_sources/
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

This file controls the application's behavior. See comments within the file for detailed explanations.

```yaml
# Configuration file for arXiv Paper Monitor

# Maximum total number of papers to fetch across *all* categories in a single run.
# This acts as a safeguard if the number of papers published today is very large.
max_total_results: 500

# --- Relevance Checking Method ---
# Determines the overall method used for checking paper relevance.
# Options: "keyword" or "llm"
relevance_checking_method: "keyword"

# --- Paper Source Configuration ---
paper_source:
  type: "arxiv" # Currently only supports arXiv
  arxiv:
    # ArXiv categories to search (e.g., cs.AI, cs.LG, math.AP)
    # Find categories here: https://arxiv.org/category_taxonomy
    categories: ["cs.AI", "cs.LG", "cs.CL"]

    # Keywords specifically for filtering papers fetched from this arXiv source
    # Used ONLY when relevance_checking_method is "keyword".
    keywords: ["large language model", "transformer", "attention"]

    # fetch_window: 24 # NOTE: Fetch window is currently hardcoded in ArxivSource to previous day

# --- Relevance Checker Specific Settings ---
# Contains settings used by the different relevance checking methods.
relevance_checker:
  # Settings used when relevance_checking_method is "llm"
  llm:
    # Currently only "groq" provider is implemented.
    provider: "groq"

    # Settings specific to the "groq" provider
    groq:
      # REQUIRED if provider is "groq". Get from https://console.groq.com/keys
      api_key: "YOUR_GROQ_API_KEY" # Replace with your key
      # Optional: Specify a Groq model. Defaults internally to llama-3.1-8b-instant.
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
  # Only applies if relevance_checking_method is "llm". Include LLM confidence score?
  include_confidence: true
  # Only applies if relevance_checking_method is "llm". Include LLM explanation?
  include_explanation: true

# --- Scheduling Configuration ---
schedule:
  # Time of day (HH:MM format, 24-hour clock) to run the check automatically.
  run_time: "09:00"
  # Optional: Timezone for the run_time. Defaults to system local time if omitted.
  # Examples: "UTC", "America/New_York". Requires 'pytz' or Python 3.9+ ('zoneinfo').
  # timezone: "UTC"

# --- Notifications Configuration ---
notifications:
  # Set to true to enable sending summary emails, false to disable.
  send_email_summary: true

  # List of email addresses that will receive the summary email.
  email_recipients:
    - "user1@example.com"
    # - "user2@example.com"

  # Sender Email Credentials - IMPORTANT: See security note in guide below!
  email_sender:
    address: "your_sender_email@gmail.com"
    # Use App Password for Gmail if 2FA is enabled
    password: "YOUR_APP_PASSWORD_OR_REGULAR_PASSWORD"

  # SMTP Server Details (Lookup for your provider)
  smtp:
    server: "smtp.gmail.com"
    port: 587 # Usually 587 for TLS
```

**Configuration Details Guide:**

*   **`max_total_results`**: Limits how many papers arXiv returns *per category list query* for the target date. Acts as a safety net. (Default: 500 in code if not set)
*   **`relevance_checking_method`**: Selects the core logic: `"keyword"` or `"llm"`. (Required)
*   **`paper_source.arxiv.categories`**: List of arXiv categories to fetch from. (Required)
*   **`paper_source.arxiv.keywords`**: List of case-insensitive keywords used *only* when `relevance_checking_method` is `"keyword"`.
*   **`relevance_checker.llm.provider`**: Specifies the LLM service (currently only `"groq"`). Used only if method is `"llm"`.
*   **`relevance_checker.llm.groq.api_key`**: Your Groq API key. **Required** if method is `"llm"` and provider is `"groq"`.
*   **`relevance_checker.llm.groq.model`**: (Optional) Specify a Groq model. Defaults to `llama-3.1-8b-instant` in the code.
*   **`relevance_checker.llm.groq.prompt`**: The question/instruction given to the LLM.
*   **`relevance_checker.llm.groq.confidence_threshold`**: Minimum LLM confidence (0.0-1.0) to mark a paper as relevant.
*   **`output.file`**: Path where results are appended. (Default: `relevant_papers.txt`)
*   **`output.format`**: Style of the output file (`"markdown"` or `"plain"`).
*   **`output.include_confidence` / `include_explanation`**: Whether to include LLM metadata in the *output file* (only applies when method is `"llm"`).
*   **`schedule.run_time`**: Time for the daily automatic run (HH:MM). (Default: "08:00" in code if not set)
*   **`schedule.timezone`**: (Optional) Timezone for `run_time`. Requires `pytz` or Python >= 3.9.
*   **`notifications.send_email_summary`**: Enable/disable email (`true`/`false`).
*   **`notifications.email_recipients`**: List of recipient email addresses.
*   **`notifications.email_sender.address` / `password`**: Credentials for the *sending* email account. **Security Warning:** Use App Passwords (Gmail 2FA) or environment variables instead of storing plain passwords here!
*   **`notifications.smtp.server` / `port`**: Your email provider's outgoing mail server details (e.g., `smtp.gmail.com`, port `587`).

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

### Adding a New Notification Handler
*(Currently, only email is implemented directly. For other methods like Slack or Discord, you would create a new class in `src/notifications/`, potentially define a `BaseNotifier` ABC, and modify `main.py` to call your new handler based on configuration.)*

## 📦 Dependencies

*   **Runtime:** `arxiv`, `schedule`, `PyYAML`, `requests`, `groq`, `tqdm` (Optional: `pytz` for timezone on Python < 3.9)
*   **Testing:** `pytest`, `pytest-mock`

---
_README updated April 2024._
