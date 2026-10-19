import unittest
import json
from app import app
from db import query_db

class CineBookTestSuite(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_homepage_loads_real_records(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        # Check branding
        self.assertIn('Cine', html)
        self.assertIn('Book', html)
        # Check real movie from DB
        self.assertIn('Leo', html)
        self.assertIn('Tamil', html)
        # Check theatres from DB
        self.assertIn('CineBook Cinemas', html)

    def test_02_movie_catalogue_search_and_filters(self):
        # All movies
        res = self.client.get('/movies')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Leo', res.data.decode('utf-8'))

        # Search parameter
        res_search = self.client.get('/movies?q=Interstellar')
        self.assertEqual(res_search.status_code, 200)
        self.assertIn('Interstellar', res_search.data.decode('utf-8'))

        # Language filter parameter
        res_lang = self.client.get('/movies?lang=Telugu')
        self.assertEqual(res_lang.status_code, 200)
        self.assertIn('RRR', res_lang.data.decode('utf-8'))

    def test_03_movie_details(self):
        res = self.client.get('/movie/1')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Leo', html)
        self.assertIn('CineBook Cinemas', html)
        self.assertIn('Screen 1', html)
        # Verify IMDb and Community ratings presentation
        self.assertIn('IMDb', html)
        self.assertIn('CineBook Community', html)
        self.assertIn('Watch Official Trailer', html)

    def test_04_theatres_discovery(self):
        res = self.client.get('/theatres')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Galaxy Multiplex', html)
        self.assertIn('Tambaram', html)

    def test_05_api_show_details_and_booked_seats(self):
        res = self.client.get('/api/shows/1/details')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['movie_name'], 'Leo')
        self.assertEqual(data['theatre_name'], 'CineBook Cinemas')
        # Check that existing booked seats A1 and A2 are accurately returned from TICKET
        self.assertIn('A1', data['booked_seats'])
        self.assertIn('A2', data['booked_seats'])

    def test_06_customer_lookup_api(self):
        # Test existing customer
        res = self.client.get('/api/customer/lookup?phone=9876500001')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['exists'])
        self.assertEqual(data['customer_name'], 'Arun Kumar')

        # Test non-existing customer
        res_none = self.client.get('/api/customer/lookup?phone=9999999999')
        self.assertEqual(res_none.status_code, 200)
        self.assertFalse(res_none.get_json()['exists'])

    def test_07_booking_seat_conflict_detection(self):
        # In show 1, seats A1 and A2 are already booked in sample database.
        # Attempting to book A1 must be safely rejected with 409 conflict!
        payload = {
            "show_id": 1,
            "seats": ["A1", "A3"],
            "customer_name": "Test Conflict User",
            "customer_phone": "9876599999",
            "payment_mode": "UPI",
            "snacks": {}
        }
        res = self.client.post('/api/booking/submit',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 409)
        data = res.get_json()
        self.assertEqual(data['error'], 'Seat conflict')
        self.assertIn('A1', data['conflicts'])

    def test_08_my_bookings_lookup(self):
        # Lookup existing booking 1 with Arun Kumar's phone
        res = self.client.get('/my-bookings?booking_id=1&phone=9876500001')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Arun Kumar', html)
        self.assertIn('Leo', html)
        self.assertIn('A1', html)
        self.assertIn('A2', html)

    def test_09_booking_confirmation_ticket_pass(self):
        res = self.client.get('/booking/confirmation/1')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('CB-00001', html)
        self.assertIn('Arun Kumar', html)
        self.assertIn('Popcorn', html)
        self.assertIn('390.00', html)
        self.assertIn('Add to Calendar', html)

    def test_10_admin_route_protection(self):
        # Unauthenticated access to admin dashboard should redirect to login
        res = self.client.get('/admin/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers['Location'])

    def test_11_admin_authentication_and_dashboard(self):
        # Wrong password
        res_fail = self.client.post('/admin/login', data={'username': 'admin', 'password': 'wrongpassword'}, follow_redirects=True)
        self.assertIn('Invalid administrator username or password', res_fail.data.decode('utf-8'))

        # Correct password
        res_ok = self.client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn('Dashboard Overview', res_ok.data.decode('utf-8'))

        # Check all admin views with authenticated session
        for path in ['/admin/movies', '/admin/theatres', '/admin/screens', '/admin/shows', '/admin/employees', '/admin/snacks', '/admin/bookings', '/admin/analytics']:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, f"Failed on path {path}")

    def test_12_api_analytics_data(self):
        res = self.client.get('/api/admin/analytics-data')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('ticket_revenue', data)
        self.assertIn('snack_revenue', data)
        self.assertIn('total_revenue', data)
        self.assertIn('movies', data)
        self.assertIn('theatres', data)
        self.assertIn('snacks', data)
        # Check positive numbers from database
        self.assertGreater(data['total_revenue'], 0)
        self.assertGreater(data['ticket_revenue'], 0)
        self.assertGreater(data['snack_revenue'], 0)

    def test_13_api_movies_quick_search(self):
        # Test quick search auto-complete endpoint
        res = self.client.get('/api/movies/quick-search?q=leo')
        self.assertEqual(res.status_code, 200)
        results = res.get_json()
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertIn('title', first)
        self.assertEqual(first['title'], 'Leo')
        self.assertIn('poster_url', first)
        self.assertIn('rating', first)

    def test_14_api_watchlist_toggle_and_list(self):
        # Toggle movie 1 into watchlist
        res_add = self.client.post('/api/watchlist/toggle',
                                  data=json.dumps({"movie_id": 1}),
                                  content_type='application/json')
        self.assertEqual(res_add.status_code, 200)
        data_add = res_add.get_json()
        self.assertTrue(data_add['in_watchlist'])
        self.assertGreaterEqual(data_add['count'], 1)

        # Query watchlist list endpoint
        res_list = self.client.get('/api/watchlist')
        self.assertEqual(res_list.status_code, 200)
        data_list = res_list.get_json()
        self.assertIn(1, data_list['watchlist'])

        # Toggle movie 1 out of watchlist
        res_rem = self.client.post('/api/watchlist/toggle',
                                  data=json.dumps({"movie_id": 1}),
                                  content_type='application/json')
        self.assertEqual(res_rem.status_code, 200)
        self.assertFalse(res_rem.get_json()['in_watchlist'])

    def test_15_api_reviews_submission_and_community_score(self):
        # Get reviews for movie 1
        res_get = self.client.get('/api/reviews/1')
        self.assertEqual(res_get.status_code, 200)
        rev_data = res_get.get_json()
        self.assertIn('average_rating', rev_data)
        self.assertIn('reviews', rev_data)

        # Submit a test review
        payload = {
            "user_name": "Test Cinephile",
            "rating": 9,
            "review_text": "Exceptional cinematography and background score in Dolby Atmos!"
        }
        res_post = self.client.post('/api/reviews/1',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(res_post.status_code, 201)
        post_data = res_post.get_json()
        self.assertEqual(post_data['success'], True)
        self.assertGreater(post_data['review_count'], 0)

    def test_16_theatres_discovery_date_and_slot_filter(self):
        # Test time slot filtering
        res_slot = self.client.get('/theatres?time_slot=Morning')
        self.assertEqual(res_slot.status_code, 200)
        html = res_slot.data.decode('utf-8')
        self.assertIn('Active filters', html)
        self.assertIn('Slot: Morning', html)

        # Test date filtering
        res_date = self.client.get('/theatres?date=2026-10-20')
        self.assertEqual(res_date.status_code, 200)
        self.assertIn('2026-10-20', res_date.data.decode('utf-8'))

    def test_17_catalogue_view_modes_and_watchlist_filter(self):
        # Test list view mode
        res_list = self.client.get('/movies?view=list')
        self.assertEqual(res_list.status_code, 200)
        html = res_list.data.decode('utf-8')
        self.assertIn('movie-list-item', html)

        # Test watchlist filter mode
        res_watch = self.client.get('/movies?watchlist=1')
        self.assertEqual(res_watch.status_code, 200)

if __name__ == '__main__':
    unittest.main()
