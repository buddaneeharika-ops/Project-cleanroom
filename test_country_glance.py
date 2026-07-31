import unittest
import json
import os
import sys

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, _build_glance_data

class TestCountryGlanceReport(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        _build_glance_data()

    def test_country_glance_report_route(self):
        """Test GET /country-glance-report returns 200 OK"""
        response = self.client.get('/country-glance-report')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Country Glance Report', response.data)

    def test_country_glance_test_alias_route(self):
        """Test GET /country-glance-test returns 200 OK (alias)"""
        response = self.client.get('/country-glance-test')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Country Glance Report', response.data)

    def test_country_glance_api_data(self):
        """Test GET /api/country_glance_report/data returns matrix & national_avg"""
        response = self.client.get('/api/country_glance_report/data')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data.decode('utf-8'))
        self.assertIn('matrix', data)
        self.assertIn('national_avg', data)
        self.assertGreater(len(data['matrix']), 0)

        # Verify J&K retro coverage is 100.0 (capped/adjusted)
        jk_row = next((r for r in data['matrix'] if r.get('state_abb') == 'JK'), None)
        self.assertIsNotNone(jk_row)
        self.assertEqual(jk_row.get('retro'), 100.0)

if __name__ == '__main__':
    unittest.main()
