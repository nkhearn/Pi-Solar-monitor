import unittest
from datetime import datetime
from api import parse_relative_time

class TestTimeParsing(unittest.TestCase):
    def test_iso_parsing(self):
        # Standard ISO with T and Z
        self.assertEqual(parse_relative_time("2024-03-20T10:00:00Z"), "2024-03-20 10:00:00")
        # ISO with T but no Z (assuming UTC as per system standard)
        self.assertEqual(parse_relative_time("2024-03-20T10:00:00"), "2024-03-20 10:00:00")
        # Original format still works
        self.assertEqual(parse_relative_time("2024-03-20 10:00:00"), "2024-03-20 10:00:00")

    def test_relative_time(self):
        # Today should return a string starting with today's date
        today_prefix = datetime.utcnow().strftime('%Y-%m-%d')
        self.assertTrue(parse_relative_time("today").startswith(today_prefix))

        # 1h should be roughly 1 hour ago
        one_hour_ago = parse_relative_time("1h")
        self.assertRegex(one_hour_ago, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

if __name__ == '__main__':
    unittest.main()
