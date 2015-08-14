import unittest

from garage.http2 import clients
from garage.http2 import utils

from .mocks import *


class TestUtils(unittest.TestCase):

    def test_form(self):
        req_to_rep = {
            ('GET', 'uri_1'): (200, b'<form action="uri_1"></form>'),
            ('POST', 'uri_1'): (200, 'hello world'),
            ('GET', 'uri_2'): (200, b'<form></form><form></form>'),
            ('GET', 'uri_3'): (
                200, b'''<form action="uri_3">
                         <input name="k1" value="v1"/>
                         <input name="k2" value="other_v2"/>
                         </form>
                      '''
            ),
            ('POST', 'uri_3'): (200, 'form filled'),
        }
        session = MockSession(req_to_rep)
        client = clients.Client(_session=session, _sleep=fake_sleep)

        rep = utils.form(client, 'uri_1')
        self.assertEqual('hello world', rep.content)

        with self.assertRaisesRegex(ValueError, 'require one form'):
            rep = utils.form(client, 'uri_2')

        session._logs.clear()
        rep = utils.form(client, 'uri_3', form_data={'k2': 'v2'})
        self.assertEqual('form filled', rep.content)
        self.assertEqual(2, len(session._logs))
        self.assertEqual('GET', session._logs[0].method)
        self.assertEqual('uri_3', session._logs[0].url)
        self.assertEqual('POST', session._logs[1].method)
        self.assertEqual('uri_3', session._logs[1].url)
        self.assertDictEqual({'k1': 'v1', 'k2': 'v2'}, session._logs[1].data)


if __name__ == '__main__':
    unittest.main()
