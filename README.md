# Multi-Source Paper Monitor

![Paper Monitor Logo](assets/logo_1.png)

## 📝 Overview

This project provides a configurable Python application to monitor publications from multiple academic sources, currently supporting **arXiv** and **bioRxiv/medRxiv**. It automatically fetches recent papers across specified categories, checks their relevance based on configured methods (keywords or LLM), outputs the findings to a file, and sends comprehensive email summaries.

The application runs on a daily schedule defined in the configuration and features a modular design for potential extension.

## ✨ Features

*   **Multi-Source Monitoring:** Fetches papers from arXiv and bioRxiv/medRxiv based on settings in `config.yaml`.
*   **Source-Specific Configuration:** Define categories, keywords (for filtering), and fetch windows (days to look back) independently for each source.
*   **Flexible Relevance Checking:**
    *   `"keyword"`: Filters papers using source-specific keyword lists against titles/abstracts.
    *   `"llm"`: Utilizes Groq's API (requires API key) for advanced relevance assessment based on a custom prompt and confidence threshold.
    *   `"none"`: Treats all fetched papers as relevant.
*   **Efficient LLM Processing:** Leverages Groq's API with batching and configurable delays for the `llm` method.
*   **Detailed Email Summaries:** Sends HTML emails summarizing each run, including source-specific fetch statistics (count, window, query times) and details of relevant papers (title, link, authors, categories, matched keywords/LLM info, abstract).
*   **File Output:** Appends relevant paper details to a configurable file (`markdown` or `plain` text format), optionally including LLM metadata.
*   **Scheduled Execution:** Runs automatically via `schedule` library at a configurable time and timezone.
*   **Progress Indicators:** Uses `tqdm` for visual feedback during API calls.
*   **Structured Logging:** Provides informative console output.
*   **Modular & Tested:** Built with Abstract Base Classes (ABCs) and includes `pytest` tests (with markers to skip external API calls).

## 📁 Project Structure

```plaintext
articlesummaries/
├── .gitignore
├── config.yaml             # --- Configuration File --- (*Create this*)
├── main.py                 # Main execution script
├── pytest.ini              # Pytest configuration (markers)
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── assets/                 # Assets (e.g., logo)
│   └── logo_1.png
├── src/                    # --- Source Code ---
│   ├── __init__.py
│   ├── config_loader.py    # Loads config.yaml
│   ├── paper.py            # Defines the Paper data class
│   ├── scheduler.py        # Handles job scheduling
│   ├── paper_sources/      # Modules for fetching papers
│   │   ├── __init__.py
│   │   ├── base_source.py  # ABC for paper sources
│   │   ├── arxiv_source.py # arXiv implementation
│   │   └── biorxiv_source.py # bioRxiv/medRxiv implementation
│   ├── filtering/          # Modules for filtering papers
│   │   ├── __init__.py
│   │   ├── base_filter.py  # ABC for filters
│   │   └── keyword_filter.py # Keyword filtering implementation
│   ├── llm/                # Modules for LLM relevance checking
│   │   ├── __init__.py
│   │   ├── base_checker.py # ABC for LLM checkers
│   │   └── groq_checker.py # Groq implementation
│   ├── notifications/      # Modules for sending notifications
│   │   ├── __init__.py
│   │   ├── base_notification.py # (Not currently used, placeholder ABC)
│   │   └── email_sender.py # Email summary implementation
│   └── output/             # Modules for handling output
│       ├── __init__.py
│       ├── base_output.py  # ABC for output handlers
│       └── file_writer.py  # File writing implementation
├── tests/                  # --- Test Suite ---
│   ├── __init__.py
│   ├── filtering/
│   │   └── test_keyword_filter.py
│   ├── llm/
│   │   └── test_groq_checker.py
│   ├── notifications/
│   │   └── test_email_sender.py
│   ├── output/
│   │   └── test_file_writer.py
│   ├── paper_sources/
│   │   ├── test_arxiv_source.py
│   │   └── test_biorxiv_source.py
│   ├── test_config_loader.py
│   ├── test_main.py
│   └── test_scheduler.py
└── venv/                   # Virtual environment (if created)

# Generated at runtime (usually gitignored):
# relevant_papers.txt     # Example default output file
# .pytest_cache/
# __pycache__/
```

## 🛠️ Setup and Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <your-repo-url>
    cd articlesummaries
    ```
2.  **Create and activate a virtual environment (Recommended):**
    ```bash
    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate

    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Create and Configure `config.yaml`:** Copy the example structure below into a `config.yaml` file in the project root and customize it.

## ⚙️ Configuration (`config.yaml`)

This file controls the application's behavior. See the comments within the example and the guide below for details.

```yaml
# ==========================================
# Multi-Source Paper Monitor Configuration
# ==========================================

# --- Global Settings ---

# List of sources to activate for fetching. Corresponds to keys under 'paper_source'.
# Example: ["arxiv", "biorxiv"]
active_sources: ["arxiv", "biorxiv"]

# Default number of days to look back for papers if not specified per source.
# Each source uses this or its own 'fetch_window' setting.
global_fetch_window_days: 4

# (Used by arXiv) Maximum total number of papers to fetch from arXiv API per run.
# Acts as a safeguard against excessively large result sets.
max_total_results: 500

# --- Relevance Checking ---

# Method to determine relevance: "keyword", "llm", or "none".
relevance_checking_method: "keyword"

# Settings used only when relevance_checking_method is "llm".
relevance_checker:
  llm:
    provider: "groq" # Currently only "groq" is implemented.
    groq:
      # REQUIRED if provider is "groq". Get from https://console.groq.com/keys
      # SECURITY: Use GROQ_API_KEY environment variable instead of hardcoding here.
      api_key: "YOUR_GROQ_API_KEY"
      # Optional: Specify Groq model. Defaults to 'llama-3.1-8b-instant'.
      # model: "mixtral-8x7b-32768"
      prompt: "Is this paper relevant to machine learning agents and reinforcement learning?"
      confidence_threshold: 0.7 # Minimum confidence score (0.0-1.0) to consider relevant.
      batch_size: 10 # Number of abstracts to process per API call.
      batch_delay_seconds: 2 # Seconds to wait between batch API calls.

# --- Paper Source Specific Settings ---
paper_source:

  # Settings for arXiv
  arxiv:
    # ArXiv categories: https://arxiv.org/category_taxonomy
    categories:
      - cs.AI
      - cs.CV
      - cs.LG
      - stat.ML
    # Keywords for filtering arXiv papers (if method is "keyword"). Case-insensitive.
    keywords:
      - agent
      - "foundation model"
      - diffusion
      - transformer
    # Optional: Override global_fetch_window_days for this source.
    fetch_window: 7

  # Settings for bioRxiv / medRxiv
  biorxiv:
    server: "biorxiv" # Can be "biorxiv" or "medrxiv"
    # Categories: https://www.biorxiv.org/collection (Case-sensitive, use spaces)
    categories:
      - Biochemistry
      - Bioinformatics
      - Neuroscience
      - Plant Biology
    # Keywords for filtering bioRxiv/medRxiv papers (if method is "keyword"). Case-insensitive.
    keywords:
      - protein
      - sequencing
      - brain
    # Optional: Override global_fetch_window_days for this source.
    fetch_window: 3

# --- Output Settings ---
output:
  file: "relevant_papers.md" # Path where results are appended.
  format: "markdown" # "markdown" or "plain".
  # Include LLM details in the file output (if method is "llm"):
  include_confidence: true
  include_explanation: false

# --- Scheduling Settings ---
schedule:
  run_time: "09:00" # Daily run time (HH:MM, 24-hour clock).
  # Optional: Timezone for run_time (e.g., "UTC", "America/New_York").
  # Requires pytz (installed) or Python >= 3.9 (zoneinfo).
  # Defaults to system local time if omitted or invalid.
  # timezone: "UTC"

# --- Notification Settings ---
notifications:
  send_email_summary: true # Enable/disable email notifications.
  email_recipients:
    - "recipient1@example.com"
    # - "recipient2@example.com"

  # Sender Email Account Details
  email_sender:
    address: "your_sender_email@gmail.com"
    # SECURITY WARNING: Use an App Password (Gmail 2FA) or environment variable
    # (EMAIL_SENDER_PASSWORD) instead of your actual password!
    password: "YOUR_APP_PASSWORD_OR_ENV_VAR"

  # SMTP Server Details (e.g., for Gmail)
  smtp:
    server: "smtp.gmail.com"
    port: 587 # Typically 587 (TLS) or 465 (SSL)
```

**Configuration Guide:**

*   **`active_sources`**: List which keys under `paper_source` to use.
*   **`global_fetch_window_days`**: Default lookback period if a source doesn't define `fetch_window`.
*   **`max_total_results`**: (arXiv only) Limits results from the API call.
*   **`relevance_checking_method`**: `keyword`, `llm`, `none`.
*   **`relevance_checker.llm...`**: Settings for LLM checks (provider, API key, model, prompt, threshold, batching). **SECURITY:** Use `GROQ_API_KEY` environment variable for the API key.
*   **`paper_source.<source_name>.*`**: Configure `categories`, `keywords`, and optional `fetch_window` for each source.
    *   `biorxiv.server`: Set to `"biorxiv"` or `"medrxiv"`.
*   **`output.*`**: File path, format (`markdown` or `plain`), and LLM detail inclusion for the output file.
*   **`schedule.*`**: Daily run time (`HH:MM`) and optional `timezone`.
*   **`notifications.*`**: Email settings. **SECURITY:** Use an environment variable (`EMAIL_SENDER_PASSWORD`) or App Password for the sender password.

## ▶️ Usage

Ensure your `config.yaml` is created and configured correctly, and any necessary environment variables (e.g., `GROQ_API_KEY`, `EMAIL_SENDER_PASSWORD`) are set.

Run the main script from the project root directory (ensure your virtual environment is active):

```bash
python main.py
```

The script performs an initial check on startup and then runs daily according to the schedule. Logs are printed to the console. Press `Ctrl+C` to stop.

## ✅ Testing

1.  Install development dependencies: `pip install -r requirements.txt`
2.  Run tests using `pytest`:
    ```bash
    # Run all tests
    pytest

    # Run verbosely
    pytest -v

    # Skip tests marked 'llm' (avoids real API calls)
    pytest -m "not llm"
    ```
    *(The `llm` marker is defined in `pytest.ini`)*

## 🚀 Extensibility

Adding new components typically involves:

1.  **Creating a Class:** Implement the corresponding ABC (e.g., `BasePaperSource`, `BaseLLMChecker`, `BaseOutput`) in the appropriate `src/` subdirectory.
2.  **Updating Factory Functions:** Modify the relevant `create_*` function in `main.py` to recognize and instantiate your new class based on configuration.
3.  **Updating Configuration:** Add necessary configuration options to `config.yaml` for your new component.
4.  **Writing Tests:** Add unit/integration tests for the new component.

*(Note: Currently, the core `check_papers` logic is geared towards the implemented sources/methods. Significant changes might require adjustments there.)*

## 📄 License

*(Consider adding a license file, e.g., MIT License)*
