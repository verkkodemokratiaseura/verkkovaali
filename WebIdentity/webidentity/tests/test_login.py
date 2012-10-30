# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from datetime import datetime
from datetime import timedelta
from pyramid import testing
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from webidentity.models import DBSession
from webidentity.tests import DUMMY_SETTINGS
from webidentity.tests import _initTestingDB

import mock
import unittest


class TestLogoutView(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_settings(DUMMY_SETTINGS)

    def tearDown(self):
        testing.tearDown()

    @mock.patch('webidentity.views.login.forget')
    def test_logout(self, forget):
        from webidentity.views.login import logout
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
        self.config = testing.setUp()
        self.config.add_route('about_page', 'about')
        self.config.add_route('contact_page', 'contact')
        self.config.add_route('login', 'login')
        self.config.add_route('openid_identity', '/id/{local_id}')
        self.config.add_route('reset_password', 'reset-password')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        _initTestingDB()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_login__no_submission(self):
        from webidentity.views.login import login
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()

        options = login(request)
        self.assertEquals(options, {
            'title': u'Login',
            'reset_url': 'http://example.com/reset-password',
            'action_url': 'http://example.com/login',
            'login': u'',
            'csrf_token': token,
            })

    def test_login__form_submission__non_existing_user(self):
        from webidentity.views.login import login
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': token,
        }

        options = login(request)
        self.assertEquals(options, {
            'title': u'Login',
            'reset_url': 'http://example.com/reset-password',
            'action_url': 'http://example.com/login',
            'login': u'john.doe',
            'csrf_token': token})

    def test_login__form_submission__csrf_mismatch(self):
        from webidentity.views.login import login

        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': u'invalid',
        }

        self.failIf(token == u'invalid')
        self.assertRaises(Forbidden, lambda: login(request))

    def test_login__form_submission__invalid_password(self):
        from webidentity.views.login import login
        from webidentity.models import User
        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': token,
        }

        options = login(request)
        self.assertEquals(options, {
            'title': u'Login',
            'reset_url': 'http://example.com/reset-password',
            'action_url': 'http://example.com/login',
            'login': u'john.doe',
            'csrf_token': token})

    @mock.patch('webidentity.views.login.remember')
    def test_login__form_submission__success_with_local_id(self, remember):
        from webidentity.views.login import login
        from webidentity.models import User
        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        remember.return_value = [('X-Login', 'john.doe')]
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'john.doe',
            'password': u'secret',
            'csrf_token': token,
        }

        response = login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com',
            'X-Login': u'john.doe'})
        self.assertEquals(request.session.pop_flash(), [u'You have successfully logged in.'])

    @mock.patch('webidentity.views.login.remember')
    def test_login__form_submission__success_with_full_identity(self, remember):
        from webidentity.views.login import login
        from webidentity.models import User
        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        remember.return_value = [('X-Login', 'john.doe')]
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'http://example.com/id/john.doe',
            'password': u'secret',
            'csrf_token': token,
        }

        response = login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com',
            'X-Login': u'john.doe'})
        self.assertEquals(request.session.pop_flash(), [u'You have successfully logged in.'])

    @mock.patch('webidentity.views.login.remember')
    def test_login__form_submission__success_with_identity_wo_scheme(self, remember):
        from webidentity.views.login import login
        from webidentity.models import User
        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        self.assertEquals(
            session.query(User).filter_by(username=u'john.doe').first().email,
            u'john@doe.com')

        remember.return_value = [('X-Login', 'john.doe')]
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'login': u'example.com/id/john.doe',
            'password': u'secret',
            'csrf_token': token,
        }

        response = login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com',
            'X-Login': u'john.doe'})
        self.assertEquals(request.session.pop_flash(), [u'You have successfully logged in.'])


class TestPasswordResetView(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('openid_identity', '/id/{local_id}')
        self.config.add_route('reset_password', '/reset-password')
        self.config.add_route('reset_password_process', '/reset-password/process')
        self.config.add_route('reset_password_initiate', '/reset-password/initiate')
        self.config.add_route('reset_password_token', '/reset-password/{token}')
        _initTestingDB()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def _makeView(self, post=None):
        from webidentity.views.login import PasswordResetView
        request = testing.DummyRequest(post=post)
        return PasswordResetView(request)

    def test_prune_expired__empty(self):
        from webidentity.models import PasswordReset

        view = self._makeView()
        session = DBSession()

        self.assertEquals(0, session.query(PasswordReset).count())
        view.prune_expired()
        self.assertEquals(0, session.query(PasswordReset).count())

    def test_prune_expired(self):
        from webidentity.models import PasswordReset

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
            'title': u'Reset password'})

    def test_password_change_form__invalid_token(self):
        view = self._makeView()
        view.request.matchdict['token'] = u'invalid'
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form__expired_token(self):
        from webidentity.models import PasswordReset

        view = self._makeView()
        reset = PasswordReset(1, datetime.now() - timedelta(days=7))
        session = DBSession()
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())

        view.request.matchdict['token'] = reset.token
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form__invalid_user(self):
        from webidentity.models import PasswordReset
        from webidentity.models import User

        view = self._makeView()
        reset = PasswordReset(1, datetime.now() + timedelta(days=7))
        session = DBSession()
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())
        self.assertEquals(None, session.query(User).get(1))

        view.request.matchdict['token'] = reset.token
        self.assertRaises(NotFound, view.password_change_form)

    def test_password_change_form(self):
        from webidentity.models import PasswordReset
        from webidentity.models import User

        view = self._makeView()
        session = DBSession()

        user = User(u'john.doe', u'secret', u'john@doe.com')
        session.add(user)

        reset = PasswordReset(1, datetime.now() + timedelta(days=7), u'uniquetoken')
        session.add(reset)

        self.assertEquals(1, session.query(PasswordReset).filter_by(token=reset.token).count())
        self.assertEquals(u'john.doe', session.query(User).get(user.id).username)

        view.request.matchdict['token'] = reset.token
        self.assertEquals(view.password_change_form(), {
            'action_url': 'http://example.com/reset-password/process',
            'token': u'uniquetoken',
            'title': u'Change password'})

    def test_send_confirmation_message__missing_user(self):
        view = self._makeView()
        response = view.send_confirmation_message()
        self.assertEquals(response.location, 'http://example.com/reset-password')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Please supply a username.'])

    def test_send_confirmation_message__invalid_user(self):
        view = self._makeView(post={'username': u'john.doe'})
        response = view.send_confirmation_message()
        self.assertEquals(response.location, 'http://example.com/reset-password')
        self.assertEquals(view.request.session.pop_flash(),
            [u'The given username does not match any account.'])

    @mock.patch('webidentity.views.login.send_mail')
    def test_send_confirmation_message(self, send_mail):
        from webidentity.models import PasswordReset
        from webidentity.models import User
        from email.message import Message

        self.config.add_settings(DUMMY_SETTINGS)
        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        session.add(user)
        self.assertEquals(u'john.doe', session.query(User).get(1).username)

        view = self._makeView(post={'username': u'john.doe'})
        response = view.send_confirmation_message()

        self.assertEquals(1, session.query(PasswordReset).filter_by(user_id=1).count())
        self.assertEquals(response.location, 'http://example.com')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Password retrieval instructions have been emailed to you.'])
        self.assertEquals(send_mail.call_args[0][0], u'webidentity@provider.com')
        self.assertEquals(send_mail.call_args[0][1], [u'john@doe.com'])
        self.failUnless(isinstance(send_mail.call_args[0][2], Message))

    def test_create_message(self):
        from webidentity.models import PasswordReset
        from webidentity.models import User

        self.config.add_settings(DUMMY_SETTINGS)
        user = User(u'john.doe', u'secret', u'john@doe.com')
        reset = PasswordReset(1, datetime(2010, 11, 15, 17, 20), u'uniquetoken')
        view = self._makeView()

        message = view.create_message(user, reset)
        self.assertEquals(unicode(message['Subject']), u'Password reset for http://example.com/id/john.doe')
        self.assertEquals(unicode(message['From']), u'webidentity@provider.com')
        self.assertEquals(unicode(message['To']), u'john.doe <john@doe.com>')

        message_str = message.as_string()
        # Check that the relevant bits of information are included in the message
        self.failUnless('http://example.com/id/john.doe' in message_str)
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
            [u'Password must be at least five characters long'])

    def test_change_password__password_mismatch(self):
        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': '321cba'})
        response = view.change_password()
        self.assertEquals(response.location, 'http://example.com/reset-password/uniquetoken')
        self.assertEquals(view.request.session.pop_flash(),
            [u'Given passwords do not match'])

    def test_change_password__invalid_token(self):
        view = self._makeView(post={
            'token': 'uniquetoken',
            'password': 'abc123',
            'confirm_password': 'abc123'})
        self.assertRaises(NotFound, view.change_password)

    def test_change_password__invalid_user(self):
        from webidentity.models import PasswordReset

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

    @mock.patch('webidentity.views.login.remember')
    def test_change_password(self, remember):
        from webidentity.models import PasswordReset
        from webidentity.models import User

        remember.return_value = [('X-Login', 'john.doe')]
        user = User(u'john.doe', u'secret', u'john@doe.com')
        reset = PasswordReset(1, datetime.now() + timedelta(days=7), u'uniquetoken')

        session = DBSession()
        session.add(reset)
        session.add(user)
        session.flush()

        self.assertEquals(1, user.id)
        self.assertEquals(1, session.query(PasswordReset)\
            .filter(PasswordReset.user_id == 1)\
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
        self.failUnless(session.query(User).get(1).check_password('abc123'))
        # Check that the reset request was deleted
        self.assertEquals(0, session.query(PasswordReset).count())
