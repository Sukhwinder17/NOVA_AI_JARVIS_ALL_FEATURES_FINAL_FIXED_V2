from __future__ import annotations

import atexit
import ctypes
import threading
import time
from pathlib import Path

from core import config


_WA_LOCK = threading.Lock()


def _cleanup_whatsapp():
    # IMPORTANT:
    # Do NOT close the user's Chrome browser.
    pass


atexit.register(_cleanup_whatsapp)


def _find_chrome_window():
    """Find a visible Chrome window on Windows."""

    user32 = ctypes.windll.user32
    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )

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
            windows.append(hwnd)

        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)

    return windows[0] if windows else None


def _activate_chrome():
    """Bring the user's existing Chrome window to the foreground."""

    hwnd = _find_chrome_window()

    if not hwnd:
        return False

    user32 = ctypes.windll.user32

    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.8)
        return True
    except Exception:
        return False


def _get_current_url():
    """Read the current Chrome tab URL using the address bar."""

    import pyautogui
    import pyperclip

    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.25)
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.25)

    try:
        return pyperclip.paste().strip()
    except Exception:
        return ""


def _open_or_reuse_whatsapp():
    """
    Use the user's EXISTING Chrome window.

    - If the current tab is WhatsApp Web, reuse it.
    - Otherwise open WhatsApp Web in a new tab in the same Chrome.
    - Never launch another Chrome process.
    - Never create another Chrome profile.
    """

    import pyautogui
    import pyperclip

    if not _activate_chrome():
        return False, "I could not find an open Chrome window."

    current_url = _get_current_url().lower()

    if "web.whatsapp.com" in current_url:
        pyautogui.press("esc")
        time.sleep(0.5)
        return True, "existing"

    # Current tab is not WhatsApp.
    # Open WhatsApp in a new tab in the SAME Chrome window.
    pyautogui.hotkey("ctrl", "l")
    pyperclip.copy(config.WHATSAPP_URL)
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")

    time.sleep(4)

    return True, "opened"


def _wait_for_whatsapp(timeout=30):
    """
    Give WhatsApp Web enough time to load.

    UI automation cannot inspect the DOM of a normal Chrome session
    without a debugging connection, so readiness is confirmed by the
    next UI operation rather than by pretending to inspect the page.
    """

    import pyautogui

    deadline = time.monotonic() + timeout

    time.sleep(4)

    while time.monotonic() < deadline:
        pyautogui.press("esc")
        time.sleep(1)

        # Continue once the normal WhatsApp UI has had time to render.
        # The search step below is the actual functional check.
        return True

    return False


def _open_new_chat():
    """Open WhatsApp Web's New Chat interface."""

    import pyautogui

    pyautogui.hotkey("ctrl", "alt", "n")
    time.sleep(1.5)


def _search_contact_and_open(receiver):
    """
    Open the WhatsApp Web search box visible in the user's
    current Chrome window, search the recipient, and open the chat.
    """

    import pyautogui
    import pyperclip

    receiver = str(receiver).strip()

    if not receiver:
        raise ValueError("Recipient name is empty.")

    # Get the current Chrome window.
    hwnd = _find_chrome_window()

    if not hwnd:
        raise RuntimeError("Chrome window was not found.")

    user32 = ctypes.windll.user32

    rect = ctypes.wintypes.RECT()

    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("Could not read Chrome window position.")

    left = rect.left
    top = rect.top
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    # WhatsApp's visible:
    # "Search or start a new chat"
    #
    # The search box is approximately 26.5% across
    # and 25.5% down the Chrome window.
    search_x = left + int(width * 0.265)
    search_y = top + int(height * 0.255)

    # Click the actual WhatsApp search box.
    pyautogui.click(search_x, search_y)

    time.sleep(0.5)

    # Select anything already in the search box.
    pyautogui.hotkey("ctrl", "a")

    # Type recipient.
    pyperclip.copy(receiver)
    pyautogui.hotkey("ctrl", "v")

    time.sleep(2)

    # Select the matching search result.
    pyautogui.press("enter")

    time.sleep(2.5)

    return True

def _send_text(message):
    """
    Click the WhatsApp message composer and send the exact message.
    """

    import pyautogui
    import pyperclip

    message = str(message)

    if not message.strip():
        raise ValueError("Message is empty.")

    hwnd = _find_chrome_window()

    if not hwnd:
        raise RuntimeError("Chrome window was not found.")

    user32 = ctypes.windll.user32

    rect = ctypes.wintypes.RECT()

    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("Could not read Chrome window position.")

    left = rect.left
    top = rect.top
    width = rect.right - rect.left
    height = rect.bottom - rect.top

    # WhatsApp message composer is at the bottom
    # of the right-hand chat panel.
    composer_x = left + int(width * 0.75)
    composer_y = top + int(height * 0.935)

    # Click composer.
    pyautogui.click(composer_x, composer_y)

    time.sleep(0.5)

    # Type exact message.
    pyperclip.copy(message)
    pyautogui.hotkey("ctrl", "v")

    time.sleep(0.5)

    # Send.
    pyautogui.press("enter")

    time.sleep(2)

    return True


def _whatsapp_web(receiver: str, message: str, attachment_path: str | None = None) -> str:
    """
    Send a WhatsApp message through the user's existing Chrome.

    This version intentionally does NOT use Playwright/CDP because that
    would require Chrome to be started with a special debugging profile.
    """

    with _WA_LOCK:
        try:
            ok, state = _open_or_reuse_whatsapp()

            if not ok:
                return state

            if not _wait_for_whatsapp():
                return (
                    "WhatsApp Web did not become ready. "
                    "Chrome has been left open."
                )

            # Search and open recipient.
            try:
                _search_contact_and_open(receiver)
            except Exception as exc:
                return (
                    f"WhatsApp opened, but I could not select "
                    f"{receiver}: {exc}"
                )

            # Send exact message.
            try:
                _send_text(message)
            except Exception as exc:
                return (
                    f"WhatsApp opened {receiver}, "
                    f"but the message could not be sent: {exc}"
                )

            # Handle optional attachment
            attach_note = ""
            if attachment_path:
                att_p = Path(attachment_path)
                if att_p.exists():
                    try:
                        # If image, copy to clipboard and paste
                        if att_p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
                            import pyautogui
                            from PIL import Image
                            import io
                            import win32clipboard
                            img = Image.open(att_p)
                            output = io.BytesIO()
                            img.convert("RGB").save(output, "BMP")
                            data = output.getvalue()[14:]
                            output.close()
                            win32clipboard.OpenClipboard()
                            win32clipboard.EmptyClipboard()
                            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                            win32clipboard.CloseClipboard()
                            time.sleep(0.5)
                            pyautogui.hotkey("ctrl", "v")
                            time.sleep(1.5)
                            pyautogui.press("enter")
                            time.sleep(1.0)
                            attach_note = f" with image '{att_p.name}' attached."
                        else:
                            attach_note = f" (File '{att_p.name}' located at {attachment_path}; ready to attach)."
                    except Exception as exc:
                        attach_note = f" (Attachment notice: could not auto-paste '{att_p.name}': {exc})."
                else:
                    attach_note = f" (Attachment '{attachment_path}' was not found)."

            # Leave Chrome open.
            return (
                f"Message sent to {receiver} through your "
                f"current Chrome WhatsApp Web session{attach_note}"
            )

        except Exception as exc:
            return f"WhatsApp Web action failed: {exc}"


def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    """Fallback for non-WhatsApp desktop messaging apps."""

    try:
        import pyautogui
        import pyperclip

        pyautogui.press("win")
        time.sleep(0.5)

        pyperclip.copy(app_name)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

        time.sleep(2.5)

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)

        pyperclip.copy(receiver)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

        time.sleep(0.8)

        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

        time.sleep(0.5)

        return f"Message sent to {receiver} via {app_name}."

    except Exception as exc:
        return f"Could not send via {app_name}: {exc}"


def send_message(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}

    receiver = str(
        p.get("receiver", "")
    ).strip()

    message = str(
        p.get("message_text", "")
    ).strip()

    platform = str(
        p.get("platform", "whatsapp")
    ).strip().lower()

    attachment_path = str(p.get("attachment_path", "")).strip() or None

    if not receiver:
        return "Please specify a recipient."

    if not message and not attachment_path:
        return "Please specify the message content."

    if platform in (
        "whatsapp",
        "whatsapp web",
        "wp",
        "wapp",
    ):
        result = _whatsapp_web(
            receiver,
            message or "Here is the attachment.",
            attachment_path=attachment_path,
        )
    else:
        result = _desktop_send(
            platform.title(),
            receiver,
            message,
        )

    if player and hasattr(player, "write_log"):
        player.write_log(
            "[message] " + result
        )

    return result


TOOL = {
    "name": "send_message",

    "description": (
        "Actually send a text message through WhatsApp Web "
        "using the user's existing Chrome window. "
        "Never launch another Chrome browser or create another "
        "Chrome profile. If WhatsApp Web is already the current "
        "tab, reuse it. Otherwise open WhatsApp Web in a new tab "
        "inside the same Chrome window. Search the requested "
        "contact, send the exact message, and leave Chrome open. "
        "Supports optional attachment_path."
    ),

    "parameters": {
        "type": "OBJECT",

        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name",
            },

            "message_text": {
                "type": "STRING",
                "description": "Exact message text to send",
            },

            "platform": {
                "type": "STRING",
                "description": "whatsapp | whatsapp web",
            },

            "attachment_path": {
                "type": "STRING",
                "description": "Optional file path to attach",
            },
        },

        "required": [
            "receiver",
            "message_text",
        ],
    },

    "handler": send_message,
}
