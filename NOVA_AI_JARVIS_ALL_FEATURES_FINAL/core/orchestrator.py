from __future__ import annotations

import re
import threading

from .action_loader import discover_actions
from .plugin_loader import discover_plugins
from .llm_router import LLMRouter
from .task_state import TaskManager
from .task_planner import TaskPlanner
from . import config
from memory.memory_manager import load_memory, format_memory_for_prompt
from memory.conversation_history import load_history, append_message


class NovaOrchestrator:
    def __init__(self, ui=None):
        self.ui = ui
        self.registry = discover_actions(config.BASE_DIR / "actions", logger=self._log)
        try:
            self.plugins = discover_plugins(
                config.BASE_DIR / "plugins",
                core_tool_names=self.registry.names(),
                logger=self._log,
            )
        except Exception:
            self.plugins = None
        self.router = LLMRouter(self.registry)
        self.task_manager = TaskManager()
        self.planner = TaskPlanner(self)
        self.history = load_history(40)
        self._last_provider = ""
        self._lock = threading.Lock()
        self._last_files = False

    def set_attachment(self, file_path: str):
        self.task_manager.set_attachment(file_path)

    def _log(self, msg):
        print("[NOVA]", msg)
        if self.ui and hasattr(self.ui, "write_log"):
            self.ui.write_log(msg)

    def _run(self, name, args):
        return self.registry.run(
            name,
            args,
            {
                "player": self.ui,
                "speak": getattr(self.ui, "speak_text", None),
                "response": None,
                "session_memory": load_memory(),
                "task_manager": self.task_manager,
            },
        )

    @staticmethod
    def _clean_search_query(text: str) -> str:
        q = re.sub(
            r"\b(?:find|search|locate|look for|show me|search for|look up|google|web|internet|network)\b",
            " ", text, flags=re.I,
        )
        q = re.sub(
            r"\b(?:my|the|all|on my|in my|laptop|computer|pc|file|files|file name|filename|"
            r"document|documents|folder|folders|related to|related|named|name|online|on the web)\b",
            " ", q, flags=re.I,
        )
        return re.sub(r"\s+", " ", q).strip()

    def _direct(self, text: str):
        t = text.strip()
        low = t.lower()

        # Voice controls
        if low in ("listen", "start listening", "listen now"):
            return "__LISTEN__"
        if low in ("stop listening", "stop listen", "stop hearing"):
            return "__STOP_LISTEN__"
        if low in ("stop speaking", "be quiet", "shut up"):
            return "__STOP_SPEAKING__"

        # Diagnostics / feature health check
        if re.fullmatch(r"(?:check|test|diagnose|scan)\s+(?:nova\s+)?(?:features?|systems?|capabilities?)", low):
            return self._run("feature_diagnostics", {})

        # Email intelligence commands.
        if re.search(r"\b(?:check|show|scan|read|summarize|review)\b", low) and re.search(r"\b(?:email|emails|inbox|mail)\b", low):
            if re.search(r"\b(?:important|urgent|assignment|work)\b", low):
                return self._run("email_manager", {"action": "important"})
            if re.search(r"\b(?:deadline|deadlines|due)\b", low):
                return self._run("email_manager", {"action": "deadlines"})
            return self._run("email_manager", {"action": "summary", "limit": 30})

        if re.search(r"\b(?:connect|link|add)\b", low) and re.search(r"\b(?:email|gmail|outlook|yahoo|mail)\b", low):
            return self._run("email_manager", {"action": "connect"})

        if re.fullmatch(r"(?:email|mail)\s+(?:accounts?|connected)", low):
            return self._run("email_manager", {"action": "accounts"})

        # Natural Language Task Planning & Orchestration layer
        # Handle PC file searches before the task planner.
        if re.search(r"\b(?:find|search|locate|look for|show me)\b", low) and re.search(r"\b(?:file|files|pdf|project|document|folder|python|code|dataset|image|video|filename|file\s+name)\b", low):
            exact = re.search(r"\bmy\s+(.+?)\s+files?\b", t, re.I)
            q = exact.group(1).strip() if exact else self._clean_search_query(t)
            if not q:
                q = t
            result = self._run("everything_file_finder", {"action": "search", "query": q, "limit": 50})
            self._last_files = True
            return result

        planned = self.planner.handle_natural_input(t)
        if planned is not None:
            return planned[0]

        # WhatsApp message commands MUST be handled before generic open-app routing.
        patterns = [
            r"^open\s+whatsapp(?:\s+web)?\s+and\s+(?:say|send(?:\s+message)?)\s+(.+?)\s+to\s+(.+?)$",
            r"^whatsapp\s+(?:say|send(?:\s+message)?)\s+(.+?)\s+to\s+(.+?)$",
        ]
        for pattern in patterns:
            m = re.match(pattern, t, re.I)
            if m:
                message_text = m.group(1).strip(" \"'")
                receiver = m.group(2).strip(" \"'")
                return self._run("send_message", {
                    "receiver": receiver,
                    "message_text": message_text,
                    "platform": "whatsapp",
                })

        # "send message to NAME say MESSAGE"
        m = re.match(
            r"^(?:send\s+(?:a\s+)?message\s+to|message\s+)"
            r"(.+?)\s+(?:saying|say|that\s+says|:)\s*"
            r"[\"']?(.+?)[\"']?$", t, re.I,
        )
        if m:
            return self._run("send_message", {
                "receiver": m.group(1).strip(" \"'"),
                "message_text": m.group(2).strip(" \"'"),
                "platform": "whatsapp",
            })

        # "send MESSAGE to NAME"
        m = re.match(r"^send\s+(.+?)\s+to\s+(.+?)$", t, re.I)
        if m and len(m.group(1)) < 300:
            return self._run("send_message", {
                "receiver": m.group(2).strip(),
                "message_text": m.group(1).strip(),
                "platform": "whatsapp",
            })

        # Explicit websites
        if re.fullmatch(r"(?:open|go to|start|launch)\s+(?:youtube|yt)", low):
            return self._run("browser_control", {
                "action": "go_to", "browser": "chrome", "url": "https://www.youtube.com/"
            })

        if re.fullmatch(r"(?:open|go to|start|launch)\s+whatsapp(?:\s+web)?", low):
            return self._run("browser_control", {
                "action": "go_to", "browser": "chrome", "url": config.WHATSAPP_URL
            })

        if re.fullmatch(r"(?:open|go to|start|launch)\s+datalens", low):
            return self._run("open_datalens", {})

        # Explicit web/network search. This avoids making the LLM merely explain
        # how to search the internet.
        if re.search(r"\b(?:search|look up|find)\b", low) and re.search(
            r"\b(?:web|internet|online|network|google|latest|news)\b", low
        ):
            q = self._clean_search_query(t)
            return self._run("web_search", {"query": q or t, "mode": "search"})

        # Generic application launch. Keep this BEFORE file-result opening.
        m = re.match(
            r"^(?:open|launch|start|run|go to)\s+(.+?)"
            r"(?:\s+in\s+(?:my|the)\s+(?:laptop|computer|pc|system))?$",
            t, re.I,
        )
        if m:
            app_name = m.group(1).strip()
            if app_name and not app_name.isdigit():
                return self._run("open_app", {"app_name": app_name})

        # Whole-PC Everything search.
        if re.search(r"\b(?:find|search|locate|look for|show me)\b", low) and re.search(
            r"\b(?:file|files|pdf|project|document|folder|python|code|dataset|image|video|filename|file\s+name)\b",
            low,
        ):
            # For natural commands like "find my gradient descent files",
            # Everything must receive only the filename phrase between "my" and "files".
            exact = re.search(r"\bmy\s+(.+?)\s+files?\b", t, re.I)
            if exact:
                q = exact.group(1).strip()
            else:
                q = self._clean_search_query(t)
            if not q:
                q = t
            result = self._run("everything_file_finder", {
                "action": "search", "query": q, "limit": 50
            })
            self._last_files = True
            return result

        # Open a previous Everything result by number/name.
        m = re.match(r"^open\s+(\d+|.+)$", t, re.I)
        if m:
            ref = m.group(1).strip()
            # Open directly from NOVA's stored search results first. This avoids
            # relying on Everything's internal module cache between messages.
            resolved = self.task_manager.resolve_file_ref(ref)
            if resolved:
                try:
                    import os
                    os.startfile(resolved)
                    return f"Opened: {resolved}"
                except Exception as exc:
                    return f"Could not open {resolved}: {exc}"
            if ref.isdigit() or self._last_files:
                return self._run("everything_file_finder", {
                    "action": "open", "ref": ref
                })

        return None

    def handle(self, text: str, provider: str | None = None):
        text = str(text or "").strip()
        if not text:
            return "", "local"

        direct = self._direct(text)
        if direct is not None:
            if direct == "__LISTEN__":
                reply, used = "Listening.", "local"
            elif direct == "__STOP_LISTEN__":
                reply, used = "Stopped listening.", "local"
            elif direct == "__STOP_SPEAKING__":
                reply, used = "Stopped speaking.", "local"
            else:
                reply, used = str(direct), "local"
            self.history.extend([
                {"role": "user", "content": text},
                {"role": "assistant", "content": reply},
            ])
            self.history = self.history[-40:]
            append_message("user", text)
            append_message("assistant", reply)
            return reply, used

        memory = load_memory()
        reply, used = self.router.run(
            text,
            self.history,
            {"memory": format_memory_for_prompt(memory)},
            provider,
        )
        self._last_provider = used
        self.history.extend([
            {"role": "user", "content": text},
            {"role": "assistant", "content": reply},
        ])
        self.history = self.history[-40:]
        append_message("user", text)
        append_message("assistant", reply)
        return reply, used
