# Multi-Source Paper Monitor

![Paper Monitor Logo](assets/logo_1.png)

## 📝 Overview

This project provides a configurable Python application to monitor publications from multiple academic sources, currently supporting **arXiv** and **bioRxiv/medRxiv**. It automatically fetches recent papers across specified categories, checks their relevance based on configured methods (keywords, LLM, or local Sentence Transformer models), outputs the findings to a file, and sends comprehensive email summaries.

The application runs on a daily schedule defined in the configuration and features a modular design for potential extension.

## ✨ Features

*   **Multi-Source Monitoring:** Fetches papers from arXiv, bioRxiv, and medRxiv based on settings in `config.yaml`.
*   **Source-Specific Configuration:** Define categories, keywords (for filtering), and fetch windows (days to look back) independently for each source.
*   **Flexible Relevance Checking:**
    *   `"keyword"`: Filters papers using source-specific keyword lists against titles/abstracts.
    *   `"llm"`: Utilizes Groq's API (requires API key) for advanced relevance assessment based on a custom prompt and confidence threshold.
    *   `"local_sentence_transformer"`: Filters based on semantic similarity using a local Sentence Transformer model. Requires the `configs/local_sentence_transformer_configs/sentence_transformer_config.yaml` file to exist and be configured.
    *   `"none"`: Treats all fetched papers as relevant.
*   **Efficient LLM Processing:** Leverages Groq's API with batching and configurable delays for the `llm` method.
*   **Detailed Email Summaries:** Sends HTML emails summarizing each run, including source-specific fetch statistics (count, window, query times) and details of relevant papers (title, link, authors, categories, matched keywords/LLM info, abstract).
*   **File Output:** Appends relevant paper details to a configurable file (`markdown` or `plain` text format), optionally including LLM metadata.
*   **Scheduled Execution:** Runs automatically via `schedule` library at a configurable time and timezone.
*   **Progress Feedback:** Provides feedback during potentially lengthy operations (e.g., model downloads, batch processing).
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

The application uses a modular, multi-file configuration system managed by `src/config_loader.py`. This allows for separation of concerns and easier management of settings. Here's a breakdown:

**1. `main_config.yaml` (Project Root)**

This is the primary configuration file and controls the overall application behavior. Key settings include:

*   `active_sources` (List[str]): Specifies which paper sources to monitor (e.g., `["arxiv", "biorxiv"]`). Each name listed here **must** have a corresponding `configs/paper_sources_configs/<source_name>_config.yaml` file.
*   `relevance_checking_method` (str): Determines the core method for filtering papers. This is crucial as it dictates which other configuration files and settings are relevant. Options:
    *   `"keyword"`: Filters based on keywords defined within each source's specific config file in `configs/paper_sources_configs/`. No additional configuration files are needed for this method itself.
    *   `"llm"`: Uses an external LLM provider for relevance checking. Requires `relevance_checker.llm.provider` to be set (e.g., `"groq"`) in this file, and the corresponding `configs/llm_configs/<provider>_llm_config.yaml` file must exist and be configured.
    *   `"local_sentence_transformer"`: Filters based on semantic similarity using a local Sentence Transformer model. Requires the `configs/local_sentence_transformer_configs/sentence_transformer_config.yaml` file to exist and be configured.
    *   `"none"`: Skips relevance checking entirely; all fetched papers are considered relevant.
*   `send_email_summary` (bool): A top-level switch (`true` or `false`) to enable or disable sending email summaries after each run.
*   `max_total_results` (int): A global safeguard limit on the total number of papers fetched across all sources in a single run (primarily affects arXiv).
*   `relevance_checker` (dict): Contains nested settings for specific checking methods:
    *   `llm.provider` (str): Specifies the LLM provider (e.g., `"groq"`) when `relevance_checking_method` is `"llm"`.
*   `output` (dict): Configures how relevant papers are saved:
    *   `file` (str): Path to the output file.
    *   `format` (str): Output format (`"markdown"` or `"plain"`).
    *   `include_confidence`, `include_explanation` (bool): Whether to include LLM-specific details in the output (if using `llm` method).
*   `schedule` (dict): Configures the daily run schedule:
    *   `run_time` (str): Time in HH:MM format (24-hour clock).
    *   `timezone` (str, optional): Timezone for the `run_time` (e.g., `"UTC"`, `"America/New_York"`).

**2. `configs/paper_sources_configs/<source_name>_config.yaml`**

Located in the `configs/paper_sources_configs/` subdirectory. You need **one separate file for each source** listed in `main_config.yaml`'s `active_sources`.

*   Each file must contain a top-level key matching the source name (e.g., `arxiv:` in `arxiv_config.yaml`).
*   Within this key, you configure source-specific settings:
    *   `categories` (List[str]): List of categories/subjects relevant to that source.
    *   `keywords` (List[str]): Keywords used for filtering **only if** `relevance_checking_method` in `main_config.yaml` is set to `"keyword"`.
    *   `fetch_window` (int): Number of past days to look back for papers from this specific source.
    *   May include other source-specific options (e.g., `server` for `biorxiv`/`medrxiv`).

**3. `configs/email_config.yaml`**

Located directly in the `configs/` directory. This file holds **all settings related to email notifications**. It is loaded **only if** `send_email_summary` is `true` in `main_config.yaml`.

*   Settings are nested under a `notifications` key.
*   `email_recipients` (List[str]): List of email addresses to send the summary to.
*   `email_sender` (dict): Contains the sender's `address` and `password` (or App Password). **SECURITY WARNING:** Avoid hardcoding passwords. Use environment variables (`EMAIL_SENDER_PASSWORD`) or a dedicated secrets manager.
*   `smtp` (dict): Contains the `server` address and `port` number for your email provider's SMTP service.

**4. `configs/llm_configs/<provider>_llm_config.yaml` (Optional)**

Located in the `configs/llm_configs/` subdirectory. This file is loaded **only if** `relevance_checking_method` is `"llm"` in `main_config.yaml`.

*   The filename must match the provider specified in `main_config.yaml` (e.g., `groq_llm_config.yaml`).
*   Contains provider-specific settings under a key matching the provider name (e.g., `groq:`).
*   Settings typically include `api_key` (use `GROQ_API_KEY` environment variable preferably), `model` name, `prompt`, `confidence_threshold`, `batch_size`, `batch_delay_seconds`, etc.

**5. `configs/local_sentence_transformer_configs/sentence_transformer_config.yaml` (Optional)**

Located in the `configs/local_sentence_transformer_configs/` subdirectory. This file is loaded **only if** `relevance_checking_method` is `"local_sentence_transformer"` in `main_config.yaml`.

*   Contains settings for the sentence transformer filter under the `sentence_transformer_filter` key:
    *   `model_name` (str): The name of the pre-trained Sentence Transformer model to download and use (e.g., `"all-MiniLM-L6-v2"`).
    *   `similarity_threshold` (float): The minimum cosine similarity score (0.0-1.0) needed between a paper's abstract and a target text to be considered relevant.
    *   `target_texts` (str or List[str]): One or more texts defining your core interest. The filter finds papers semantically similar to these.
    *   `device` (str, optional): Specify the device (`'cuda'`, `'cpu'`, `'mps'`). If omitted, the library attempts auto-detection.
    *   `batch_size` (int, optional): Number of abstracts to encode in a single batch. Adjust based on available VRAM/RAM. Defaults to 32.

**Loading Logic:**

The `src/config_loader.py` script orchestrates the loading:
1.  Reads `main_config.yaml`.
2.  Based on `active_sources`, reads each corresponding file from `configs/paper_sources_configs/` and merges the settings into `config['paper_source']`.
3.  If `send_email_summary` is true, reads `configs/email_config.yaml` and merges its `notifications` section into `config['notifications']`.
4.  Checks `relevance_checking_method`:
    *   If `"llm"`, reads the provider file from `configs/llm_configs/` and merges settings into `config['relevance_checker']['llm'][provider]`.
    *   If `"local_sentence_transformer"`, reads `configs/local_sentence_transformer_configs/sentence_transformer_config.yaml` and merges settings into `config['relevance_checker']['sentence_transformer_filter']`.
    *   If `"keyword"` or `"none"`, no additional relevance config files are loaded.
5.  Returns the final, merged configuration dictionary.

This ensures that only relevant configuration files are loaded based on the chosen methods.

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

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

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

### Example `configs/email_config.yaml`

```yaml
# Email Configuration
notifications:
  email_recipients:
    - "recipient1@example.com"
    - "recipient2@example.com"
  email_sender:
    address: "sender@example.com"
    # SECURITY WARNING: Use an App Password (Gmail 2FA) or environment variable
    # (EMAIL_SENDER_PASSWORD) instead of your actual password!
    password: "YOUR_APP_PASSWORD_OR_ENV_VAR"

  # SMTP Server Details (e.g., for Gmail)
  smtp:
    server: "smtp.gmail.com"
    port: 587 # Typically 587 (TLS) or 465 (SSL)
```

### Example `configs/llm_configs/groq_llm_config.yaml`

```yaml
# Groq LLM Provider Configuration
groq:
  # Get from https://console.groq.com/keys
  # SECURITY: Use GROQ_API_KEY environment variable instead of hardcoding here.
  api_key: ""
  # Optional: Specify Groq model. Defaults to 'llama-3.1-8b-instant'.
  # model: "mixtral-8x7b-32768"
  prompt: "Is this paper relevant to machine learning agents and reinforcement learning?"
  confidence_threshold: 0.7 # Minimum confidence score (0.0-1.0) to consider relevant.
  batch_size: 10 # Number of abstracts to process per API call.
  batch_delay_seconds: 2 # Seconds to wait between batch API calls.
```

### Example `configs/local_sentence_transformer_configs/sentence_transformer_config.yaml`

```yaml
# Configuration for the Sentence Transformer filter
sentence_transformer_filter:
  # Name of the Sentence Transformer model (e.g., from Hugging Face Hub).
  # See https://www.sbert.net/docs/pretrained_models.html
  model_name: "all-MiniLM-L6-v2"
  # Minimum cosine similarity score (0.0-1.0) for relevance.
  similarity_threshold: 0.65
  # Text(s) representing your core interest.
  target_texts:
    - "machine learning agents and reinforcement learning"
    # - "Other relevant topics..."
  # Optional: Specify device ('cuda', 'cpu', 'mps'). Defaults to auto-detection.
  # device: null
  # Optional: Number of abstracts to encode in a single batch (adjust based on VRAM/RAM).
  # Defaults to 32.
  # batch_size: 32
```
