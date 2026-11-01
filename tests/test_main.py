import unittest

from housing_monitor.email_ingestion.parsers.immoscout24 import parse_email


def run():
    return {"status": "ok", "parser": parse_email}


class TestMain(unittest.TestCase):

    def test_run(self):
        result = run()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(callable(result["parser"]))


if __name__ == '__main__':
    unittest.main()