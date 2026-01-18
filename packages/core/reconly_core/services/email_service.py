"""Email service for sending digest emails - OSS version."""
import logging
import os
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime

from jinja2 import Template

logger = logging.getLogger(__name__)


def markdown_to_html(text: str) -> str:
    """
    Convert basic markdown to HTML.

    Handles: headers (##), bold (**), bullet points (•), links [text](url), line breaks.

    Args:
        text: Markdown text

    Returns:
        HTML formatted text
    """
    if not text:
        return ""

    # Convert headers (## Header -> <h4>Header</h4>)
    text = re.sub(r'^## (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)

    # Convert markdown links [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # Convert bold (**text** -> <strong>text</strong>)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Convert bullet points (• or - or * at start of line)
    text = re.sub(r'^[•\-\*] (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)

    # Wrap consecutive <li> items in <ul>
    text = re.sub(r'(<li>.*</li>\n)+', lambda m: '<ul>' + m.group(0) + '</ul>\n', text, flags=re.MULTILINE)

    # Convert double line breaks to paragraphs
    paragraphs = text.split('\n\n')
    formatted_paragraphs = []
    for para in paragraphs:
        para = para.strip()
        if para and not para.startswith('<h') and not para.startswith('<ul>'):
            formatted_paragraphs.append(f'<p>{para}</p>')
        else:
            formatted_paragraphs.append(para)

    return '\n'.join(formatted_paragraphs)


class EmailService:
    """Service for sending digest emails via SMTP."""

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None
    ):
        """
        Initialize email service.

        Args:
            smtp_host: SMTP server hostname (default: from SMTP_HOST env var)
            smtp_port: SMTP port (default: from SMTP_PORT env var or 587)
            smtp_user: SMTP username (default: from SMTP_USER env var)
            smtp_password: SMTP password (default: from SMTP_PASSWORD env var)
            from_email: From email address (default: from SMTP_FROM_EMAIL env var)
            from_name: From name (default: from SMTP_FROM_NAME env var or "Reconly")
        """
        self.smtp_host = smtp_host or os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = smtp_port or int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = smtp_user or os.getenv('SMTP_USER')
        self.smtp_password = smtp_password or os.getenv('SMTP_PASSWORD')
        self.from_email = from_email or os.getenv('SMTP_FROM_EMAIL', self.smtp_user)
        self.from_name = from_name or os.getenv('SMTP_FROM_NAME', 'Reconly')

    def _extract_youtube_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        if not url:
            return None
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional, falls back to HTML stripped)

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Validate configuration
            if not self.smtp_host or not self.smtp_user or not self.smtp_password:
                logger.error("Email service not configured. Missing SMTP credentials.")
                return False

            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            # Add plain text version if provided
            if body_text:
                part1 = MIMEText(body_text, 'plain', 'utf-8')
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(part2)

            # Send email
            logger.info(f"Sending email to {to_email} via {self.smtp_host}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            return False

    def render_digest_email(
        self,
        digests: List[dict],
        date: Optional[datetime] = None,
        language: str = 'en'
    ) -> tuple[str, str]:
        """
        Render digest email template.

        Args:
            digests: List of digest dictionaries
            date: Date for the digest (default: today)
            language: Language for template text (en or de)

        Returns:
            Tuple of (html_body, text_body)
        """
        if date is None:
            date = datetime.now()

        # Process digests: extract real titles from markdown and convert to HTML
        processed_digests = []
        for digest in digests:
            processed = digest.copy()
            summary = processed.get('summary', '')

            # Extract title from markdown header if present (## Title)
            title_match = re.match(r'^##\s+(.+?)(?:\n|$)', summary)
            if title_match:
                # Use extracted title instead of generic one
                extracted_title = title_match.group(1).strip()
                # Remove "Summary of " prefix if present
                extracted_title = re.sub(r'^Summary of\s+', '', extracted_title)
                processed['title'] = extracted_title
                # Remove the header from summary
                summary = re.sub(r'^##\s+.+?\n+', '', summary)

            # Convert markdown to HTML for email display
            processed['summary_html'] = markdown_to_html(summary)
            processed['summary_text'] = summary

            # Get thumbnail URL - only use actual images, no placeholders
            thumbnail_url = processed.get('image_url')
            if not thumbnail_url and processed.get('source_type', '').lower() == 'youtube':
                # For YouTube, construct thumbnail from video URL
                url = processed.get('url', '')
                video_id = self._extract_youtube_video_id(url)
                if video_id:
                    thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            processed['thumbnail_url'] = thumbnail_url

            processed_digests.append(processed)

        # Language-specific text
        if language == 'de':
            title = "Reconly Digest"
            intro = f"Hier sind deine {len(digests)} Zusammenfassungen für heute:"
            source_label = "Quelle"
            lang_label = "Sprache"
            tags_label = "Tags"
            read_more = "Zum Original-Artikel"
            footer = "Automatisch generiert mit KI"
        else:
            title = "Reconly Digest"
            intro = f"Here are your {len(digests)} summaries for today:"
            source_label = "Source"
            lang_label = "Language"
            tags_label = "Tags"
            read_more = "Read original article"
            footer = "Automatically generated with AI"

        # HTML template
        html_template = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { margin: 0; font-size: 28px; }
        .header p { margin: 10px 0 0 0; opacity: 0.9; }
        .content { padding: 20px; background: #ffffff; }
        .digest { background: #f8f9fa; margin: 20px 0; padding: 20px; border-left: 4px solid #667eea; border-radius: 4px; }
        .digest-header { width: 100%; }
        .digest-title { vertical-align: top; }
        .digest-thumbnail-cell { vertical-align: top; text-align: right; padding-left: 15px; width: 115px; }
        .digest h3 { margin-top: 0; color: #667eea; font-size: 20px; }
        .digest-thumbnail { width: 115px; height: 65px; object-fit: cover; border-radius: 4px; border: 1px solid #e0e0e0; }
        .metadata { color: #666; font-size: 0.9em; margin: 10px 0; padding: 10px 0; border-bottom: 1px solid #e0e0e0; }
        .metadata span { margin-right: 15px; }
        .summary { margin: 15px 0; line-height: 1.7; }
        .summary h4 { color: #333; font-size: 1.1em; margin: 15px 0 10px 0; font-weight: 600; }
        .summary h5 { color: #555; font-size: 1em; margin: 12px 0 8px 0; font-weight: 600; }
        .summary p { margin: 8px 0; }
        .summary ul { margin: 10px 0; padding-left: 20px; }
        .summary li { margin: 5px 0; }
        .summary strong { color: #444; font-weight: 600; }
        .read-more { display: inline-block; margin-top: 10px; color: #667eea; text-decoration: none; font-weight: 500; }
        .read-more:hover { text-decoration: underline; }
        .footer { text-align: center; color: #999; padding: 20px; font-size: 0.85em; background: #f8f9fa; border-radius: 0 0 8px 8px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📰 {{ title }}</h1>
        <p>{{ date.strftime('%A, %B %d, %Y') if language == 'en' else date.strftime('%A, %d. %B %Y') }}</p>
    </div>

    <div class="content">
        <p>{{ intro }}</p>

        {% for digest in digests %}
        <div class="digest">
            <table class="digest-header" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td class="digest-title"><h3>{{ digest.title }}</h3></td>
                    {% if digest.thumbnail_url %}<td class="digest-thumbnail-cell"><img src="{{ digest.thumbnail_url }}" alt="" class="digest-thumbnail" /></td>{% endif %}
                </tr>
            </table>
            <div class="metadata">
                <span><strong>{{ source_label }}:</strong> {{ digest.source_type|upper }}</span>
                <span><strong>{{ lang_label }}:</strong> {{ digest.language|upper }}</span>
                {% if digest.tags %}<span><strong>{{ tags_label }}:</strong> {{ digest.tags|join(', ') }}</span>{% endif %}
            </div>
            <div class="summary">{{ digest.summary_html|safe }}</div>
            {% if not digest.consolidated_count or digest.consolidated_count <= 1 %}
            <a href="{{ digest.url }}" class="read-more">→ {{ read_more }}</a>
            {% endif %}
        </div>
        {% endfor %}
    </div>

    <div class="footer">
        <p>Reconly - {{ footer }}</p>
    </div>
</body>
</html>
        """)

        # Text template
        text_template = Template("""
📰 {{ title|upper }} - {{ date.strftime('%d.%m.%Y') }}
=====================================

{{ intro }}

{% for digest in digests %}
---
{{ loop.index }}. {{ digest.title }}

{{ source_label }}: {{ digest.source_type|upper }} | {{ lang_label }}: {{ digest.language|upper }}
{% if digest.tags %}{{ tags_label }}: {{ digest.tags|join(', ') }}{% endif %}

{{ digest.summary_text }}

{% if not digest.consolidated_count or digest.consolidated_count <= 1 %}
→ {{ digest.url }}
{% endif %}

{% endfor %}
---
Reconly - {{ footer }}
        """)

        html_body = html_template.render(
            digests=processed_digests,
            date=date,
            language=language,
            title=title,
            intro=intro,
            source_label=source_label,
            lang_label=lang_label,
            tags_label=tags_label,
            read_more=read_more,
            footer=footer
        )
        text_body = text_template.render(
            digests=processed_digests,
            date=date,
            title=title,
            intro=intro,
            source_label=source_label,
            lang_label=lang_label,
            tags_label=tags_label,
            footer=footer
        )

        return html_body, text_body

    def send_digest_email(
        self,
        to_email: str,
        digests: List[dict],
        date: Optional[datetime] = None,
        language: str = 'en'
    ) -> bool:
        """
        Send digest email to recipient.

        Args:
            to_email: Recipient email address
            digests: List of digest dictionaries
            date: Date for digest (default: today)
            language: Language for email (en or de)

        Returns:
            True if sent successfully
        """
        if date is None:
            date = datetime.now()

        subject = f"📰 Reconly Digest - {date.strftime('%d.%m.%Y')}"
        html_body, text_body = self.render_digest_email(digests, date, language)

        return self.send_email(to_email, subject, html_body, text_body)
