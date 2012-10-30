# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalit.models import DBSession
from nuorisovaalit.tests import init_testing_db
from pyramid import testing
from pyramid.testing import DummyRequest

import unittest2 as unittest


class UnauthorizedTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.views.system import renderer_globals_factory
        self.config = testing.setUp()
        self.config.set_renderer_globals_factory(renderer_globals_factory)
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_unauthorized__response_status(self):
        from nuorisovaalit.views.exceptions import unauthorized

        self.assertEquals('403 Forbidden', unauthorized(DummyRequest()).status)
