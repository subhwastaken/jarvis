"""Email Composer for J.A.R.V.I.S.
Opens Gmail (web) or Apple Mail pre-filled via mailto: URI.
No credentials required — uses the system default mail handler or browser.

Supported flows:
  • "write an email to xyz@gmail.com"
  • "compose an email to john saying hi there"
  • "send an email to boss@work.com about the report"
  • "email xyz@gmail.com subject: Meeting body: Let's catch up"

Windows: opens mailto: via default mail app (Outlook / Thunderbird)
macOS:   opens Gmail compose tab in default browser (fastest)
"""

import os
import re
import sys
import subprocess
import urllib.parse

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", re.I)

_SUBJECT_RE = re.compile(
    r"\bsubject[:\s]+([^;,]+?)(?:\s+(?:body|saying|message)[:\s]|$)", re.I
)
_BODY_RE = re.compile(
    r"\b(?:body|saying|message|that|content)[:\s]+(.+)", re.I
)
_TO_RE = re.compile(
    r"\b(?:to|for)\s+([\w.+-]+@[\w-]+\.[a-zA-Z]{2,})", re.I
)


def _extract_parts(text: str):
    """Parse recipient, subject, and body from natural-language email request."""
    recipient = ""
    subject = ""
    body = ""

    # Recipient — email address wins over name
    m_email = _EMAIL_RE.search(text)
    if m_email:
        recipient = m_email.group(0)

    # Subject
    m_subj = _SUBJECT_RE.search(text)
    if m_subj:
        subject = m_subj.group(1).strip().rstrip(".,!?")

    # Body
    m_body = _BODY_RE.search(text)
    if m_body:
        body = m_body.group(1).strip().rstrip(".,")

    # If no explicit subject, infer from "about X"
    if not subject:
        m_about = re.search(r"\babout\s+(?:the\s+)?(.+?)(?:\s+(?:body|saying|message)|$)", text, re.I)
        if m_about:
            subject = m_about.group(1).strip().rstrip(".,!?").title()

    return recipient, subject, body


def _open_gmail_compose(to: str, subject: str, body: str) -> str:
    """Open Gmail compose window in browser with pre-filled fields."""
    base = "https://mail.google.com/mail/?view=cm&fs=1"
    params = []
    if to:
        params.append(f"to={urllib.parse.quote(to)}")
    if subject:
        params.append(f"su={urllib.parse.quote(subject)}")
    if body:
        params.append(f"body={urllib.parse.quote(body)}")
    url = base + ("&" + "&".join(params) if params else "")

    if IS_MAC:
        subprocess.run(["open", url], capture_output=True)
    elif IS_WIN:
        os.startfile(url) if hasattr(os, "startfile") else subprocess.run(["start", url], shell=True)
    else:
        subprocess.run(["xdg-open", url], capture_output=True)

    return url


def _open_mailto(to: str, subject: str, body: str) -> str:
    """Fall back to mailto: for native mail apps."""
    params = {}
    if subject:
        params["subject"] = subject
    if body:
        params["body"] = body
    query = urllib.parse.urlencode(params)
    mailto = f"mailto:{urllib.parse.quote(to)}?{query}" if to else f"mailto:?{query}"

    if IS_MAC:
        subprocess.run(["open", mailto], capture_output=True)
    elif IS_WIN:
        os.startfile(mailto) if hasattr(os, "startfile") else subprocess.run(["start", mailto], shell=True)
    else:
        subprocess.run(["xdg-open", mailto], capture_output=True)

    return mailto


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_email_command(text: str, use_gmail: bool = True) -> str:
    """Parse natural-language email command and open the compose window.

    Examples:
        handle_email_command("write an email to john@gmail.com about the project")
        handle_email_command("compose email to boss@work.com subject: Urgent body: please call me")
    """
    to, subject, body = _extract_parts(text)

    if not to and not subject and not body:
        return (
            "I need at least a recipient email address, sir. "
            "Try: 'write an email to someone@gmail.com about the meeting'."
        )

    if use_gmail:
        _open_gmail_compose(to, subject, body)
    else:
        _open_mailto(to, subject, body)

    parts = []
    if to:
        parts.append(f"to {to}")
    if subject:
        parts.append(f"with subject '{subject}'")
    if body:
        parts.append(f"and your message pre-filled")

    desc = " ".join(parts) if parts else "a blank compose window"
    return f"Opened Gmail compose {desc}, sir. The window is ready for you to review and send."


# Alias — called from dispatcher
def compose_email(text: str) -> str:
    return handle_email_command(text)
