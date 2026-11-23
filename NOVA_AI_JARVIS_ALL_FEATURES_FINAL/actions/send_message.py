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
    """Use a persistent Chrome profile and WhatsApp Web's accessible DOM."""
    from playwright.async_api import async_playwright

    profile = Path(config.NOVA_BROWSER_PROFILE).expanduser()
    profile.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        # This is NOVA's persistent Chrome profile. WhatsApp login is retained
        # here between runs; it does not take over or close the user's other
        # Chrome windows.
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=["--start-maximized", "--disable-notifications"],
        )
        try:
            pages = context.pages
            page = pages[0] if pages else await context.new_page()
            whatsapp_pages = [p for p in pages if "web.whatsapp.com" in p.url]
            if whatsapp_pages:
                page = whatsapp_pages[0]
            else:
                await page.goto(config.WHATSAPP_URL, wait_until="domcontentloaded", timeout=60000)

            # Detect login using WhatsApp's actual page UI, not a fixed sleep.
            deadline = asyncio.get_running_loop().time() + 180
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

                login_visible = (
                    "scan the qr code" in body
                    or "link with phone number" in body
                    or await page.locator('canvas[aria-label*="Scan"], [data-ref]').count() > 0
                )
                search = await _first_visible([
                    page.get_by_role("textbox", name="Search or start a new chat"),
                    page.locator('div[contenteditable="true"][data-tab="3"]'),
                    page.locator('div[contenteditable="true"][role="textbox"]'),
                    page.locator('input[placeholder*="Search"]'),
                ], timeout_ms=1000)

                if search is not None:
                    break
                if login_visible:
                    await asyncio.sleep(2)
                    continue
                await asyncio.sleep(2)
            else:
                return (
                    "WhatsApp Web is still not logged in or its chat list did not load. "
                    "Scan the QR code in the NOVA Chrome window, then ask me to send again."
                )

            # Search by the exact contact name/number.
            await search.click()
            await search.fill(receiver)
            await asyncio.sleep(1.5)

            # Find an exact visible result; do not press Enter on an arbitrary
            # first result. WhatsApp's result rows commonly expose title/text.
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
                # Some WhatsApp versions render search hits as buttons.
                buttons = page.get_by_role("button")
                try:
                    count = await buttons.count()
                except Exception:
                    count = 0
                for index in range(min(count, 60)):
                    candidate = buttons.nth(index)
                    try:
                        if await candidate.is_visible():
                            label = (await candidate.inner_text(timeout=700)).strip()
                            if label.splitlines() and label.splitlines()[0].strip().casefold() == wanted:
                                result = candidate
                                break
                    except Exception:
                        continue

            if result is None:
                return f"I couldn't find an exact WhatsApp contact match for '{receiver}'. No message was sent."

            await result.click()
            await asyncio.sleep(1)

            # Verify the chat header before sending.
            header = await _first_visible([
                page.locator('header [title]'),
                page.locator('header [dir="auto"]'),
                page.locator('header'),
            ], timeout_ms=4000)
            if header is None:
                return f"I opened a possible chat for '{receiver}', but couldn't verify its header. No message was sent."

            header_text = (await header.inner_text(timeout=2000)).strip()
            header_title = (await header.get_attribute("title")) or ""
            verified_text = (header_title + " " + header_text).casefold()
            if wanted not in verified_text:
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

            # Send using WhatsApp's Send button where available.
            send_button = await _first_visible([
                page.get_by_role("button", name="Send"),
                page.locator('button[aria-label="Send"]'),
                page.locator('[data-testid="send"]'),
            ], timeout_ms=2500)
            if send_button is not None:
                await send_button.click()
            else:
                await composer.press("Enter")

            # Confirm the exact message appears in the conversation.
            try:
                await page.get_by_text(message, exact=True).last.wait_for(state="visible", timeout=10000)
            except Exception:
                return (
                    f"The send action was triggered for '{receiver}', but I couldn't "
                    "confirm the message in the conversation. Please check WhatsApp."
                )
            return f"WhatsApp message sent and visible in the chat with {receiver}."
        finally:
            # The persistent context is intentionally left to Playwright's
            # lifecycle management; this finally block is retained for cleanup
            # hooks if the browser flow is extended later.
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
