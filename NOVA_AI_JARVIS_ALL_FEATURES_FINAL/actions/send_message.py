from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from core import config

_WA_LOCK = threading.Lock()


async def _first_visible(locators, timeout_ms: int = 2500):
    """Return the first visible locator from a list of Playwright locators."""
    for locator in locators:
        try:
            item = locator.first
            await item.wait_for(state="visible", timeout=timeout_ms)
            return item
        except Exception:
            continue
    return None


async def _whatsapp_flow(receiver: str, message: str) -> str:
    """Attach to a NOVA-controlled Chrome via CDP and use a new WhatsApp tab."""
    import os
    import subprocess
    import time
    import urllib.error
    import urllib.request

    from playwright.async_api import async_playwright

    debug_port = int(os.getenv("NOVA_CHROME_DEBUG_PORT", "9222"))
    debug_url = f"http://127.0.0.1:{debug_port}"
    profile = Path(config.NOVA_BROWSER_PROFILE).expanduser()
    automation_profile = (Path(config.BASE_DIR) / "data" / "browser_profile").resolve()
    chrome_user_data = (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google" / "Chrome" / "User Data"
    )
    if profile.resolve() == automation_profile and chrome_user_data.exists():
        profile = chrome_user_data
    profile.mkdir(parents=True, exist_ok=True)

    def cdp_ready() -> bool:
        try:
            with urllib.request.urlopen(debug_url + "/json/version", timeout=1.5) as response:
                return response.status == 200
        except Exception:
            return False

    def chrome_running() -> bool:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                capture_output=True, text=True, timeout=5
            )
            return "chrome.exe" in result.stdout.lower()
        except Exception:
            return False

    async with async_playwright() as playwright:
        if not cdp_ready():
            # A regular Chrome instance cannot be remotely automated unless it
            # was started with a debugging port. Do not try to open the same
            # locked profile through launch_persistent_context (that causes the
            # "Opening in existing browser session" error).
            if chrome_running():
                return (
                    "Chrome is already open, but it was not started with NOVA's "
                    "remote-debugging port. Close every Chrome window and make "
                    "sure chrome.exe exits, then retry. NOVA will reopen your "
                    "same Chrome profile with remote debugging enabled. "
                    "Your existing WhatsApp login will be retained."
                )

            chrome_exe = Path(os.environ.get("PROGRAMFILES", r"C:\\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if not chrome_exe.exists():
                chrome_exe = Path(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if not chrome_exe.exists():
                return "Google Chrome executable was not found. Install Chrome or set its path for NOVA."

            args = [
                str(chrome_exe),
                f"--remote-debugging-port={debug_port}",
                f"--user-data-dir={profile}",
                "--profile-directory=Default",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                config.WHATSAPP_URL,
            ]
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = asyncio.get_running_loop().time() + 25
            while asyncio.get_running_loop().time() < deadline and not cdp_ready():
                await asyncio.sleep(0.5)
            if not cdp_ready():
                return (
                    "Chrome started, but its remote-debugging endpoint did not become ready. "
                    "Close Chrome and retry; no WhatsApp message was sent."
                )

        browser = await playwright.chromium.connect_over_cdp(debug_url)
        contexts = browser.contexts
        if not contexts:
            return "NOVA connected to Chrome, but no browser context was available. No message was sent."
        context = contexts[0]

        # Always create a new tab in the same Chrome window/session rather than
        # launching another Chrome process or stealing an unrelated tab.
        page = await context.new_page()
        try:
            await page.goto(config.WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)

            deadline = asyncio.get_running_loop().time() + 180
            search = None
            while asyncio.get_running_loop().time() < deadline:
                try:
                    current_url = page.url.lower()
                    body = (await page.locator("body").inner_text(timeout=3000)).lower()
                except Exception:
                    await asyncio.sleep(2)
                    continue

                if "web.whatsapp.com" not in current_url:
                    await page.goto(config.WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)
                    continue

                search = await _first_visible([
                    page.get_by_role("textbox", name="Search or start a new chat"),
                    page.locator('div[contenteditable="true"][data-tab="3"]'),
                    page.locator('div[contenteditable="true"][role="textbox"]'),
                    page.locator('input[placeholder*="Search"]'),
                ], timeout_ms=1000)
                if search is not None:
                    break

                if "scan the qr code" in body or "link with phone number" in body:
                    await asyncio.sleep(2)
                    continue
                await asyncio.sleep(2)
            else:
                return (
                    "WhatsApp Web is not logged in on the Chrome profile NOVA opened. "
                    "Scan the QR code in this new tab once, wait for chats to load, "
                    "then repeat your command. No message was sent."
                )

            await search.click()
            await search.fill(receiver)
            await asyncio.sleep(1.5)

            result = None
            candidates = page.locator('[role="listitem"], [data-testid*="cell-frame"], [role="option"]')
            try:
                count = await candidates.count()
            except Exception:
                count = 0

            wanted = receiver.casefold().strip()
            for index in range(min(count, 40)):
                candidate = candidates.nth(index)
                try:
                    if not await candidate.is_visible():
                        continue
                    label = (await candidate.inner_text(timeout=1000)).strip()
                    first_line = label.splitlines()[0].strip() if label else ""
                    if first_line.casefold() == wanted:
                        result = candidate
                        break
                except Exception:
                    continue

            if result is None:
                return f"I couldn't find an exact WhatsApp contact match for '{receiver}'. No message was sent."

            await result.click()
            await asyncio.sleep(1)
            header = await _first_visible([
                page.locator('header [title]'),
                page.locator('header [dir="auto"]'),
                page.locator('header'),
            ], timeout_ms=4000)
            if header is None:
                return f"I opened a possible chat for '{receiver}', but couldn't verify its header. No message was sent."

            header_text = (await header.inner_text(timeout=2000)).strip()
            header_title = (await header.get_attribute("title")) or ""
            if wanted not in (header_title + " " + header_text).casefold():
                return (
                    f"The opened chat does not clearly match '{receiver}' "
                    f"(header: '{header_text[:100]}'). No message was sent."
                )

            composer = await _first_visible([
                page.get_by_role("textbox", name="Type a message"),
                page.locator('footer [contenteditable="true"][role="textbox"]'),
                page.locator('footer [contenteditable="true"]'),
            ], timeout_ms=5000)
            if composer is None:
                return f"Chat with '{receiver}' is open, but the message box wasn't found. No message was sent."

            await composer.click()
            await composer.fill(message)
            send_button = await _first_visible([
                page.get_by_role("button", name="Send"),
                page.locator('button[aria-label="Send"]'),
                page.locator('[data-testid="send"]'),
            ], timeout_ms=2500)
            if send_button is not None:
                await send_button.click()
            else:
                await composer.press("Enter")

            try:
                await page.get_by_text(message, exact=True).last.wait_for(state="visible", timeout=10000)
            except Exception:
                return (
                    f"The send action was triggered for '{receiver}', but I couldn't "
                    "confirm the message in the conversation. Please check WhatsApp."
                )
            return f"WhatsApp message sent and visible in the chat with {receiver}."
        finally:
            # Keep the Chrome window and its tabs open for the user.
            pass


def _whatsapp_web(receiver: str, message: str, attachment_path: str | None = None) -> str:
    if attachment_path:
        return "WhatsApp file attachments are not handled by this verified text-message flow yet. No message was sent."
    with _WA_LOCK:
        try:
            return asyncio.run(_whatsapp_flow(receiver, message))
        except Exception as exc:
            return f"WhatsApp Web could not complete the task: {exc}"


def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    """Fallback for non-WhatsApp desktop messaging apps."""
    try:
        import pyautogui
        import pyperclip
        pyautogui.press("win")
        pyperclip.copy(app_name)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        pyautogui.sleep(2.5)
        pyautogui.hotkey("ctrl", "f")
        pyperclip.copy(receiver)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        pyautogui.sleep(0.8)
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        return f"Message send action completed for {receiver} via {app_name}."
    except Exception as exc:
        return f"Could not send via {app_name}: {exc}"


def send_message(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    receiver = str(p.get("receiver", "")).strip()
    message = str(p.get("message_text", "")).strip()
    platform = str(p.get("platform", "whatsapp")).strip().lower()
    attachment_path = str(p.get("attachment_path", "")).strip() or None

    if not receiver:
        return "Please specify a recipient."
    if not message and not attachment_path:
        return "Please specify the message content."

    if platform in ("whatsapp", "whatsapp web", "wp", "wapp"):
        result = _whatsapp_web(receiver, message, attachment_path)
    else:
        result = _desktop_send(platform.title(), receiver, message)

    if player and hasattr(player, "write_log"):
        player.write_log("[message] " + result)
    return result


TOOL = {
    "name": "send_message",
    "description": (
        "Send WhatsApp text messages using NOVA's persistent Chrome profile. "
        "Open WhatsApp Web if needed, wait for QR login, search for the exact "
        "contact, verify the chat header, then send and confirm the message. "
        "If the recipient cannot be verified, do not send. Supports message_text "
        "and receiver. Attachments are not supported by this verified flow."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {"type": "STRING", "description": "Exact WhatsApp contact name or number"},
            "message_text": {"type": "STRING", "description": "Exact message text to send"},
            "platform": {"type": "STRING", "description": "whatsapp | whatsapp web"},
            "attachment_path": {"type": "STRING", "description": "Optional attachment path (not supported by this flow)"},
        },
        "required": ["receiver", "message_text"],
    },
    "handler": send_message,
}
