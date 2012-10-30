# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import datetime
from datetime import timedelta
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.tests import DUMMY_SETTINGS
from nuorisovaalitadmin.tests import init_testing_db
from nuorisovaalitadmin.tests import populate_testing_db
from pyramid import testing
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.testing import DummyRequest
import mock
import unittest


class LoginTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_index__unauthenticated(self):
        from nuorisovaalitadmin.views.login import index

        self.assertRaises(Forbidden, lambda: index(DummyRequest()))

    def test_index__authenticated(self):
        from nuorisovaalitadmin.views.login import index
        from nuorisovaalitadmin.models import User

        session = DBSession()
        populate_testing_db()
        user = session.query(User).first()
        self.config.testing_securitypolicy(userid=user.username)

        self.assertEquals({}, index(DummyRequest()))


class TestUtilities(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()
        DBSession.remove()

    def test_authenticated_user__anonymous(self):
        from nuorisovaalitadmin.views.login import authenticated_user

        request = testing.DummyRequest()
        self.failUnless(authenticated_user(request) is None)

    def test_authenticated_user__authenticated(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import authenticated_user

        self.config.testing_securitypolicy(userid=u'dokai')
        session = DBSession()

        # We're cheating here by setting the foreign key without having a
        # corresponding object. We get away with it because SQLite doesn't
        # enforce the foreign key constraint.
        user = User(u'dokai', u'secret', u'Kai', 'dokai@foobar.com', school_or_id=1)
        session.add(user)

        request = testing.DummyRequest()
        self.assertEquals(user, authenticated_user(request))

    def test_authenticated_user__authenticated_model_missing(self):
        from nuorisovaalitadmin.views.login import authenticated_user

        self.config.testing_securitypolicy(userid=u'dokai')
        request = testing.DummyRequest()
        self.failUnless(authenticated_user(request) is None)

    def test_groupfinder__invalid_user(self):
        from nuorisovaalitadmin.views.login import groupfinder

        self.assertEquals(None, groupfinder(u'unknown', testing.DummyRequest()))

    def test_groupfinder__no_groups(self):
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import groupfinder

        session = DBSession()
        session.add(User(u'dokai', u'secret', u'Kai', 'dokai@foobar.com', school_or_id=1))

        self.assertEquals([], groupfinder(u'dokai', testing.DummyRequest()))

    def test_groupfinder__with_groups(self):
        from nuorisovaalitadmin.models import Group
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import groupfinder

        session = DBSession()
        user = User(u'dokai', u'secret', u'Kai', 'dokai@foobar.com', school_or_id=1)
        session.add(user)
        session.flush()
        user.groups.append(Group(u'coolios', u'Coolios'))
        user.groups.append(Group(u'admins', u'Administrators'))

        self.assertEquals(groupfinder(u'dokai', testing.DummyRequest()), [
            'group:coolios', 'group:admins'])


class TestLogoutView(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @mock.patch('nuorisovaalitadmin.views.login.forget')
    def test_logout(self, forget):
        from nuorisovaalitadmin.views.login import logout
        request = testing.DummyRequest()
        forget.return_value = [('X-Logout', 'logout')]

        response = logout(request)
        self.failUnless(forget.called)
        # Assert we do a redirect back to the root
        self.assertEqual(dict(response.headers), {
            'Content-Length': '0',
            'X-Logout': 'logout',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com'})


class TestLoginView(unittest.TestCase):

    def setUp(self):
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        self.config = testing.setUp()
        self.config.add_route('about_page', 'about')
        self.config.add_route('contact_page', 'contact')
        self.config.add_route('login', 'login')
        self.config.add_route('reset_password', 'reset-password')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_login__no_submission(self):
        from nuorisovaalitadmin.views.login import login
        request = testing.DummyRequest()
        token = request.session.new_csrf_token()

        options = login(request)
        self.assertEquals(options, {
            'title': u'Kirjaudu sisään',
            'action_url': 'http://example.com/login',
            'username': u'',
            'reset_url': 'http://example.com/reset-password',
            'csrf_token': token,
            })

    def test_login__form_submission__non_existing_user(self):
        from nuorisovaalitadmin.views.login import login
        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'username': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': token,
        }

        options = login(request)
        self.assertEquals(options, {
            'title': u'Kirjaudu sisään',
            'action_url': 'http://example.com/login',
            'username': u'john.doe',
            'reset_url': 'http://example.com/reset-password',
            'csrf_token': token})

    def test_login__form_submission__csrf_mismatch(self):
        from nuorisovaalitadmin.views.login import login

        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'username': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': u'invalid',
        }

        self.failIf(token == u'invalid')
        self.assertRaises(Forbidden, lambda: login(request))

    def test_login__form_submission__invalid_password(self):
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import login

        session = DBSession()
        populate_testing_db()
        school = session.query(School).first()
        self.assertTrue(school is not None)
        session.add(User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school))
        session.flush()
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'username': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': token,
        }

        options = login(request)
        self.assertEquals(options, {
            'title': u'Kirjaudu sisään',
            'action_url': 'http://example.com/login',
            'username': u'john.doe',
            'reset_url': 'http://example.com/reset-password',
            'csrf_token': token})

    @mock.patch('nuorisovaalitadmin.views.login.remember')
    def test_login__form_submission__success_with_local_id(self, remember):
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import login

        session = DBSession()
        populate_testing_db()
        school = session.query(School).first()
        self.assertTrue(school is not None)
        session.add(User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        remember.return_value = [('X-Login', 'john.doe')]
        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'username': u'john.doe',
            'password': u'secret',
            'csrf_token': token,
        }

        response = login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com',
            'X-Login': u'john.doe'})
        self.assertEquals(request.session.pop_flash(), [u'Olet kirjautunut sisään.'])

    @mock.patch('nuorisovaalitadmin.views.login.remember')
    def test_login__form_submission__success_with_full_identity(self, remember):
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.login import login

        session = DBSession()
        populate_testing_db()
        school = session.query(School).first()
        self.assertTrue(school is not None)
        session.add(User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        remember.return_value = [('X-Login', 'john.doe')]
        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'username': u'john.doe',
            'password': u'secret',
            'csrf_token': token,
        }

        response = login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com',
            'X-Login': u'john.doe'})
        self.assertEquals(request.session.pop_flash(), [u'Olet kirjautunut sisään.'])


class TestPasswordResetView(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('reset_password', '/reset-password')
        self.config.add_route('reset_password_process', '/reset-password/process')
        self.config.add_route('reset_password_initiate', '/reset-password/initiate')
        self.config.add_route('reset_password_token', '/reset-password/{token}')
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def _makeView(self, post=None):
        from nuorisovaalitadmin.views.login import PasswordResetView
        request = testing.DummyRequest(post=post)
        return PasswordResetView(request)

    def test_prune_expired__empty(self):
        from nuorisovaalitadmin.models import PasswordReset

        view = self._makeView()
        session = DBSession()

        self.assertEquals(0, session.query(PasswordReset).count())
        view.prune_expired()
        self.assertEquals(0, session.query(PasswordReset).count())

    def test_prune_expired(self):
        from nuorisovaalitadmin.models import PasswordReset

        view = self._makeView()
        session = DBSession()

        session.add(PasswordReset(1, datetime.now() - timedelta(days=30)))
        session.add(PasswordReset(2, datetime.now() + timedelta(days=30)))

        self.assertEquals(2, session.query(PasswordReset).count())
        view.prune_expired()
        self.assertEquals(1, session.query(PasswordReset).count())
        self.assertEquals(2, session.query(PasswordReset).first().user_id)

    def test_render_form(self):
        view = self._makeView()
        self.assertEquals(view.render_form(), {
            'action_url': 'http://example.com/reset-password/initiate',
            'title': u'Nollaa salasana'})

    def test_password_change_form__invalid_token(self):
        view = self._makeView()
        view.request.matchdict['token'] = u'invalid'
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form__expired_token(self):
        from nuorisovaalitadmin.models import PasswordReset

        view = self._makeView()
        reset = PasswordReset(1, datetime.now() - timedelta(days=7))
        session = DBSession()
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())

        view.request.matchdict['token'] = reset.token
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form__invalid_user(self):
        from nuorisovaalitadmin.models import PasswordReset
        from nuorisovaalitadmin.models import User

        view = self._makeView()
        reset = PasswordReset(1, datetime.now() + timedelta(days=7))
        session = DBSession()
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())
        self.assertEquals(None, session.query(User).get(1))

        view.request.matchdict['token'] = reset.token
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form(self):
        from nuorisovaalitadmin.models import PasswordReset
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User

        view = self._makeView()
        session = DBSession()
        populate_testing_db()

        school = session.query(School).first()
        self.assertTrue(school is not None)

        user = User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school)
        session.add(user)
        session.flush()

        reset = PasswordReset(user.id, datetime.now() + timedelta(days=7), u'uniquetoken')
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())
        self.assertEquals(u'john.doe', session.query(User).get(user.id).username)

        view.request.matchdict['token'] = reset.token
        self.assertEquals(view.password_change_form(), {
            'username': u'john.doe',
            'action_url': 'http://example.com/reset-password/process',
            'token': u'uniquetoken',
            'title': u'Vaihda salasana'})

    def test_send_confirmation_message__missing_user(self):
        view = self._makeView()
        response = view.send_confirmation_message()
        self.assertEquals(response.location, 'http://example.com/reset-password')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Anna käyttäjätunnus.'])

    def test_send_confirmation_message__invalid_user(self):
        view = self._makeView(post={'username': u'john.doe'})
        response = view.send_confirmation_message()
        self.assertEquals(response.location, 'http://example.com/reset-password')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Annettua käyttäjätunnusta ei löydy.'])

    @mock.patch('nuorisovaalitadmin.views.login.send_mail')
    def test_send_confirmation_message(self, send_mail):
        from email.message import Message
        from nuorisovaalitadmin.models import PasswordReset
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User

        self.config.add_settings(DUMMY_SETTINGS)
        session = DBSession()
        populate_testing_db()
        school = session.query(School).first()
        self.assertTrue(school is not None)

        user = User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school)
        session.add(user)
        session.flush()
        userid = user.id

        view = self._makeView(post={'username': u'john.doe'})
        response = view.send_confirmation_message()

        self.assertEquals(1, session.query(PasswordReset).filter_by(user_id=userid).count())
        self.assertEquals(response.location, 'http://example.com')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Ohjeet salasanan vaihtamiseen on lähetetty sähköpostissa.'])
        self.assertEquals(send_mail.call_args[0][0], u'nuorisovaalitadmin@provider.com')
        self.assertEquals(send_mail.call_args[0][1], [u'john@doe.com'])
        self.failUnless(isinstance(send_mail.call_args[0][2], Message))

    def test_create_message(self):
        from nuorisovaalitadmin.models import PasswordReset
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User

        session = DBSession()
        populate_testing_db()
        self.config.add_settings(DUMMY_SETTINGS)

        school = session.query(School).first()
        self.assertTrue(school is not None)
        user = User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school)
        session.add(user)
        session.flush()
        reset = PasswordReset(user.id, datetime(2010, 11, 15, 17, 20), u'uniquetoken')
        view = self._makeView()

        message = view.create_message(user, reset)
        self.assertEquals(unicode(message['Subject']), u'john.doe')
        self.assertEquals(unicode(message['From']), u'xxxx@xxxx.xxx')
        self.assertEquals(unicode(message['To']), u'john.doe <john@doe.com>')

        message_str = message.as_string()
        # Check that the relevant bits of information are included in the message
        self.failUnless('john.doe' in message_str)
        self.failUnless('15.11.2010 17:20' in message_str)
        self.failUnless('http://example.com/reset-password/uniquetoken' in message_str)

    def test_change_password__missing_token(self):
        view = self._makeView()
        self.assertRaises(NotFound, view.change_password)

    def test_change_password__password_too_short(self):
        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc'})
        response = view.change_password()
        self.assertEquals(response.location, 'http://example.com/reset-password/uniquetoken')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Salasanan on oltava vähintään viisi merkkiä pitkä'])

    def test_change_password__password_mismatch(self):
        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': '321cba'})
        response = view.change_password()
        self.assertEquals(response.location, 'http://example.com/reset-password/uniquetoken')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Annetut salasanat eivät vastaa toisiaan'])

    def test_change_password__invalid_token(self):
        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': 'abc123'})
        self.assertRaises(NotFound, view.change_password)

    def test_change_password__invalid_user(self):
        from nuorisovaalitadmin.models import PasswordReset

        reset = PasswordReset(1, datetime.now() + timedelta(days=7), u'uniquetoken')
        session = DBSession()
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset)\
            .filter(PasswordReset.token == u'uniquetoken')\
            .filter(PasswordReset.expires >= datetime.now())\
            .count())

        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': 'abc123'})
        self.assertRaises(NotFound, view.change_password)

    @mock.patch('nuorisovaalitadmin.views.login.remember')
    def test_change_password(self, remember):
        from nuorisovaalitadmin.models import PasswordReset
        from nuorisovaalitadmin.models import School
        from nuorisovaalitadmin.models import User

        session = DBSession()
        populate_testing_db()

        school = session.query(School).first()
        self.assertTrue(school is not None)

        remember.return_value = [('X-Login', 'john.doe')]
        user = User(u'john.doe', u'secret', u'Jöhn Döe', u'john@doe.com', school_or_id=school)
        session.add(user)
        session.flush()

        reset = PasswordReset(user.id, datetime.now() + timedelta(days=7), u'uniquetoken')
        session.add(reset)
        session.flush()

        self.assertEquals(1, session.query(PasswordReset)\
            .filter(PasswordReset.user_id == user.id)\
            .filter(PasswordReset.token == u'uniquetoken')\
            .filter(PasswordReset.expires >= datetime.now())\
            .count())

        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': 'abc123'})
        response = view.change_password()
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'X-Login': 'john.doe',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com'})
        # Check that the password was changed
        self.failUnless(session.query(User).filter_by(id=user.id).first().check_password('abc123'))
        # Check that the reset request was deleted
        self.assertEquals(0, session.query(PasswordReset).count())
