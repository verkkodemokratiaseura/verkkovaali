# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from webob import Response

import unittest2 as unittest


class TestViews(unittest.TestCase):

    def test_disable_caching__headers_are_preserved(self):
        from nuorisovaalit.views import disable_caching
        response = Response()
        response.headerlist.append(('X-My-Header', 's3kr3t'))

        disable_caching(None, response)
        self.assertEquals(response.headers['x-my-header'], 's3kr3t')

    def test_disable_caching__cache_disabled(self):
        from nuorisovaalit.views import disable_caching
        response = Response()

        disable_caching(None, response)
        self.assertEquals(response.headerlist, [
            ('Content-Type', 'text/html; charset=UTF-8'),
            ('Content-Length', '0'),
            ('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0'),
            ('Cache-Control', 'post-check=0, pre-check=0'),
            ('Expires', ' Tue, 03 Jul 2001 06:00:00 GMT'),
            ('Pragma', 'no-cache')])
