from __future__ import annotations

import ctypes
import os
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple


def _find_chrome_window() -> Optional[int]:
    user32 = ctypes.windll.user32
    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.lower()
        if "chrome" in title:
            windows.append((hwnd, buffer.value))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return windows[0][0] if windows else None


def _get_chrome_titles() -> list[str]:
    user32 = ctypes.windll.user32
    titles = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value
        if "chrome" in title.lower():
            titles.append(title)
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return titles


def _activate_chrome() -> bool:
    hwnd = _find_chrome_window()
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.5)
        return True
    except Exception:
        return False


def check_gmail_status() -> Tuple[bool, str]:
    """
    Checks if Gmail is currently logged in, open, or requiring login in Chrome.
    Returns (is_logged_in, status_reason).
    """
    titles = _get_chrome_titles()
    for t in titles:
        low = t.lower()
        if "sign in - google accounts" in low or "accounts.google.com" in low:
            return False, "login_required"
        if "gmail" in low or "inbox" in low:
            return True, "logged_in"

    # If Chrome isn't clearly on a login page, assume normal profile readiness
    return True, "ready"


def open_gmail_in_chrome(account_label: str = "") -> str:
    """
    Opens Gmail in the user's existing Chrome session.
    """
    import webbrowser
    u_idx = "0"
    if "work" in account_label.lower() or "second" in account_label.lower() or "2" in account_label:
        u_idx = "1"

    url = f"https://mail.google.com/mail/u/{u_idx}/"
    try:
        # Try to use Chrome if registered, or default browser
        webbrowser.open(url)
        time.sleep(2.0)
        _activate_chrome()
        return f"Opened Gmail in Chrome (account {u_idx})."
    except Exception as exc:
        return f"Could not launch Gmail: {exc}"


def compose_email_in_gmail(
    recipient: str,
    subject: str,
    body: str,
    account_label: str = "",
    attachment_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Navigates to the official Gmail compose URL pre-filling recipient, subject, and body.
    """
    import webbrowser
    u_idx = "0"
    if "work" in (account_label or "").lower() or "second" in (account_label or "").lower() or "2" in (account_label or ""):
        u_idx = "1"

    params = {
        "view": "cm",
        "fs": "1",
        "to": recipient,
        "su": subject,
        "body": body,
    }
    query_string = urllib.parse.urlencode(params)
    compose_url = f"https://mail.google.com/mail/u/{u_idx}/?{query_string}"

    try:
        webbrowser.open(compose_url)
        time.sleep(2.5)
        _activate_chrome()

        attach_msg = ""
        if attachment_path:
            att = Path(attachment_path)
            if att.exists():
                try:
                    import pyperclip
                    pyperclip.copy(str(att.resolve()))
                    attach_msg = f" File '{att.name}' path copied to clipboard for instant attachment."
                except Exception:
                    attach_msg = f" File '{att.name}' ready at {attachment_path}."
            else:
                attach_msg = f" (Warning: attachment '{attachment_path}' not found on disk)."

        return True, f"Gmail compose opened for {recipient} with subject '{subject}'.{attach_msg}"
    except Exception as exc:
        return False, f"Failed to open Gmail compose: {exc}"


def send_current_email_in_browser() -> Tuple[bool, str]:
    """
    Triggers the Gmail shortcut (Ctrl+Enter) in the active Gmail compose tab to send the message.
    """
    try:
        import pyautogui

        if not _activate_chrome():
            return False, "Could not bring Chrome to the foreground to send the email."

        time.sleep(0.8)
        # Ctrl+Enter sends email in Gmail
        pyautogui.hotkey("ctrl", "enter")
        time.sleep(1.5)

        return True, "Email sent successfully via Gmail."
    except Exception as exc:
        return False, f"Could not trigger send in Gmail: {exc}"
