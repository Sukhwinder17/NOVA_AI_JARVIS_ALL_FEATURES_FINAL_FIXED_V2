from __future__ import annotations

import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any


@dataclass
class Task:
    task_type: str                   # "send_email", "send_whatsapp", "find_files", "browser_task", "general"
    goal: str
    recipient: Optional[str] = None
    account: Optional[str] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    needs_attachment: Optional[bool] = None
    attachment_path: Optional[str] = None
    search_query: Optional[str] = None
    search_results: list[str] = field(default_factory=list)
    stage: str = "INIT"             # Stage string, e.g. "ASK_ACCOUNT", "ASK_MESSAGE", "ASK_ATTACHMENT", "CONFIRM"
    requires_confirmation: bool = False
    confirmed: bool = False
    status: str = "active"          # "active", "waiting_input", "paused_login", "completed", "cancelled"
    prompt_for_user: str = ""
    created_at: float = field(default_factory=time.time)
    context_data: dict = field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status in ("active", "waiting_input", "paused_login")


class TaskManager:
    def __init__(self):
        self.current_task: Optional[Task] = None
        self.last_file_results: list[str] = []
        self.last_attachment: Optional[str] = None
        self.last_links: list[dict] = []
        self.pending_confirmation: Optional[dict] = None
        self.history_tasks: list[Task] = []

    def start_task(self, task_type: str, goal: str, **kwargs) -> Task:
        task = Task(task_type=task_type, goal=goal, **kwargs)
        # If user pre-selected an attachment via UI button, attach it
        if self.last_attachment and not task.attachment_path:
            task.attachment_path = self.last_attachment
            task.needs_attachment = True
        self.current_task = task
        return task

    def get_task(self) -> Optional[Task]:
        if self.current_task and self.current_task.is_active():
            return self.current_task
        return None

    def cancel_task(self) -> str:
        if self.current_task and self.current_task.is_active():
            task_type = self.current_task.task_type
            self.current_task.status = "cancelled"
            self.history_tasks.append(self.current_task)
            self.current_task = None
            self.pending_confirmation = None
            return f"I've cancelled the pending {task_type.replace('_', ' ')} task."
        if self.pending_confirmation:
            self.pending_confirmation = None
            return "Cancelled the pending action."
        return "There is no active task to cancel."

    def describe_current_task(self) -> str:
        task = self.get_task()
        if not task:
            if self.last_file_results:
                return (
                    f"No active multi-step task. However, I have {len(self.last_file_results)} "
                    f"file search results stored from our recent search. You can say 'open 1' or '3'."
                )
            return "We don't have any pending or active tasks right now. What would you like to do?"

        lines = [f"📋 Current task: {task.goal}"]
        lines.append(f"  • Task type: {task.task_type.replace('_', ' ').title()}")
        if task.recipient:
            lines.append(f"  • Recipient: {task.recipient}")
        if task.account:
            lines.append(f"  • Account: {task.account}")
        if task.subject:
            lines.append(f"  • Subject: {task.subject}")
        if task.message:
            preview = task.message if len(task.message) < 60 else task.message[:57] + "..."
            lines.append(f"  • Message: \"{preview}\"")
        if task.attachment_path:
            lines.append(f"  • Attachment: {Path(task.attachment_path).name} ({task.attachment_path})")
        
        lines.append(f"  • Status: {task.status.replace('_', ' ').title()}")
        if task.prompt_for_user:
            lines.append(f"\nNext step: {task.prompt_for_user}")
        return "\n".join(lines)

    def set_attachment(self, file_path: str) -> None:
        p = str(Path(file_path).resolve())
        self.last_attachment = p
        if self.current_task and self.current_task.is_active():
            self.current_task.attachment_path = p
            self.current_task.needs_attachment = True

    def set_links(self, links: list[dict]) -> None:
        self.last_links = [dict(x) for x in (links or []) if isinstance(x, dict) and x.get("url")]

    def resolve_link_ref(self, ref: str) -> Optional[dict]:
        if not self.last_links:
            return None
        m = re.search(r"\b(?:link|result|choice|number|#)?\s*(\d+)\b", str(ref).lower())
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(self.last_links):
                return self.last_links[idx]
        target = str(ref).lower().strip()
        for item in self.last_links:
            if target in str(item.get("name", "")).lower() or target in str(item.get("url", "")).lower():
                return item
        return None

    def set_file_results(self, results: list[str]) -> None:
        self.last_file_results = list(results)
        if self.current_task and self.current_task.is_active():
            self.current_task.search_results = list(results)

    def resolve_file_ref(self, ref: str) -> Optional[str]:
        """Resolves a reference like '3', 'file 3', 'DSA_Final.pdf' against recent search results."""
        if not self.last_file_results:
            return None

        clean_ref = str(ref).strip().lower()
        # Match 'file 3' or 'result 3' or '3'
        num_m = re.search(r"\b(?:file|result|choice|number|#)?\s*(\d+)\b", clean_ref)
        if num_m:
            idx = int(num_m.group(1)) - 1
            if 0 <= idx < len(self.last_file_results):
                return self.last_file_results[idx]

        # Match by filename substring
        clean_target = re.sub(r"^(?:file|open|attach)\s+", "", clean_ref).strip()
        for p in self.last_file_results:
            path_obj = Path(p)
            if clean_target in path_obj.name.lower() or clean_target in str(p).lower():
                return p
        return None

    def set_pending_confirmation(self, action_name: str, details: dict, callback: Callable) -> None:
        self.pending_confirmation = {
            "action_name": action_name,
            "details": details,
            "callback": callback,
            "created_at": time.time(),
        }

    def resolve_confirmation(self, confirmed: bool) -> tuple[str, bool]:
        if not self.pending_confirmation:
            return "There is nothing pending confirmation.", False

        item = self.pending_confirmation
        self.pending_confirmation = None

        if not confirmed:
            if self.current_task and self.current_task.is_active():
                self.current_task.status = "cancelled"
            return f"Cancelled '{item['action_name']}'. Nothing was sent or modified.", True

        try:
            cb = item["callback"]
            result = cb()
            if self.current_task and self.current_task.is_active():
                self.current_task.status = "completed"
                self.history_tasks.append(self.current_task)
                self.current_task = None
            return result, True
        except Exception as exc:
            return f"Action failed during execution: {exc}", True
