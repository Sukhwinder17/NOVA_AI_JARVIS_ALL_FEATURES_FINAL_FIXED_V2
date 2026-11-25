import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from actions.whatsapp_wa import waha_client, store


class WahaClientTests(unittest.TestCase):
    def test_save_settings_preserves_existing_env_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            env_path = Path(temp) / ".env"
            env_path.write_text("# keep this comment\nGROQ_API_KEY=existing\n", encoding="utf-8")
            with patch.object(waha_client, "ENV_PATH", env_path):
                waha_client.save_settings({
                    "url": "http://127.0.0.1:3000",
                    "api_key": "test-key",
                    "session": "nova",
                    "webhook_token": "webhook-secret",
                    "dashboard_password": "dashboard-secret",
                })
            saved = env_path.read_text(encoding="utf-8")
            self.assertIn("# keep this comment", saved)
            self.assertIn("GROQ_API_KEY=existing", saved)
            self.assertIn("NOVA_WAHA_API_KEY=test-key", saved)

    def test_send_text_posts_to_correct_endpoint(self):
        response = Mock()
        response.content = b'{"id":"sent"}'
        response.json.return_value = {"id": "sent"}
        with patch.object(waha_client, "_request", return_value=response) as request:
            with patch.object(waha_client, "settings", return_value={"session": "nova"}):
                result = waha_client.send_text("919900000000@c.us", "hello")
        request.assert_called_once_with("POST", "/api/sendText", json={
            "session": "nova",
            "chatId": "919900000000@c.us",
            "text": "hello",
        })
        self.assertEqual(result, {"id": "sent"})

    def test_missing_chat_or_text_rejected(self):
        with self.assertRaises(ValueError):
            waha_client.send_text("", "hello")
        with self.assertRaises(ValueError):
            waha_client.send_text("919900000000@c.us", "")

    def test_waha_history_sync_deduplicates_message_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "nova.sqlite3"
            messages = [
                {"id": "msg-1", "timestamp": 1760000000, "from": "919900000000@c.us", "fromMe": False, "body": "hello"},
                {"id": "msg-2", "timestamp": 1760000001, "from": "919900000000@c.us", "fromMe": True, "body": "reply"},
            ]
            with patch.object(store, "DB_PATH", db_path):
                first = store.add_waha_history("nova", "919900000000@c.us", "Test Contact", messages)
                second = store.add_waha_history("nova", "919900000000@c.us", "Test Contact", messages)
                with store.connect() as db:
                    count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            self.assertEqual(first["added"], 2)
            self.assertEqual(second["added"], 0)
            self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
