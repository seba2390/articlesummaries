"""Handles sending email notifications with run summaries."""

import html  # For escaping potentially problematic characters in paper details
import logging
import smtplib

# Removed MIMEBase and encoders as we are not attaching files anymore
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

# Import Paper type hint
from src.paper import Paper

logger = logging.getLogger(__name__)


class EmailSender:
    """Handles formatting and sending the summary email."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the EmailSender with notification configuration."""
        self.config = config.get("notifications", {})
        self.sender_config = self.config.get("email_sender", {})
        self.smtp_config = self.config.get("smtp", {})
        self.recipients = self.config.get("email_recipients", [])
        self.send_email = self.config.get("send_email_summary", False)
        self.output_config = config.get("output", {})  # Get output config for flags

        # Validate essential configuration
        if self.send_email:
            if not self.recipients:
                logger.warning("Email notifications enabled, but no recipients configured.")
                self.send_email = False
            if not self.sender_config.get("address") or not self.sender_config.get("password"):
                logger.error("Email notifications enabled, but sender address or password missing.")
                self.send_email = False
            if not self.smtp_config.get("server") or not self.smtp_config.get("port"):
                logger.error("Email notifications enabled, but SMTP server or port missing.")
                self.send_email = False

    def _format_paper_html(self, paper: Paper, checking_method: str) -> str:
        """Formats a single paper into an HTML block."""
        title_escaped = html.escape(paper.title)
        abstract_escaped = html.escape(paper.abstract or "N/A")  # Handle None abstract
        authors_str = html.escape(", ".join(paper.authors) if paper.authors else "N/A")
        categories_str = html.escape(", ".join(paper.categories) if paper.categories else "N/A")
        published_str = paper.published_date.strftime("%Y-%m-%d") if paper.published_date else "N/A"

        paper_html = f"""
        <div class="paper">
          <h3><a href="{html.escape(paper.url)}" target="_blank">{title_escaped}</a></h3>
          <p><strong>Authors:</strong> {authors_str}</p>
          <p><strong>Categories:</strong> {categories_str}</p>
          <p><strong>Published/Updated:</strong> {published_str}</p>
        """

        # Add matched keywords if applicable
        if checking_method == "keyword" and paper.matched_keywords:
            kw_str = html.escape(", ".join(paper.matched_keywords))
            paper_html += f'<p><strong>Matched Keywords:</strong> <span class="keywords">{kw_str}</span></p>\n'

        # Add LLM relevance if applicable and configured
        include_confidence = self.output_config.get("include_confidence", False)
        include_explanation = self.output_config.get("include_explanation", False)
        if checking_method == "llm" and paper.relevance:
            if include_confidence:
                confidence = paper.relevance.get("confidence", "N/A")
                try:
                    confidence_str = f"{float(confidence):.2f}"
                except:
                    confidence_str = html.escape(str(confidence))
                paper_html += f"<p><strong>LLM Confidence:</strong> {confidence_str}</p>\n"
            if include_explanation:
                explanation = html.escape(paper.relevance.get("explanation", "N/A"))
                paper_html += f'<details><summary><strong>LLM Explanation</strong></summary><p class="explanation">{explanation}</p></details>\n'

        # Add abstract in a collapsible section
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
        """Creates a beautifully formatted HTML summary including relevant papers."""
        num_relevant = len(relevant_papers)

        # Basic styling
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>arXiv Paper Monitor Summary</title>
        <style>
          body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol"; margin: 20px; line-height: 1.5; color: #333; }}
          h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
          h2 {{ color: #3498db; margin-top: 30px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
          h3 {{ margin-bottom: 5px; color: #2980b9; }}
          h3 a {{ color: #2980b9; text-decoration: none; }}
          h3 a:hover {{ text-decoration: underline; }}
          p {{ margin: 5px 0 10px 0; }}
          .summary {{ background-color: #ecf0f1; padding: 15px; border-radius: 8px; margin-bottom: 25px; border: 1px solid #bdc3c7; }}
          .summary p {{ margin: 8px 0; }}
          .paper {{ border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin-bottom: 15px; background-color: #fff; }}
          .keywords {{ background-color: #eafaf1; color: #1abc9c; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
          details summary {{ cursor: pointer; font-weight: bold; color: #34495e; margin-bottom: 5px; }}
          details summary:hover {{ color: #2c3e50; }}
          .abstract, .explanation {{ margin-left: 20px; font-size: 0.95em; color: #555; background-color: #f9f9f9; padding: 10px; border-radius: 4px; border: 1px dashed #eee; }}
        </style>
        </head>
        <body>
          <h1>arXiv Paper Monitor: Run Summary</h1>
          <div class="summary">
            <p><strong>Run completed:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>Relevance checking method used:</strong> <span style="font-weight: bold; color: #8e44ad;">{html.escape(checking_method.upper())}</span></p>
            <p><strong>Total papers fetched (initial):</strong> {num_fetched}</p>
            <p><strong>Relevant papers found:</strong> {num_relevant}</p>
            <p><strong>Total run duration:</strong> {run_duration_secs:.2f} seconds</p>
          </div>
        """

        if relevant_papers:
            html_content += "<h2>Relevant Papers Found</h2>\n"
            for paper in relevant_papers:
                html_content += self._format_paper_html(paper, checking_method)
        else:
            html_content += "<p>No relevant papers were found in this run.</p>\n"

        html_content += """
        </body>
        </html>
        """
        return html_content

    def send_summary_email(
        self,
        num_fetched: int,
        relevant_papers: List[Paper],  # Changed from num_relevant
        run_duration_secs: float,
        checking_method: str,  # Added checking method
        # Removed attachment_path
    ):
        """Sends the summary email with embedded paper details."""
        if not self.send_email:
            logger.info("Email notifications are disabled or improperly configured. Skipping email.")
            return

        sender_email = self.sender_config["address"]
        sender_password = self.sender_config["password"]
        smtp_server = self.smtp_config["server"]
        smtp_port = self.smtp_config["port"]

        subject = (
            f"arXiv Monitor Summary - {datetime.now().strftime('%Y-%m-%d')} - {len(relevant_papers)} Relevant Papers"
        )

        # Create the email message object
        msg = MIMEMultipart("alternative")  # Use alternative for HTML/Plain text
        msg["From"] = sender_email
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject

        # Create HTML body using the new formatting function
        html_body = self._format_html_summary(
            num_fetched=num_fetched,
            relevant_papers=relevant_papers,
            run_duration_secs=run_duration_secs,
            checking_method=checking_method,
        )
        # Attach HTML part
        # Ensure UTF-8 encoding is specified for HTML email part
        msg.attach(MIMEText(html_body, "html", _charset="utf-8"))

        # REMOVED Attachment logic

        server = None
        try:
            logger.info(f"Connecting to SMTP server {smtp_server}:{smtp_port}...")
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.ehlo()
            server.starttls()
            server.ehlo()
            logger.info("Logging into SMTP server...")
            server.login(sender_email, sender_password)
            logger.info(f"Sending email summary to: {', '.join(self.recipients)}")
            server.sendmail(sender_email, self.recipients, msg.as_string())
            logger.info("Summary email sent successfully.")
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP Authentication Error: Check sender email/password (or App Password). Email not sent.")
        except smtplib.SMTPConnectError:
            logger.error(
                f"SMTP Connection Error: Could not connect to {smtp_server}:{smtp_port}. Check server/port. Email not sent."
            )
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
        finally:
            if server:
                try:
                    server.quit()
                    logger.info("SMTP connection closed.")
                except Exception as e_quit:
                    logger.error(f"Error closing SMTP connection: {e_quit}")
