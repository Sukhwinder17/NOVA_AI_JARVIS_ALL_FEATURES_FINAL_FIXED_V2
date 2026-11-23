import unittest
from actions.whatsapp_wa.importer import parse_export

class WhatsAppExportParserTests(unittest.TestCase):
    def test_android_export_and_multiline(self):
        sample = "11/23/26, 09:15 - Alice: Hello\ncontinued line\n11/23/26, 09:16 - Bob: Hi"
        rows = parse_export(sample)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sender"], "Alice")
        self.assertIn("continued line", rows[0]["text"])
        self.assertEqual(rows[1]["sender"], "Bob")

    def test_ios_export(self):
        sample = "[23/11/26, 09:15:00] Alice: Hello"
        rows = parse_export(sample)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "Hello")

    def test_empty_export(self):
        self.assertEqual(parse_export("This is not a chat export"), [])

if __name__ == "__main__":
    unittest.main()
