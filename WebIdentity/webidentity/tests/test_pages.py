# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
import unittest
from pyramid import testing


class TestFrontPage(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_frontpage(self):
        from webidentity.views.pages import front_page

        self.config.add_route('openid_endpoint', '/openid')
        self.config.add_route('yadis_server', '/yadis')
        request = testing.DummyRequest()

        self.assertEquals(front_page(request), {
            'xrds_location': 'http://example.com/yadis',
            'openid_endpoint': 'http://example.com/openid',
            'title': u'Nuorisovaalit 2011 - Tunnistautuminen'})
