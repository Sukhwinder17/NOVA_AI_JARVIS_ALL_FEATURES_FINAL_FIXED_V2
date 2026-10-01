from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple, Any

from .task_state import Task, TaskManager
from . import email_flow
from . import config
from tools.everything_file_finder import search, open_result

# Web apps and common URLs to avoid sending them to open_app
WEB_SERVICES = {
    "google colab": "https://colab.research.google.com/",
    "colab": "https://colab.research.google.com/",
    "youtube": "https://www.youtube.com/",
    "yt": "https://www.youtube.com/",
    "gmail": "https://mail.google.com/",
    "google mail": "https://mail.google.com/",
    "email": "https://mail.google.com/",
    "my email": "https://mail.google.com/",
    "whatsapp": config.WHATSAPP_URL,
    "whatsapp web": config.WHATSAPP_URL,
    "datalens": config.DATALENS_URL,
    "google": "https://www.google.com/",
    "google search": "https://www.google.com/",
    "github": "https://github.com/",
    "chatgpt": "https://chatgpt.com/",
    "claude": "https://claude.ai/",
    "reddit": "https://www.reddit.com/",
    "twitter": "https://twitter.com/",
    "x": "https://x.com/",
    "linkedin": "https://www.linkedin.com/",
    "kaggle": "https://www.kaggle.com/",
    "leetcode": "https://leetcode.com/",
    "huggingface": "https://huggingface.co/",
    "overleaf": "https://www.overleaf.com/",
}


def _extract_target_and_browser(text: str) -> Tuple[str, str]:
    """
    Extracts service name/URL and target browser from commands like:
    'open google colab in chrome' -> ('google colab', 'chrome')
    'launch colab' -> ('colab', 'chrome')
    """
    t = text.strip()
    browser = "chrome"
    m = re.search(r"\b(?:in|on|using|with)\s+(chrome|edge|firefox|brave|opera|operagx|vivaldi|browser)\b", t, re.I)
    if m:
        b_name = m.group(1).lower()
        browser = "chrome" if b_name == "browser" else b_name
        t = re.sub(r"\b(?:in|on|using|with)\s+(?:chrome|edge|firefox|brave|opera|operagx|vivaldi|browser)\b", "", t, flags=re.I).strip()

    t = re.sub(r"^(?:open|launch|start|go to|navigate to)\s+", "", t, flags=re.I).strip()
    return t, browser


def run_attachment_search(query: str, task: Optional[Task], task_manager: TaskManager) -> str:
    """Searches the whole PC with Everything and formats numbered results."""
    clean_q = re.sub(r"\b(?:find|search|locate|look for|attach|my|the|all|pdf|file|files|document|documents)\b", " ", query, flags=re.I)
    clean_q = re.sub(r"\s+", " ", clean_q).strip()
    if not clean_q:
        clean_q = query.strip()

    rows, _ = search(clean_q, limit=20)
    if not rows and query != clean_q:
        rows, _ = search(query, limit=20)

    if not rows:
        return f"I searched the entire PC with Everything for '{clean_q}', but no matching files were found. Please check the filename or provide a path."

    task_manager.set_file_results(rows)
    lines = [f"Found {len(rows)} matching file(s) for '{clean_q}':"]
    for i, path_str in enumerate(rows[:8], 1):
        name = Path(path_str).name
        lines.append(f"  {i}. {name} ({path_str})")

    if len(rows) > 8:
        lines.append(f"  ...and {len(rows) - 8} more.")

    lines.append("\nPlease choose which file (e.g. reply '1', '2', or the filename).")
    return "\n".join(lines)


def format_email_confirmation(task: Task, task_manager: TaskManager) -> str:
    task.stage = "CONFIRM_SEND"
    task.status = "waiting_input"
    task.prompt_for_user = "Please confirm whether to send this email (Yes/Cancel)."

    att_label = Path(task.attachment_path).name if task.attachment_path else "None"
    lines = [
        "📧 Email Details Ready:",
        f"  • To: {task.recipient}",
        f"  • Account: {task.account or 'Personal Gmail'}",
        f"  • Subject: {task.subject or 'Assignment'}",
        f"  • Message: {task.message or '(No message body)'}",
        f"  • Attachment: {att_label}",
        "",
        "Would you like me to send this email now? (Reply 'Yes' or 'Send' to proceed, or 'Cancel' to abort)"
    ]
    return "\n".join(lines)


def execute_send_email(task: Task, orchestrator: Any) -> str:
    # 1. Open Gmail Compose with details
    ok, comp_msg = email_flow.compose_email_in_gmail(
        recipient=task.recipient or "",
        subject=task.subject or "Message from NOVA",
        body=task.message or "",
        account_label=task.account or "0",
        attachment_path=task.attachment_path
    )
    if not ok:
        return f"Failed to compose email: {comp_msg}"

    # 2. Trigger send in Gmail
    sent_ok, send_msg = email_flow.send_current_email_in_browser()
    att_str = f" with '{Path(task.attachment_path).name}' attached" if task.attachment_path else ""

    if sent_ok:
        task.status = "completed"
        return f"✅ Email sent successfully to {task.recipient}{att_str} via Gmail."
    else:
        return f"I opened Gmail compose and populated the details for {task.recipient}{att_str}, but automatic dispatch reported: {send_msg}. You can click 'Send' in the active Gmail window."


def format_whatsapp_confirmation(task: Task, task_manager: TaskManager, orchestrator: Any) -> str:
    task.stage = "CONFIRM_SEND"
    task.status = "waiting_input"
    att_label = Path(task.attachment_path).name if task.attachment_path else "None"
    lines = [
        "💬 WhatsApp Message Ready:",
        f"  • To: {task.recipient}",
        f"  • Message: \"{task.message}\"",
        f"  • Attachment: {att_label}",
        "",
        "Send this WhatsApp message now? (Reply 'Yes' or 'Send' to confirm, or 'Cancel' to abort)"
    ]
    return "\n".join(lines)


def execute_send_whatsapp(task: Task, orchestrator: Any) -> str:
    result = orchestrator._run("send_message", {
        "receiver": task.recipient or "",
        "message_text": task.message or "",
        "platform": "whatsapp",
        "attachment_path": task.attachment_path or ""
    })
    task.status = "completed"
    return result


class TaskPlanner:
    def __init__(self, orchestrator: Any):
        self.orchestrator = orchestrator
        self.task_manager = orchestrator.task_manager

    def handle_natural_input(self, text: str, provider: Optional[str] = None) -> Optional[Tuple[str, str]]:
        t = text.strip()
        low = t.lower()

        # ----------------------------------------------------
        # 1. SPECIAL COMMANDS & TASK CONTROL
        # ----------------------------------------------------
        if low in ("cancel", "abort", "stop task", "never mind", "cancel task", "stop this"):
            return self.task_manager.cancel_task(), "local"

        if low in ("what were we doing?", "what are we doing?", "what was the task?", "status", "current task", "what's the task?"):
            return self.task_manager.describe_current_task(), "local"

        # ----------------------------------------------------
        # 2. CONFIRMATION RESPONSES (YES / NO / CONFIRM)
        # ----------------------------------------------------
        is_yes = low in ("yes", "confirm", "send", "send it", "do it", "sure", "proceed", "yep", "ok", "okay", "yeah", "send now")
        is_no = low in ("no", "cancel", "don't send", "stop", "abort", "never mind", "nope")

        # Check pending confirmation object
        if self.task_manager.pending_confirmation:
            if is_yes:
                res, _ = self.task_manager.resolve_confirmation(True)
                return res, "local"
            elif is_no:
                res, _ = self.task_manager.resolve_confirmation(False)
                return res, "local"

        # ----------------------------------------------------
        # 3. ADVANCE ACTIVE TASK IN MULTI-TURN CONVERSATION
        # ----------------------------------------------------
        task = self.task_manager.get_task()
        if task:
            # Paused for login
            if task.status == "paused_login":
                if any(w in low for w in ("ready", "signed in", "logged in", "done", "continue", "yes")):
                    is_logged, status_msg = email_flow.check_gmail_status()
                    task.status = "active"
                    if task.task_type == "send_email":
                        task.stage = "ASK_ACCOUNT"
                        return "Great! Gmail is ready. Which email account should I send it from?", "local"

            # Active Email Task progression
            if task.task_type == "send_email":
                if task.stage == "CONFIRM_SEND":
                    if is_yes:
                        return execute_send_email(task, self.orchestrator), "local"
                    elif is_no:
                        return self.task_manager.cancel_task(), "local"

                if task.stage == "ASK_ACCOUNT":
                    task.account = t
                    # Open Gmail
                    email_flow.open_gmail_in_chrome(task.account)
                    if not task.message:
                        task.stage = "ASK_MESSAGE"
                        task.prompt_for_user = "What would you like the message to say?"
                        return "What would you like the message to say?", "local"
                    elif task.needs_attachment is None and not task.attachment_path:
                        task.stage = "ASK_ATTACHMENT"
                        task.prompt_for_user = "Do you want to attach a file?"
                        return "Do you want to attach a file?", "local"
                    else:
                        return format_email_confirmation(task, self.task_manager), "local"

                if task.stage == "ASK_MESSAGE":
                    if any(w in low for w in ("generate a message", "draft a message", "write a message", "create a message", "draft it", "generate it")):
                        sub = "Assignment Submission" if "assignment" in task.goal.lower() else "Important Update"
                        task.subject = sub
                        task.message = f"Hi {task.recipient},\n\nI hope this email finds you well. I am sharing the requested materials and details with you. Please review the attached document when you have a moment.\n\nBest regards,\nNOVA AI"
                    else:
                        cleaned = re.sub(r"^(?:tell\s+him|tell\s+her|tell\s+them|say|saying|that)\s+", "", t, flags=re.I).strip(" \"'")
                        task.message = f"Hi {task.recipient},\n\n{cleaned}\n\nPlease let me know if you need anything else.\n\nBest regards."
                        if not task.subject:
                            task.subject = "Assignment" if "assignment" in (t + task.goal).lower() else "Message from NOVA"

                    if task.attachment_path:
                        return format_email_confirmation(task, self.task_manager), "local"
                    else:
                        task.stage = "ASK_ATTACHMENT"
                        task.prompt_for_user = "Do you want to attach a file?"
                        return "Do you want to attach a file?", "local"

                if task.stage == "ASK_ATTACHMENT":
                    if low in ("no", "none", "no attachment", "don't attach", "skip", "nope"):
                        task.needs_attachment = False
                        return format_email_confirmation(task, self.task_manager), "local"
                    elif any(w in low for w in ("yes", "attach", "pdf", "file", "document", "notes", "assignment")):
                        # Search for file
                        q = re.sub(r"\b(?:yes|please|attach|my|the|file|document|named)\b", " ", t, flags=re.I).strip()
                        if not q:
                            # check goal
                            m_file = re.search(r"attach\s+(?:the|my)?\s*([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\s+send|$)", task.goal, re.I)
                            q = m_file.group(1).strip() if m_file else "PDF"
                        task.search_query = q
                        task.stage = "SELECT_ATTACHMENT"
                        task.needs_attachment = True
                        return run_attachment_search(q, task, self.task_manager), "local"

                if task.stage == "SELECT_ATTACHMENT":
                    resolved = self.task_manager.resolve_file_ref(t)
                    if resolved:
                        task.attachment_path = resolved
                        return f"Selected '{Path(resolved).name}'.\n\n" + format_email_confirmation(task, self.task_manager), "local"
                    else:
                        return f"I couldn't identify which file you meant by '{t}'. Please answer with a number (1-{len(task.search_results)}) or the exact filename.", "local"

            # Active WhatsApp Task progression
            if task.task_type == "send_whatsapp":
                if task.stage == "CONFIRM_SEND":
                    if is_yes:
                        return execute_send_whatsapp(task, self.orchestrator), "local"
                    elif is_no:
                        return self.task_manager.cancel_task(), "local"

                if task.stage == "ASK_MESSAGE":
                    task.message = t
                    return format_whatsapp_confirmation(task, self.task_manager, self.orchestrator), "local"

                if task.stage == "SELECT_ATTACHMENT":
                    resolved = self.task_manager.resolve_file_ref(t)
                    if resolved:
                        task.attachment_path = resolved
                        return format_whatsapp_confirmation(task, self.task_manager, self.orchestrator), "local"

        # ----------------------------------------------------
        # 4. NUMBERED LEARNING LINKS ("open link 2")
        # ----------------------------------------------------
        m_link = re.fullmatch(r"(?:open|go to|launch)\\s+(?:link|resource|website)\\s+(\\d+)", low)
        if m_link:
            item = self.task_manager.resolve_link_ref(m_link.group(1))
            if item:
                url = item.get("url", "")
                try:
                    import webbrowser
                    webbrowser.open(url)
                    return f"Opened link {m_link.group(1)}: {item.get('name', url)}", "local"
                except Exception as exc:
                    return f"I found the link but could not open it: {exc}", "local"
            return "I don't have a numbered learning link with that number yet. Ask me for learning resources first.", "local"

        # Also accept just "2" immediately after a learning-resource list.
        if low.isdigit() and self.task_manager.last_links:
            item = self.task_manager.resolve_link_ref(low)
            if item:
                url = item.get("url", "")
                try:
                    import webbrowser
                    webbrowser.open(url)
                    return f"Opened link {low}: {item.get('name', url)}", "local"
                except Exception as exc:
                    return f"I found the link but could not open it: {exc}", "local"

        # ----------------------------------------------------
        # 5. STANDALONE FILE SELECTION (E.G. USER SAYS "3" OR "FILE 3")
        # ----------------------------------------------------
        m_num = re.fullmatch(r"(?:open\s+|file\s+|result\s+|#\s*)?(\d+)", low)
        if m_num or (low.isdigit() and len(low) <= 3):
            resolved = self.task_manager.resolve_file_ref(t)
            if resolved:
                try:
                    os.startfile(resolved)
                    return f"Opened: {resolved}", "local"
                except Exception as exc:
                    return f"Could not open {resolved}: {exc}", "local"
            elif self.orchestrator._last_files:
                # Fallback to existing everything_file_finder action
                return self.orchestrator._run("everything_file_finder", {"action": "open", "ref": t}), "local"

        # ----------------------------------------------------
        # 5. LEARNING REQUESTS ("I want to learn DSA", etc.)
        # ----------------------------------------------------
        if re.search(r"\b(?:i\s+want\s+to\s+learn|learn|learning|guide\s+(?:for|to)|study|how\s+to\s+start|channels?\s+for)\b", low):
            # Check if this is a learning request for a topic
            m_learn = re.search(
                r"(?:i\s+want\s+to\s+learn|how\s+to\s+learn|guide\s+for|channels?\s+for|resources?\s+for)\s+(.+)$",
                low
            )
            topic = m_learn.group(1).strip() if m_learn else ""
            if not topic:
                for kw in ("dsa", "python", "machine learning", "web development", "sql", "deep learning", "algorithms"):
                    if kw in low:
                        topic = kw
                        break
            if topic:
                topic = re.sub(r"\b(?:give\s+me|youtube|channels?|resources?|roadmap|tutorials?)\b", "", topic).strip()
                res = self.orchestrator._run("learning_resources", {"topic": topic or "DSA", "open_in_browser": False})
                urls = []
                seen = set()
                for url in re.findall(r"https?://\\S+", str(res)):
                    url = url.rstrip(").,;")
                    if url not in seen:
                        seen.add(url)
                        urls.append(url)
                self.task_manager.set_links([
                    {"name": f"Learning resource {i}", "url": url}
                    for i, url in enumerate(urls, 1)
                ])
                return res, "local"

        # ----------------------------------------------------
        # 6. ATTACHMENT SELECTION COMMANDS ("attach my DSA PDF")
        # ----------------------------------------------------
        if re.search(r"\b(?:attach\s+(?:my\s+|the\s+)?|find\s+(?:and\s+attach))\b", low) and not re.search(r"\b(?:send|email|whatsapp)\b", low):
            q = re.sub(r"^(?:attach|find\s+and\s+attach)\s+(?:my\s+|the\s+)?", "", t, flags=re.I).strip()
            return run_attachment_search(q or "PDF", None, self.task_manager), "local"

        # ----------------------------------------------------
        # 7. EMAIL COMMANDS & WORKFLOWS
        # ----------------------------------------------------
        # Matches: "open email and send a message to Rahul", "send Rahul an email...", "open Gmail, send Rahul the assignment..."
        if re.search(r"\b(?:email|gmail)\b", low) and re.search(r"\b(?:send|message|compose|write)\b", low):
            recipient = ""
            m_rec = re.search(r"\b(?:to|message\s+to|send)\s+([A-Z][a-zA-Z0-9_\s]{1,30}?)(?:\s+(?:saying|say|the|with|and|that|about|$)|$)", t)
            if m_rec:
                recipient = m_rec.group(1).strip()
            if not recipient:
                # Try generic extraction
                m_rec = re.search(r"\b(?:to)\s+([a-zA-Z0-9_\.\@\s]{2,35}?)(?:\s+(?:saying|say|the|with|and|that|about|$)|$)", t, re.I)
                if m_rec:
                    recipient = m_rec.group(1).strip()

            # Check if attachment is mentioned in prompt
            att_query = ""
            m_att = re.search(r"\b(?:attach|with)\s+(?:the\s+|my\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\s+send|$)", t, re.I)
            if m_att:
                att_query = m_att.group(1).strip()

            # Check message in prompt
            message_text = ""
            m_msg = re.search(r"\b(?:saying|say|that\s+says|message\s+as)\s+[\"']?(.+?)[\"']?$", t, re.I)
            if m_msg:
                message_text = m_msg.group(1).strip()

            task = self.task_manager.start_task(
                task_type="send_email",
                goal=t,
                recipient=recipient or "Recipient",
                message=message_text or None,
            )

            # Check login & open Gmail
            email_flow.open_gmail_in_chrome()
            is_logged, status_reason = email_flow.check_gmail_status()
            if status_reason == "login_required":
                task.status = "paused_login"
                return "I opened Gmail in Chrome, but you aren't signed in. Please sign in to your Google account in Chrome and tell me when you're ready.", "local"

            if not task.account:
                task.stage = "ASK_ACCOUNT"
                task.prompt_for_user = "Which email account should I send it from?"
                return "I've opened Gmail in Chrome. Which email account should I send it from?", "local"

        # ----------------------------------------------------
        # 8. WHATSAPP NATURAL LANGUAGE COMMANDS
        # ----------------------------------------------------
        if re.search(r"\b(?:whatsapp|wp)\b", low):
            # "open WhatsApp and send hi to Sukhwinder Singh"
            # "send Rahul a WhatsApp saying hi"
            # "send Rahul hi on WhatsApp"
            # "tell Rahul on WhatsApp that I'm coming"
            # "send this PDF to Rahul on WhatsApp"
            recipient = ""
            message = ""
            att_path = self.task_manager.last_attachment

            # "send NAME a WhatsApp saying/say MESSAGE"
            m = re.search(r"send\s+([a-zA-Z0-9_\s]+?)\s+(?:a\s+)?whatsapp\s+(?:saying|say|that\s+says|:)\s*(.+)$", t, re.I)
            if m:
                recipient = m.group(1).strip()
                message = m.group(2).strip(" \"'")

            # "tell NAME on WhatsApp that MESSAGE"
            if not recipient:
                m = re.search(r"tell\s+([a-zA-Z0-9_\s]+?)\s+on\s+whatsapp\s+(?:that\s+|to\s+|:)?\s*(.+)$", t, re.I)
                if m:
                    recipient = m.group(1).strip()
                    message = m.group(2).strip(" \"'")

            # "send NAME MESSAGE on WhatsApp"
            if not recipient:
                m = re.search(r"send\s+([a-zA-Z0-9_\s]+?)\s+(.+?)\s+on\s+whatsapp$", t, re.I)
                if m:
                    recipient = m.group(1).strip()
                    message = m.group(2).strip(" \"'")

            # "open whatsapp and send MESSAGE to NAME"
            if not recipient:
                m = re.search(r"open\s+whatsapp(?:\s+web)?\s+and\s+(?:say|send(?:\s+message)?)\s+(.+?)\s+to\s+(.+?)$", t, re.I)
                if m:
                    message = m.group(1).strip(" \"'")
                    recipient = m.group(2).strip(" \"'")

            # "send this PDF to NAME on WhatsApp"
            if not recipient:
                m = re.search(r"send\s+(?:this\s+)?(file|pdf|document)\s+to\s+([a-zA-Z0-9_\s]+?)(?:\s+on\s+whatsapp|$)", t, re.I)
                if m:
                    recipient = m.group(2).strip()
                    message = "Here is the document."

            if recipient:
                # If recipient extracted, check if message is present
                if not message:
                    task = self.task_manager.start_task(
                        task_type="send_whatsapp",
                        goal=t,
                        recipient=recipient,
                        attachment_path=att_path
                    )
                    task.stage = "ASK_MESSAGE"
                    return f"What would you like me to say to {recipient} on WhatsApp?", "local"

                # Execute WhatsApp send with existing action
                result = self.orchestrator._run("send_message", {
                    "receiver": recipient,
                    "message_text": message,
                    "platform": "whatsapp",
                    "attachment_path": att_path or ""
                })
                return result, "local"

        # ----------------------------------------------------
        # 9. BROWSER NAVIGATION & WEB SERVICES
        # ----------------------------------------------------
        # Handles "open google colab in chrome", "open youtube", "open colab in my browser", etc.
        target_raw, browser_target = _extract_target_and_browser(t)
        target_key = target_raw.lower().strip()

        # Check known web services
        if target_key in WEB_SERVICES:
            url = WEB_SERVICES[target_key]
            if target_key == "datalens":
                return self.orchestrator._run("open_datalens", {}), "local"
            return self.orchestrator._run("browser_control", {
                "action": "go_to",
                "browser": browser_target,
                "url": url
            }), "local"

        # Check if URL-like (ends in domain or contains http)
        if any(target_key.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".app", ".ai", ".edu", ".gov")) or "://" in target_key:
            return self.orchestrator._run("browser_control", {
                "action": "go_to",
                "browser": browser_target,
                "url": target_raw
            }), "local"

        # ----------------------------------------------------
        # 10. EVERYTHING FILE SEARCH ("find my DSA PDF", etc.)
        # ----------------------------------------------------
        if re.search(r"\b(?:find|search|locate|look for|show me)\b", low) and re.search(
            r"\b(?:file|files|pdf|project|document|folder|python|code|dataset|image|video|filename|file\s+name)\b",
            low,
        ):
            # Check if this is a combo intent: "find my DSA PDF and send it to Rahul"
            m_combo = re.search(r"find\s+(?:my\s+|the\s+)?(.+?)\s+and\s+send\s+(?:it\s+)?to\s+([a-zA-Z0-9_\s]+)", t, re.I)
            if m_combo:
                file_target = m_combo.group(1).strip()
                recipient = m_combo.group(2).strip()
                # Start task to send after selection
                task = self.task_manager.start_task(
                    task_type="send_email" if "email" in low else "send_whatsapp",
                    goal=t,
                    recipient=recipient,
                    stage="SELECT_ATTACHMENT",
                    status="waiting_input"
                )
                search_res = run_attachment_search(file_target, task, self.task_manager)
                return f"I've initiated the request to send the file to {recipient}.\n\n{search_res}", "local"

            # Plain file search
            q = self.orchestrator._clean_search_query(t) or t
            res = self.orchestrator._run("everything_file_finder", {"action": "search", "query": q, "limit": 40})
            self.orchestrator._last_files = True
            # Cache rows in task manager as well
            rows, _ = search(q, limit=40)
            self.task_manager.set_file_results(rows)
            return res, "local"

        return None
