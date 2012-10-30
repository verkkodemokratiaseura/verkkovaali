# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from pyramid import testing

import unittest


class TestSystem(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('login', '/login')
        self.config.add_route('about_page', '/about')
        self.config.add_route('contact_page', '/contact')
        self.config.add_route('openid_identity', '/id/{local_id}')
        self.config.add_route('home_page', '/home')
        self.config.add_route('logout', '/logout')

    def tearDown(self):
        testing.tearDown()

    def test_renderer_globals_factory__anonymous(self):
        from webidentity.views.system import renderer_globals_factory
        request = testing.DummyRequest()
        globs = renderer_globals_factory(dict(request=request))

        self.failIf(globs.pop('main', None) is None)
        self.assertEquals(globs, {
            'username': None,
            'flash_messages': [],
            'identity': None})

    def test_renderer_globals_factory__authenticated(self):
        from webidentity.views.system import renderer_globals_factory
        request = testing.DummyRequest()
        self.config.testing_securitypolicy(userid=u'dokai')
        globs = renderer_globals_factory(dict(request=request))

        self.failIf(globs.pop('main', None) is None)
        self.assertEquals(globs, {
            'username': u'dokai',
            'flash_messages': [],
            'identity': 'http://example.com/id/dokai'})

    def test_renderer_globals_factory__invalid_username(self):
        from webidentity.views.system import renderer_globals_factory
        request = testing.DummyRequest()
        request.headers['x-vhm-host'] = 'http://provider.com'

        self.config.testing_securitypolicy(userid=u'dokai ')
        self.assertRaises(ValueError, lambda: renderer_globals_factory(dict(request=request)))

    def test_renderer_globals_factory__flash_messages(self):
        from webidentity.views.system import renderer_globals_factory
        request = testing.DummyRequest()
        request.session.flash(u'Test messäge')
        globs = renderer_globals_factory(dict(request=request))

        self.failIf(globs.pop('main', None) is None)
        self.assertEquals(globs, {
            'username': None,
            'flash_messages': [u'Test messäge'],
            'identity': None})
