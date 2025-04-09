# Multi-Source Paper Monitor

![Paper Monitor Logo](assets/logo_1.png)

## 📝 Overview

This project provides a configurable Python application to monitor publications from multiple academic sources, currently supporting **arXiv** and **bioRxiv/medRxiv**. It automatically fetches recent papers across specified categories, checks their relevance based on configured methods (keywords or LLM), outputs the findings to a file, and sends comprehensive email summaries.

The application runs on a daily schedule defined in the configuration and features a modular design for potential extension.

## ✨ Features

*   **Multi-Source Monitoring:** Fetches papers from arXiv, bioRxiv, and medRxiv based on settings in `config.yaml`.
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
├── main_config.yaml        # Main configuration file
├── main_config.example.yaml # Example main config
├── configs/                # Directory for modular configs
│   ├── email_config.yaml   # Email settings
│   ├── email_config.example.yaml # Example email settings
│   ├── paper_sources_configs/ # Source-specific settings
│   │   ├── arxiv_config.yaml
│   │   ├── arxiv_config.example.yaml
│   │   ├── biorxiv_config.yaml
│   │   ├── biorxiv_config.example.yaml
│   │   └── ... (other sources)
│   └── llm_configs/          # LLM provider settings (optional)
│       ├── groq_llm_config.yaml
│       └── groq_llm_config.example.yaml
├── main.py                 # Main execution script
├── pytest.ini              # Pytest configuration (markers)
├── README.md               # This file
├── requirements.txt        # Python dependencies
├── assets/                 # Assets (e.g., logo)
│   └── logo_1.png
├── src/                    # --- Source Code ---
│   ├── __init__.py
│   ├── config_loader.py    # Loads and merges all config files
│   ├── paper.py            # Defines the Paper data class
│   ├── scheduler.py        # Handles job scheduling
│   ├── paper_sources/      # Modules for fetching papers
│   │   ├── __init__.py
│   │   ├── base_source.py  # ABC for paper sources
│   │   ├── arxiv_source.py # arXiv implementation
│   │   └── biorxiv_source.py # bioRxiv implementation (used by medRxiv source)
│   │   └── medrxiv_source.py # medRxiv implementation
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
│   │   └── test_medrxiv_source.py
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
4.  **Create Configuration Files:**
    *   Copy `main_config.example.yaml` to `main_config.yaml`.
    *   Create a `configs/` directory in the project root.
    *   Inside `configs/`, create a `paper_sources_configs/` subdirectory.
    *   Inside `configs/`, create an `llm_configs/` subdirectory (if using LLM checks).
    *   Copy `configs/email_config.example.yaml` to `configs/email_config.yaml`.
    *   Copy source examples (e.g., `configs/paper_sources_configs/arxiv_config.example.yaml`) to `configs/paper_sources_configs/` for each source listed in `main_config.yaml`, renaming them (e.g., `arxiv_config.yaml`).
    *   Copy LLM examples (e.g., `configs/llm_configs/groq_llm_config.example.yaml`) to `configs/llm_configs/` if needed.
5.  **Configure:** Edit the copied YAML files (`main_config.yaml`, `configs/email_config.yaml`, `configs/paper_sources_configs/*.yaml`, `configs/llm_configs/*.yaml`) according to your needs. See details below.
6.  **(Optional - LLM)** If using `relevance_checking_method: "llm"` with Groq, set the `GROQ_API_KEY` environment variable:
    ```bash
    export GROQ_API_KEY='YOUR_GROQ_API_KEY'
    ```
    (Or place it in a `.env` file, which is gitignored by default).

## ⚙️ Configuration Files

The application uses a modular configuration system managed by `src/config_loader.py`:

1.  **`main_config.yaml`**: Located in the project root. This file defines the core behavior:
    *   `active_sources`: A list of source names (e.g., `"arxiv"`, `"biorxiv"`). These names correspond to the filenames (without `.yaml`) in the `configs/paper_sources_configs/` directory.
    *   `relevance_checking_method`: Sets the global method (`"keyword"`, `"llm"`, or `"none"`).
    *   `send_email_summary`: A top-level boolean (`true` or `false`) to enable/disable email summaries globally. *Note: Email details are configured in `email_config.yaml`.*
    *   `max_total_results`: A safeguard limit for the total number of papers fetched per run.
    *   `relevance_checker.llm.provider`: Specifies the LLM provider (e.g., `"groq"`) if `relevance_checking_method` is `"llm"`. *Note: Provider-specific settings (like API key, model, prompt) are loaded from `configs/llm_configs/<provider>_llm_config.yaml`.*
    *   `output`: Configures the output file (`file`), format (`format`), and whether to include LLM details (`include_confidence`, `include_explanation`).
    *   `schedule`: Defines the daily run time (`run_time`) and timezone (`timezone`).

2.  **`configs/paper_sources_configs/<source_name>_config.yaml`**: One file per active source, located in `configs/paper_sources_configs/`. Each file contains settings specific to that source:
    *   A top-level key matching the source name (e.g., `arxiv:`).
    *   `categories`: List of categories/subjects to search within.
    *   `keywords`: List of keywords used for filtering if `relevance_checking_method` is `"keyword"`.
    *   `fetch_window`: Number of past days to fetch papers from for this source.
    *   (Source-specific settings like `server` for bioRxiv/medRxiv).

3.  **`configs/email_config.yaml`**: Located in `configs/`. This file exclusively contains email notification settings under the `notifications` key:
    *   `email_recipients`: List of recipient addresses.
    *   `email_sender`: Sender's `address` and `password` (or App Password). *Security Note: Use environment variables or a secrets manager for the password instead of hardcoding.* See comments in the example file.
    *   `smtp`: SMTP `server` and `port` details.

4.  **`configs/llm_configs/<provider>_llm_config.yaml`**: (Optional) Located in `configs/llm_configs/`. Contains provider-specific LLM settings (e.g., API key, model, prompt, batching) if `relevance_checking_method` is `"llm"`.
    *   These files are structured according to the needs of the specific LLM provider implementation (e.g., `groq:` key for Groq settings).

**Loading Logic:** The `config_loader.py` script first loads `main_config.yaml`. Then, for each source listed in `active_sources`, it loads the corresponding `<source_name>_config.yaml`. It also loads `email_config.yaml` and merges its `notifications` section. Finally, if LLM checking is enabled, it loads the relevant `<provider>_llm_config.yaml` and merges its settings. This creates a single, combined configuration dictionary used by the application.

## ▶️ Running the Application

Once configured, run the main script from the project root:

```bash
python main.py
```

The script will:
1.  Load all configuration files.
2.  Log the setup.
3.  Wait until the scheduled time (`schedule.run_time`).
4.  Execute the `check_papers` job:
    *   Fetch papers from active sources.
    *   Filter/check relevance based on the configured method.
    *   Append relevant papers to the output file.
    *   Send an email summary (if enabled).
5.  Repeat daily.

To stop the scheduler, press `Ctrl+C`.

## ✅ Testing

Tests are located in the `tests/` directory and use `pytest`.

*   Run all tests:
    ```bash
    pytest
    ```
*   Run tests *excluding* those marked `llm` (which might make external API calls):
    ```bash
    pytest -m "not llm"
    ```
*   Run only tests marked `llm`:
    ```bash
    pytest -m llm
    ```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## 📜 License

This project is licensed under the [LICENSE_NAME] License - see the [LICENSE](LICENSE) file for details.

## 🚀 Extensibility

Adding new components (like paper sources or LLM relevance checkers) involves the following steps:

1.  **Create the Implementation Class:**
    *   For a new paper source, create a Python class in `src/paper_sources/` that inherits from `src.paper_sources.base_source.BasePaperSource` and implements its abstract methods (`configure`, `fetch_papers`).
    *   For a new LLM checker, create a class in `src/llm/` inheriting from `src.llm.base_checker.BaseLLMChecker` and implementing its methods.
    *   Follow a similar pattern for new output handlers or notification systems, inheriting from the corresponding base class in `src/output/` or `src/notifications/`.

2.  **Update the Factory Function:**
    *   Modify the relevant `create_*` function in `main.py` (e.g., `create_paper_source`, `create_relevance_checker`) to recognize a new configuration key or provider name and instantiate your newly created class.

3.  **Add Configuration File(s):**
    *   **Paper Source:** Create a new YAML configuration file for your source in the `configs/paper_sources_configs/` directory (e.g., `configs/paper_sources_configs/pubmed_config.yaml`). The filename (without `.yaml`) should match the source name you use in `main_config.yaml`'s `active_sources` list and the factory function logic. Define the source-specific settings within this file under a top-level key matching the source name (e.g., `pubmed:`).
    *   **LLM Checker:** If your checker requires specific configuration (API keys, models, prompts), create a configuration file in `configs/llm_configs/` (e.g., `configs/llm_configs/openai_llm_config.yaml`). Structure the settings as needed by your implementation.
    *   Update `main_config.yaml` if necessary (e.g., add the new source name to `active_sources`, set the `relevance_checker.llm.provider` to your new checker's name).

4.  **Write Tests:**
    *   Add unit tests for your new class in the corresponding subdirectory within `tests/`.
    *   Consider adding integration tests or updating existing ones in `tests/test_main.py` if your component significantly changes the main workflow.

*(Note: Depending on the complexity of the new component, adjustments might also be needed in the core `check_papers` logic within `main.py`.)*
