"""Handles sending email notifications with run summaries."""

import html  # For escaping potentially problematic characters in paper details
import logging
import smtplib

# Removed MIMEBase and encoders as we are not attaching files anymore
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

# Import Paper type hint
from src.paper import Paper

logger = logging.getLogger(__name__)


class EmailSender:
    """Handles the formatting and sending of summary email notifications.

    Reads configuration for SMTP server, sender credentials, recipients,
    and formatting options. Constructs an HTML email summarizing the
    results of a monitoring run.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initializes the EmailSender and validates necessary configuration.

        Args:
            config: The main application configuration dictionary.
        """
        # Extract relevant configuration sections with defaults
        self.config = config  # Store full config if needed later
        notification_config = config.get("notifications", {})
        self.sender_config = notification_config.get("email_sender", {})
        self.smtp_config = notification_config.get("smtp", {})
        self.recipients = notification_config.get("email_recipients", [])
        self.send_email = notification_config.get("send_email_summary", False)
        self.output_config = config.get("output", {})  # Used for formatting flags

        # Validate essential configuration if email sending is enabled
        if self.send_email:
            if not self.recipients:
                logger.warning(
                    "Email notifications enabled (`notifications.send_email_summary: true`), "
                    "but no recipients defined in `notifications.email_recipients`. Disabling email."
                )
                self.send_email = False  # Disable if no recipients
            if not self.sender_config.get("address") or not self.sender_config.get("password"):
                logger.error(
                    "Email notifications enabled, but sender address or password missing in `notifications.email_sender`. "
                    "Disabling email."
                )
                self.send_email = False  # Disable if credentials missing
            if not self.smtp_config.get("server") or not self.smtp_config.get("port"):
                logger.error(
                    "Email notifications enabled, but SMTP server or port missing in `notifications.smtp`. "
                    "Disabling email."
                )
                self.send_email = False  # Disable if SMTP config missing

    def _format_paper_html(self, paper: Paper, checking_method: str) -> str:
        """Formats a single Paper object into an HTML block for the email body.

        Includes title (as a link), authors, categories, publication date,
        conditionally includes matched keywords or LLM relevance details,
        and provides the abstract in a collapsible section.

        Args:
            paper: The Paper object to format.
            checking_method: The relevance checking method used ('keyword' or 'llm').

        Returns:
            An HTML string representing the paper.
        """
        # Escape potentially unsafe characters in user-generated content
        title_escaped = html.escape(paper.title)
        # Handle potential None values before escaping
        abstract_escaped = html.escape(paper.abstract or "N/A")
        authors_str = html.escape(", ".join(paper.authors) if paper.authors else "N/A")
        categories_str = html.escape(", ".join(paper.categories) if paper.categories else "N/A")
        published_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"
        url_escaped = html.escape(paper.url or "#")  # Use # if URL is missing

        # Start building the HTML block for the paper
        paper_html = f'''
        <div class="paper">
          <h3><a href="{url_escaped}" target="_blank">{title_escaped}</a></h3>
          <p><strong>Authors:</strong> {authors_str}</p>
          <p><strong>Categories:</strong> {categories_str}</p>
          <p><strong>Published/Updated:</strong> {published_str}</p>
        '''

        # Add matched keywords block if applicable
        if checking_method == "keyword" and paper.matched_keywords:
            kw_str = html.escape(", ".join(paper.matched_keywords))
            paper_html += f'<p><strong>Matched Keywords:</strong> <span class="keywords">{kw_str}</span></p>\n'

        # Add LLM relevance block if applicable and configured to be included
        include_confidence = self.output_config.get("include_confidence", False)
        include_explanation = self.output_config.get("include_explanation", False)
        if checking_method == "llm" and paper.relevance:
            if include_confidence:
                confidence = paper.relevance.get("confidence", "N/A")
                try:
                    # Format confidence as float with 2 decimal places if possible
                    confidence_str = f"{float(confidence):.2f}"
                except (ValueError, TypeError):
                    # Fallback if confidence is not a valid number
                    confidence_str = html.escape(str(confidence))
                paper_html += f"<p><strong>LLM Confidence:</strong> {confidence_str}</p>\n"
            if include_explanation:
                explanation = html.escape(paper.relevance.get("explanation", "N/A"))
                paper_html += f'<details><summary><strong>LLM Explanation</strong></summary><p class="explanation">{explanation}</p></details>\n'

        # Add abstract in a collapsible <details> section
        paper_html += f"""
          <details>
            <summary><strong>Abstract</strong></summary>
            <p class="abstract">{abstract_escaped}</p>
          </details>
        </div>
        """
        return paper_html

    def _format_html_summary(
        self, num_fetched: int, relevant_papers: List[Paper], run_duration_secs: float, checking_method: str
    ) -> str:
        """Creates the full HTML body for the summary email.

        Includes a header with run statistics and then lists the details
        of each relevant paper formatted by `_format_paper_html`.

        Args:
            num_fetched: Total number of papers fetched initially.
            relevant_papers: List of papers deemed relevant.
            run_duration_secs: Duration of the monitoring job run in seconds.
            checking_method: The relevance checking method used ('keyword' or 'llm').

        Returns:
            The complete HTML string for the email body.
        """
        num_relevant = len(relevant_papers)
        run_completed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Basic CSS styling for the email
        # Note: Email client CSS support varies. Inline styles might be more robust
        # but this external block is cleaner to read/maintain.
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>arXiv Paper Monitor Summary</title>
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"; margin: 20px; line-height: 1.5; color: #333; background-color: #f4f7f6; }}
          .container {{ max-width: 800px; margin: 0 auto; background-color: #ffffff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
          h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; margin-top: 0; }}
          h2 {{ color: #3498db; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
          h3 {{ margin-bottom: 5px; color: #2980b9; }}
          h3 a {{ color: #2980b9; text-decoration: none; }}
          h3 a:hover {{ text-decoration: underline; }}
          p {{ margin: 5px 0 10px 0; }}
          .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #bdc3c7; }}
          .summary p {{ margin: 8px 0; }}
          .paper {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; background-color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }}
          .keywords {{ background-color: #eafaf1; color: #16a085; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; display: inline-block; margin-right: 4px; }}
          details summary {{ cursor: pointer; font-weight: bold; color: #34495e; margin-bottom: 5px; outline: none; }}
          details summary:hover {{ color: #2c3e50; }}
          details[open] summary {{ margin-bottom: 10px; }}
          .abstract, .explanation {{ margin-left: 20px; font-size: 0.95em; color: #555; background-color: #fdfefe; padding: 10px; border-radius: 4px; border: 1px dashed #ecf0f1; }}
        </style>
        </head>
        <body>
        <div class="container">
          <h1>arXiv Paper Monitor: Run Summary</h1>
          <div class="summary">
            <p><strong>Run completed:</strong> {run_completed_time}</p>
            <p><strong>Relevance checking method used:</strong> <span style="font-weight: bold; color: #8e44ad;">{html.escape(checking_method.upper())}</span></p>
            <p><strong>Total papers fetched (initial):</strong> {num_fetched}</p>
            <p><strong>Relevant papers found:</strong> {num_relevant}</p>
            <p><strong>Total run duration:</strong> {run_duration_secs:.2f} seconds</p>
          </div>
        """

        # Add section for relevant papers if any were found
        if relevant_papers:
            html_content += "<h2>Relevant Papers Found</h2>\n"
            for paper in relevant_papers:
                html_content += self._format_paper_html(paper, checking_method)
        else:
            html_content += "<p>No relevant papers were found in this run.</p>\n"

        html_content += """
        </div> {# End container #}
        </body>
        </html>
        """
        return html_content

    def send_summary_email(
        self,
        num_fetched: int,
        relevant_papers: List[Paper],
        run_duration_secs: float,
        checking_method: str,
        # output_file: Optional[str] = None # Parameter removed as it wasn't used
    ):
        """Connects to the SMTP server, sends the HTML summary email, and disconnects.

        This method orchestrates the email sending process:
        1. Checks if email sending is enabled and configured.
        2. Constructs the email subject.
        3. Creates a MIMEMultipart message with the HTML body.
        4. Connects to the SMTP server using TLS.
        5. Authenticates with the sender credentials.
        6. Sends the email to the configured recipients.
        7. Closes the SMTP connection.
        Handles common SMTP errors gracefully.

        Args:
            num_fetched: Total number of papers fetched initially.
            relevant_papers: List of papers deemed relevant.
            run_duration_secs: Duration of the monitoring job run in seconds.
            checking_method: The relevance checking method used ('keyword' or 'llm').
        """
        # Early exit if email is disabled or misconfigured (checked in __init__)
        if not self.send_email:
            logger.info("Email notifications are disabled or improperly configured. Skipping email sending.")
            return

        # Extract required configuration details
        sender_email = self.sender_config["address"]
        sender_password = self.sender_config["password"]
        smtp_server = self.smtp_config["server"]
        smtp_port = self.smtp_config["port"]

        # Construct the email subject line
        subject = (
            f"arXiv Monitor Summary - {datetime.now().strftime('%Y-%m-%d')} - {len(relevant_papers)} Relevant Paper(s)"
        )

        # Create the email message object (MIMEMultipart for HTML content)
        msg = MIMEMultipart("alternative")
        msg["From"] = sender_email
        msg["To"] = ", ".join(self.recipients)  # Comma-separated list for header
        msg["Subject"] = subject
        # Set content type explicitly to help some clients
        msg.add_header("Content-Type", "text/html; charset=utf-8")

        # Format the HTML body
        html_body = self._format_html_summary(
            num_fetched=num_fetched,
            relevant_papers=relevant_papers,
            run_duration_secs=run_duration_secs,
            checking_method=checking_method,
        )
        # Attach the HTML part, ensuring UTF-8 encoding
        msg.attach(MIMEText(html_body, "html", _charset="utf-8"))

        # Initialize SMTP server connection variable
        server: Optional[smtplib.SMTP] = None
        try:
            # Connect to the SMTP server
            logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
            # Consider adding a timeout to the SMTP connection
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)  # 30-second timeout
            server.ehlo()  # Identify client to server
            # Upgrade connection to secure TLS
            server.starttls()
            server.ehlo()  # Re-identify after TLS

            # Login to the SMTP server
            logger.info("Logging into SMTP server...")
            server.login(sender_email, sender_password)

            # Send the email
            logger.info(f"Sending email summary to: {', '.join(self.recipients)}")
            # sendmail expects recipients as a list, not a comma-separated string
            server.sendmail(sender_email, self.recipients, msg.as_string())
            logger.info("Summary email sent successfully.")

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "SMTP Authentication Error: Check sender email/password in config `notifications.email_sender`. "
                "If using Gmail/Google Workspace, an App Password might be required. Email not sent."
            )
        except smtplib.SMTPConnectError as e:
            logger.error(
                f"SMTP Connection Error: Could not connect to {smtp_server}:{smtp_port}. "
                f"Check server/port in config `notifications.smtp`. Error: {e}. Email not sent."
            )
        except smtplib.SMTPServerDisconnected:
            logger.error("SMTP Server Disconnected unexpectedly. Email may not have been sent.")
        except TimeoutError:
            logger.error(f"SMTP connection to {smtp_server}:{smtp_port} timed out. Email not sent.")
        except Exception as e:
            # Catch any other exceptions during the SMTP process
            logger.error(f"An unexpected error occurred while sending email: {e}", exc_info=True)
        finally:
            # Ensure the SMTP connection is closed gracefully
            if server:
                try:
                    server.quit()
                    logger.info("SMTP connection closed.")
                except Exception as e_quit:
                    # Log error during quit but don't crash
                    logger.error(f"Error closing SMTP connection: {e_quit}")
