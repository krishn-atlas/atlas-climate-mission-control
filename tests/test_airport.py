import unittest
from datetime import datetime, timezone
from scripts.publish_airport import normalize

class AirportTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 10, 0, tzinfo=timezone.utc)
        self.record = {'icaoId': 'VOMM', 'obsTime': self.now.timestamp(), 'rawOb': 'SYNTHETIC', 'temp': 0, 'wspd': 8, 'altim': 1011, 'visib': '10+'}

    def test_units_zero_and_qualified_visibility(self):
        result = normalize([self.record], self.now)
        self.assertEqual(result['temperature_c'], 0)
        self.assertEqual(result['wind_kmh'], 14.8)
        self.assertEqual(result['visibility_statute_miles'], '10+')

    def test_missing_values_stay_missing(self):
        for key in ['temp', 'wspd', 'altim', 'visib']:
            self.record.pop(key)
        result = normalize([self.record], self.now)
        self.assertIsNone(result['temperature_c'])
        self.assertIsNone(result['wind_kmh'])

    def test_bad_reports_rejected(self):
        for change in [{'icaoId': 'OTHER'}, {'obsTime': self.now.timestamp()-7300}, {'obsTime': self.now.timestamp()+400}, {'rawOb': ''}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize([dict(self.record, **change)], self.now)

    def test_newest_report_selected(self):
        old = dict(self.record, obsTime=self.now.timestamp()-1800, temp=10)
        self.assertEqual(normalize([self.record, old], self.now)['temperature_c'], 0)
