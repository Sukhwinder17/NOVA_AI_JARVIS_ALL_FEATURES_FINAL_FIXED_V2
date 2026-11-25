import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from chat_fusion_dialog import _load_export, _parse_conversation


def sample_chat(title, cid, timestamp, role, text):
    return {
        "title": title,
        "id": cid,
        "mapping": {
            "node": {
                "message": {
                    "author": {"role": role},
                    "create_time": timestamp,
                    "content": {"content_type": "text", "parts": [text]},
                }
            }
        },
    }


class ChatFusionParserTests(unittest.TestCase):
    def test_parse_extracts_user_and_assistant_messages(self):
        data = sample_chat("Python Chat", "c1", 1700000000, "user", "Explain classes")
        parsed = _parse_conversation(data)
        self.assertEqual(parsed["title"], "Python Chat")
        self.assertEqual(len(parsed["messages"]), 1)
        self.assertEqual(parsed["messages"][0]["role"], "user")
        self.assertEqual(parsed["messages"][0]["text"], "Explain classes")

    def test_skips_non_conversation_and_empty_messages(self):
        self.assertIsNone(_parse_conversation({"title": "No mapping"}))
        empty = {"title": "Empty", "mapping": {"n": {"message": {
            "author": {"role": "system"}, "content": {"parts": ["hidden"]}
        }}}}
        self.assertIsNone(_parse_conversation(empty))

    def test_loads_json_export(self):
        export = [
            sample_chat("Chat A", "a", 1700000000, "user", "hello"),
            sample_chat("Chat B", "b", 1700000001, "assistant", "hi"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "conversations.json"
            path.write_text(json.dumps(export), encoding="utf-8")
            chats = _load_export(path)
        self.assertEqual([c["title"] for c in chats], ["Chat A", "Chat B"])

    def test_loads_chatgpt_export_zip(self):
        export = [sample_chat("Zip Chat", "z", 1700000000, "user", "from zip")]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chatgpt-export.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("account/conversations.json", json.dumps(export))
            chats = _load_export(path)
        self.assertEqual(chats[0]["messages"][0]["text"], "from zip")


if __name__ == "__main__":
    unittest.main()
