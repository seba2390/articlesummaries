![arXiv Paper Monitor Logo](assets/logo.png)

# 📄 arXiv Paper Monitor

## 📝 Description

This project provides a configurable Python application to monitor publications on arXiv. It automatically fetches papers updated on the previous calendar day across specified categories, checks their relevance (using keyword matching or LLM-based assessment via Groq), outputs the findings to a file, and can send an email summary containing the details of relevant papers.

The application runs on a daily schedule and is designed with a modular structure.

## ✨ Features

*   **Configurable Monitoring:** Define arXiv categories and fetch limits in `config.yaml`.
*   **Previous Day Fetching:** Fetches arXiv papers last updated on the previous calendar day (UTC).
*   **Flexible Relevance Checking:** Choose the checking method via `relevance_checking_method` in `config.yaml`:
    *   `"keyword"`: Filters papers based on keywords (defined per source) found in the title/abstract.
    *   `"llm"`: Uses Groq's API (requires API key) for advanced relevance assessment based on a custom prompt.
*   **Groq Batch Processing:** Leverages Groq's batch API internally for efficient LLM processing when the `llm` method is selected.
*   **Email Summaries:** Optionally sends beautifully formatted HTML email summaries of each run, embedding relevant paper details (title, link, authors, categories, keywords/LLM info, abstract).
*   **Configurable Output File:** Appends relevant paper details to a text file in Markdown or plain text format.
*   **Daily Scheduling:** Runs automatically at a configurable time and timezone.
*   **Progress Indicator:** Uses `tqdm` to show progress during arXiv API result processing.
*   **Structured Logging:** Provides clear console output.
*   **Modular Design:** Extensible with new paper sources, filtering logic, relevance checkers, or output/notification methods (via ABCs).
*   **Tested:** Includes `pytest` tests with options to skip external API calls.

## 📁 Project Structure

```
articlesummaries/
├── .git/                   # Git repository data
├── .gitignore              # Files/directories ignored by Git
├── .pytest_cache/          # Pytest cache directory
├── __pycache__/            # Python bytecode cache (and in subdirs)
├── config.yaml             # Configuration file
├── main.py                 # Main script to run the monitor
├── pytest.ini              # Pytest configuration (defines markers like 'llm')
├── README.md               # This file
├── relevant_papers.txt     # Default output file (created/appended)
├── requirements.txt        # Python dependencies
├── src/                    # Source code directory
│   ├── __init__.py
│   ├── config_loader.py    # Handles loading config.yaml
│   │   ├── __init__.py
│   │   ├── base_filter.py  # ABC for filters
│   │   └── keyword_filter.py # Keyword filtering implementation
│   ├── llm/                # Modules for LLM relevance checking
│   │   ├── __init__.py
│   │   ├── base_checker.py # ABC for relevance checkers
│   │   └── groq_checker.py # Groq implementation
│   ├── notifications/      # Modules for sending notifications
│   │   ├── __init__.py
│   │   ├── base_notification.py # ABC for notifications
│   │   └── email_sender.py # Email summary implementation
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
│   │   └── test_keyword_filter.py
│   ├── llm/
│   │   └── test_groq_checker.py
│   ├── notifications/
│   │   └── test_email_sender.py # Tests for email functionality
│   ├── output/
│   │   └── test_file_writer.py
│   ├── paper_sources/
│   │   └── test_arxiv_source.py
│   ├── test_config_loader.py
│   ├── test_main.py
│   └── test_scheduler.py
└── venv/                   # Virtual environment (if created)
```
*Note: Cache directories (`__pycache__`, `.pytest_cache`), `venv`, and the output file (`relevant_papers.txt` or custom) are typically generated during setup/runtime and might be in your `.gitignore`.*

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

This file controls the application's behavior. See comments within the file for detailed explanations. Create `config.yaml` in the project root if it doesn't exist, using the structure below as a template.

```yaml
# Configuration file for arXiv Paper Monitor

# Maximum total number of papers to fetch from arXiv in a single run.
# This limits the results returned by the arXiv API query for the specified categories
# and date range. Acts as a safeguard.
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
      # SECURITY: Consider using environment variables (e.g., GROQ_API_KEY) instead!
      api_key: "YOUR_GROQ_API_KEY" # Replace with your key or remove if using env var
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
    # SECURITY: Use App Password (Gmail 2FA) or environment variable (EMAIL_SENDER_PASSWORD)
    # instead of storing your plain password here!
    password: "YOUR_APP_PASSWORD_OR_ENV_VAR_VALUE"

  # SMTP Server Details (Lookup for your provider)
  smtp:
    server: "smtp.gmail.com"
    port: 587 # Usually 587 for TLS
```

**Configuration Details Guide:**

*   **`max_total_results`**: Limits how many papers arXiv returns for the fetch query (based on categories and date). (Default: 500 in code if not set)
*   **`relevance_checking_method`**: Selects the core logic: `"keyword"` or `"llm"`. (Required)
*   **`paper_source.arxiv.categories`**: List of arXiv categories to fetch from. (Required)
*   **`paper_source.arxiv.keywords`**: List of case-insensitive keywords used *only* when `relevance_checking_method` is `"keyword"`.
*   **`relevance_checker.llm.provider`**: Specifies the LLM service (currently only `"groq"`). Used only if method is `"llm"`.
*   **`relevance_checker.llm.groq.api_key`**: Your Groq API key. **Required** if method is `"llm"` and provider is `"groq"`. **SECURITY:** Prefer loading this from an environment variable (`GROQ_API_KEY`) over hardcoding it. The script will check the environment variable first.
*   **`relevance_checker.llm.groq.model`**: (Optional) Specify a Groq model. Defaults to `llama-3.1-8b-instant` in the code.
*   **`relevance_checker.llm.groq.prompt`**: The question/instruction given to the LLM.
*   **`relevance_checker.llm.groq.confidence_threshold`**: Minimum LLM confidence (0.0-1.0) to mark a paper as relevant.
*   **`output.file`**: Path where results are appended. (Default: `relevant_papers.txt`)
*   **`output.format`**: Style of the output file (`"markdown"` or `"plain"`).
*   **`output.include_confidence` / `include_explanation`**: Whether to include LLM metadata in the *output file* (only applies when method is `"llm"`).
*   **`schedule.run_time`**: Time for the daily automatic run (HH:MM). (Default: `"08:00"` in code if not set)
*   **`schedule.timezone`**: (Optional) Timezone for `run_time`. Requires `pytz` (included) or Python >= 3.9 (`zoneinfo`).
*   **`notifications.send_email_summary`**: Enable/disable email (`true`/`false`).
*   **`notifications.email_recipients`**: List of recipient email addresses.
*   **`notifications.email_sender.address` / `password`**: Credentials for the *sending* email account. **SECURITY WARNING:** **Do not store plain passwords directly in the config file.** Use an App Password (especially for Gmail with 2FA) or preferably load the password from an environment variable (`EMAIL_SENDER_PASSWORD`). The script checks the environment variable first.
*   **`notifications.smtp.server` / `port`**: Your email provider's outgoing mail server details (e.g., `smtp.gmail.com`, port `587`).

## ▶️ Usage

Run the main script from the project's root directory:

```bash
python main.py
```

The script will perform an initial check upon starting and then run daily at the time specified in `config.yaml`. It logs progress to the console. Press `Ctrl+C` to stop gracefully.

## ✅ Testing

1.  Ensure development dependencies are installed: `pip install -r requirements.txt` (includes `pytest`, `pytest-mock`).
2.  Run `pytest` from the project root:
    ```bash
    # Run all tests
    pytest

    # Run tests verbosely
    pytest -v

    # Run tests BUT SKIP those marked 'llm' (which require API keys/external calls)
    pytest -m "not llm"
    ```
    *Note: The `llm` marker is defined in `pytest.ini`.*

## 🚀 Extensibility

The application uses Abstract Base Classes (ABCs) for modularity, making it easier to add new functionality.

### Adding a New Paper Source

*(Limitation: Currently, `main.py` is hardcoded to instantiate and use `ArxivSource`. Future improvements could make the source configurable via `config.yaml`.)*

1.  **Create Source Class:** In `src/paper_sources/`, create `your_source.py` inheriting from `BasePaperSource` (`src.paper_sources.base_source.BasePaperSource`).
2.  **Implement Methods:** Implement the abstract methods: `configure(config)` and `fetch_papers()`.
3.  **Update `main.py` (Manual Step):** Modify `main.py` to instantiate your new source class instead of `ArxivSource`.

### Adding a New Relevance Checker (e.g., different LLM provider)

1.  **Create Checker Class:** In `src/llm/`, create `your_checker.py` inheriting from `BaseRelevanceChecker` (`src.llm.base_checker.BaseRelevanceChecker`).
2.  **Implement Methods:** Implement the abstract methods: `configure(config)`, `check_relevance(paper)`, and potentially `check_relevance_batch(papers)`.
3.  **Update `create_relevance_checker` in `main.py`:** Modify the factory function in `main.py` to recognize and instantiate your new checker based on the `relevance_checker.llm.provider` config value.
4.  **Update Config:** Add necessary configuration options for your checker in `config.yaml` under `relevance_checker.llm`.

### Adding a New Output Format/Method

1.  **Create Output Class:** In `src/output/`, create `your_output.py` inheriting from `BaseOutput` (`src.output.base_output.BaseOutput`).
2.  **Implement Methods:** Implement `configure(config)` and `output(papers)`.
3.  **Update `create_output_handlers` in `main.py`:** Modify the factory function to instantiate your new output handler based on config (e.g., based on `output.format` or a new `output.type` key).

### Adding a New Notification Method

1.  **Create Notification Class:** In `src/notifications/`, create `your_notification.py` inheriting from `BaseNotification` (`src.notifications.base_notification.BaseNotification`).
2.  **Implement Methods:** Implement `configure(config)` and `notify(papers, run_stats)`.
3.  **Update `create_notification_handler` in `main.py`:** Modify the factory function to instantiate your new handler based on config.

## 🤝 Contributing (Placeholder)

Contributions are welcome! Please follow standard fork/pull request procedures. (Consider adding guidelines for code style, testing, etc.)

## 📜 License

This project is licensed under the [GNU GPLv3](LICENSE).
