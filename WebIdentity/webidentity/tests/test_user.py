# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import datetime
from pyramid import testing
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from webidentity.models import Activity
from webidentity.models import DBSession
from webidentity.models import Persona
from webidentity.models import User
from webidentity.models import UserAttribute
from webidentity.models import VisitedSite
from webidentity.tests import _initTestingDB
from webidentity.tests import DUMMY_SETTINGS
from webidentity.tests import DUMMY_USER_ATTRIBUTES

import unittest


class TestUser(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_settings(DUMMY_SETTINGS)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        _initTestingDB()

    def tearDown(self):
        testing.tearDown()
        DBSession.remove()

    def test_authenticated_user__anonymous(self):
        from webidentity.views.user import authenticated_user
        request = testing.DummyRequest()
        self.failUnless(authenticated_user(request) is None)

    def test_authenticated_user__authenticated(self):
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest()
        self.assertEquals(user, authenticated_user(request))

    def test_authenticated_user__authenticated_model_missing(self):
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'dokai')
        request = testing.DummyRequest()
        self.failUnless(authenticated_user(request) is None)

    def test_log_activity__anonymous(self):
        from webidentity.views.user import log_activity

        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())

        request = testing.DummyRequest()
        log_activity(request, Activity.LOGIN)
        self.assertEquals(0, session.query(Activity).count())

    def test_log_activity__without_url(self):
        from webidentity.views.user import log_activity

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())
        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest(
            environ={'REMOTE_ADDR': '1.2.3.4'},
            cookies={'auth_tkt': 'sessiontoken'})
        log_activity(request, Activity.LOGIN)

        self.assertEquals(1, session.query(Activity).count())
        log_entry = session.query(Activity).first()
        self.assertEquals(user.id, log_entry.user_id)
        self.assertEquals('1.2.3.4', log_entry.ipaddr)
        self.assertEquals('sessiontoken', log_entry.session)
        self.assertEquals(Activity.LOGIN, log_entry.action)
        self.assertEquals(None, log_entry.url)

    def test_log_activity__with_url(self):
        from webidentity.views.user import log_activity

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())
        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest(
            environ={'REMOTE_ADDR': '1.2.3.4'},
            cookies={'auth_tkt': 'sessiontoken'})
        log_activity(request, Activity.LOGIN, 'http://www.rp.com')

        self.assertEquals(1, session.query(Activity).count())
        log_entry = session.query(Activity).first()
        self.assertEquals(user.id, log_entry.user_id)
        self.assertEquals('1.2.3.4', log_entry.ipaddr)
        self.assertEquals('sessiontoken', log_entry.session)
        self.assertEquals(Activity.LOGIN, log_entry.action)
        self.assertEquals('http://www.rp.com', log_entry.url)

    def test_log_activity__with_single_x_http_forwarded_for(self):
        from webidentity.views.user import log_activity

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())
        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest(
            environ={
                'REMOTE_ADDR': '1.2.3.4',
                'HTTP_X_FORWARDED_FOR': '4.3.2.1'},
            cookies={'auth_tkt': 'sessiontoken'})
        log_activity(request, Activity.LOGIN, 'http://www.rp.com')

        self.assertEquals(1, session.query(Activity).count())
        log_entry = session.query(Activity).first()
        self.assertEquals(user.id, log_entry.user_id)
        self.assertEquals('4.3.2.1', log_entry.ipaddr)
        self.assertEquals('sessiontoken', log_entry.session)
        self.assertEquals(Activity.LOGIN, log_entry.action)
        self.assertEquals('http://www.rp.com', log_entry.url)

    def test_log_activity__with_empty_x_http_forwarded_for(self):
        from webidentity.views.user import log_activity

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())
        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest(
            environ={
                'REMOTE_ADDR': '1.2.3.4',
                'HTTP_X_FORWARDED_FOR': ''},
            cookies={'auth_tkt': 'sessiontoken'})
        log_activity(request, Activity.LOGIN, 'http://www.rp.com')

        self.assertEquals(1, session.query(Activity).count())
        log_entry = session.query(Activity).first()
        self.assertEquals(user.id, log_entry.user_id)
        self.assertEquals('1.2.3.4', log_entry.ipaddr)
        self.assertEquals('sessiontoken', log_entry.session)
        self.assertEquals(Activity.LOGIN, log_entry.action)
        self.assertEquals('http://www.rp.com', log_entry.url)

    def test_log_activity__with_multiple_x_http_forwarded_for(self):
        from webidentity.views.user import log_activity

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        self.assertEquals(0, session.query(Activity).count())
        user = User('dokai', 'secret', 'dokai@foobar.com')
        session.add(user)

        request = testing.DummyRequest(
            environ={
                'REMOTE_ADDR': '1.2.3.4',
                'HTTP_X_FORWARDED_FOR': '4.3.2.1,127.0.0.1,127.0.0.1'},
            cookies={'auth_tkt': 'sessiontoken'})
        log_activity(request, Activity.LOGIN, 'http://www.rp.com')

        self.assertEquals(1, session.query(Activity).count())
        log_entry = session.query(Activity).first()
        self.assertEquals(user.id, log_entry.user_id)
        self.assertEquals('4.3.2.1', log_entry.ipaddr)
        self.assertEquals('sessiontoken', log_entry.session)
        self.assertEquals(Activity.LOGIN, log_entry.action)
        self.assertEquals('http://www.rp.com', log_entry.url)

    def test_home_page__anonymous(self):
        from webidentity.views.user import home_page
        from pyramid.exceptions import Forbidden

        request = testing.DummyRequest()
        self.assertRaises(Forbidden, lambda: home_page(request))

    def test_home_page__authenticated(self):
        from webidentity.views.user import home_page

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()
        session.add(User('dokai', 'secret', 'dokai@foobar.com'))
        request = testing.DummyRequest()

        self.assertEquals(home_page(request), {})

    def test_change_password__anonymous(self):
        from webidentity.views.user import change_password
        from pyramid.exceptions import Forbidden

        request = testing.DummyRequest()
        self.assertRaises(Forbidden, lambda: change_password(request))

    def test_change_password__wrong_current_password(self):
        from webidentity.views.user import change_password

        self.config.testing_securitypolicy(userid=u'dokai')
        self.config.add_route('change_password', '/change-password')

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session = DBSession()
        session.add(user)
        request = testing.DummyRequest(
            post={
                'form.submitted': '1',
                'current_password': 'wrong',
                })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = token

        self.assertEquals(change_password(request), {
            'action_url': 'http://example.com/change-password',
            'csrf_token': token})
        # Check that the password is unchanged
        self.failUnless(user.check_password('secret'))

    def test_change_password__password_too_short(self):
        from webidentity.views.user import change_password

        self.config.testing_securitypolicy(userid=u'dokai')
        self.config.add_route('change_password', '/change-password')

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session = DBSession()
        session.add(user)
        request = testing.DummyRequest(
            post={
                'form.submitted': '1',
                'current_password': 'secret',
                'password': 'new',
                'confirm_password': 'new',
                })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = token

        self.assertEquals(change_password(request), {
            'action_url': 'http://example.com/change-password',
            'csrf_token': token})
        # Check that the password is unchanged
        self.failUnless(user.check_password('secret'))

    def test_change_password__password_mismatch(self):
        from webidentity.views.user import change_password

        self.config.testing_securitypolicy(userid=u'dokai')
        self.config.add_route('change_password', '/change-password')

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session = DBSession()
        session.add(user)
        request = testing.DummyRequest(
            post={
                'form.submitted': '1',
                'current_password': 'secret',
                'password': 'new_password',
                'confirm_password': 'something_else',
                })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = token

        self.assertEquals(change_password(request), {
            'action_url': 'http://example.com/change-password',
            'csrf_token': token})
        # Check that the password is unchanged
        self.failUnless(user.check_password('secret'))

    def test_change_password__csrf_mismatch(self):
        from pyramid.exceptions import Forbidden
        from webidentity.views.user import change_password

        self.config.testing_securitypolicy(userid=u'dokai')
        self.config.add_route('change_password', '/change-password')

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session = DBSession()
        session.add(user)
        request = testing.DummyRequest(
            post={
                'form.submitted': '1',
                'current_password': 'secret',
                'password': 'new_password',
                'confirm_password': 'something_else',
                })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = 'invalid'

        self.failIf(token == 'invalid')
        self.assertRaises(Forbidden, lambda: change_password(request))

    def test_change_password__success(self):
        from webidentity.views.user import change_password

        self.config.testing_securitypolicy(userid=u'dokai')
        self.config.add_route('change_password', '/change-password')

        user = User('dokai', 'secret', 'dokai@foobar.com')
        session = DBSession()
        session.add(user)
        request = testing.DummyRequest(
            post={
                'form.submitted': '1',
                'current_password': 'secret',
                'password': 'new_password',
                'confirm_password': 'new_password',
                })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = token

        self.assertEquals(change_password(request), {
            'action_url': 'http://example.com/change-password',
            'csrf_token': token})
        # Check that the password was changed correctly.
        self.failUnless(user.check_password('new_password'))

    def test_visited_sites__anonymous(self):
        from webidentity.views.user import visited_sites
        from pyramid.exceptions import Forbidden

        request = testing.DummyRequest()
        self.assertRaises(Forbidden, lambda: visited_sites(request))

    def test_visited_sites__empty(self):
        from webidentity.views.user import visited_sites
        self.config.testing_securitypolicy(userid=u'dokai')

        session = DBSession()
        session.add(User('dokai', 'secret', 'dokai@foobar.com'))

        request = testing.DummyRequest()
        self.assertEquals(visited_sites(request), {
            'action_url': 'form_action', 'sites': []})

    def test_visited_sites__not_empty(self):
        from webidentity.views.user import visited_sites
        self.config.testing_securitypolicy(userid=u'dokai')

        session = DBSession()
        user = User('dokai', 'secret', 'dokai@foobar.com')

        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))

        site1 = VisitedSite('http://www.rp.com', remember=False)
        site2 = VisitedSite('http://www.plone.org', remember=True)
        site2.persona = user.personas[0]

        user.visited_sites.append(site1)
        user.visited_sites.append(site2)

        user.activity.append(Activity(
            ipaddr='1.2.3.4',
            session='session1',
            action=Activity.AUTHORIZE_ONCE,
            url='http://www.rp.com',
            timestamp=datetime(2010, 1, 15, 12, 0)))
        user.activity.append(Activity(
            ipaddr='2.3.4.5',
            session='session2',
            action=Activity.AUTHORIZE_ONCE,
            url='http://www.plone.org',
            timestamp=datetime(2010, 3, 24, 15, 23)))
        user.activity.append(Activity(
            ipaddr='2.3.4.5',
            session='session3',
            action=Activity.AUTHORIZE,
            url='http://www.plone.org',
            timestamp=datetime(2010, 11, 15, 17, 9)))

        session.add(user)

        request = testing.DummyRequest()
        self.assertEquals(visited_sites(request), {
            'action_url': 'form_action',
            'sites': [
                {'url': u'http://www.plone.org',
                 'timestamp': '15.11.2010 17:09',
                 'persona': {'id': 1,
                             'edit_url': 'http://fo.bar/',
                             'name': u'Test persönä'},
                 'id': 2,
                 'remember': 'checked'},
                {'url': u'http://www.rp.com',
                 'timestamp': '15.01.2010 12:00',
                 'persona': None,
                 'id': 1,
                 'remember': None}]})
