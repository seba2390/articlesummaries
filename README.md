# 📄 arXiv Paper Monitor

## 📝 Description

This project provides a configurable Python application to monitor publications on arXiv. It automatically fetches papers submitted or updated within the last 24 hours across specified categories, filters them based on relevance (currently keyword matching in title/abstract), and appends the details of relevant papers to an output file.

The application runs on a daily schedule and is designed with a modular structure, making it easy to extend with new paper sources, different filtering mechanisms, or alternative output methods.

## ✨ Features

*   **Configurable Monitoring:** Define arXiv categories, keywords, and fetch limits in a simple `config.yaml` file.
*   **Recent Paper Fetching:** Focuses on papers submitted/updated within the last 24 hours (relative to script run time).
*   **Total Results Limit:** Set a maximum total number of papers to fetch (`max_total_results`) as a safeguard.
*   **Daily Scheduling:** Automatically checks for new papers at a configurable time each day using the `schedule` library.
*   **Keyword Filtering:** Filters papers based on the presence of keywords in the title or abstract.
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
│   ├── filtering/          # Modules for filtering papers
│   │   ├── __init__.py
│   │   ├── base_filter.py  # ABC for filters
│   │   └── keyword_filter.py # Keyword filtering implementation
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

Edit the `config.yaml` file to customize the monitor's behavior:

*   `categories`: A list of arXiv category identifiers (e.g., `cs.AI`, `math.AP`). Find categories [here](https://arxiv.org/category_taxonomy).
*   `keywords`: A list of keywords to search for (case-insensitive) in paper titles and abstracts.
*   `max_total_results`: The maximum total number of papers (most recently submitted/updated) to fetch across *all* specified categories in a single run. This acts as a safeguard against fetching an excessive number of papers if the daily volume is very high.
*   `run_time_daily`: The time of day (HH:MM format, 24-hour clock) to run the check.
*   `output_file`: The path to the file where relevant paper details will be appended.

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

## 🚀 Extensibility

The use of Abstract Base Classes (`src/paper_sources/base_source.py`, `src/filtering/base_filter.py`, `src/output/base_output.py`) makes extending the application straightforward:

1.  **Add a New Paper Source:**
    *   Create a new class in `src/paper_sources/` that inherits from `BasePaperSource`.
    *   Implement the `configure` and `fetch_papers` methods. `fetch_papers` should return a list of `src.paper.Paper` objects.
    *   Modify `main.py` to instantiate and use your new source (potentially based on configuration).
2.  **Add a New Filter:**
    *   Create a new class in `src/filtering/` inheriting from `BaseFilter`.
    *   Implement `configure` and `filter`. The `filter` method takes a list of `Paper` objects and returns a filtered list.
    *   Modify `main.py` to use your new filter.
3.  **Add a New Output Handler:**
    *   Create a new class in `src/output/` inheriting from `BaseOutput`.
    *   Implement `configure` and `output`. The `output` method receives the list of relevant `Paper` objects.
    *   Modify `main.py` to use your new output handler.

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
