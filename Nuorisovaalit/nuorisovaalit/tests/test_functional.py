# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from Cookie import SimpleCookie
from datetime import datetime
from nuorisovaalit.models import DBSession
from nuorisovaalit.tests import populate_testing_db
from nuorisovaalit.tests import static_datetime
from pyramid import testing
from pyramid.interfaces import IAuthenticationPolicy
from pyramid.testing import DummyRequest

import mock
import shutil
import tempfile
import unittest2 as unittest
import webtest


TEST_CONFIG = {

    'sqlalchemy.url': 'sqlite://',

    'session.key': 'nuorisovaalit',
    'session.cookie_expires': 'true',
    'session.type': 'ext:memcached',
    'session.url': 'xxx.x.x.x:xxxxx',
    'session.auto': 'true',
    'session.validate_key': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    'session.timeout': '3600',
}


class TestHelpers(unittest.TestCase):

    def test_static_datetime(self):
        d = datetime(1999, 1, 2, 3, 4, 5, 6)
        static = static_datetime(d)
        for i in xrange(1000):
            self.assertEquals(d, static.now())

    def test_static_datetime__invalid(self):
        self.assertRaises(TypeError, lambda: static_datetime(None))
        self.assertRaises(TypeError, lambda: static_datetime(u'Invalid'))

    def test_Coalition__no_district(self):
        from nuorisovaalit.models import Coalition

        coalition = Coalition(u'name')
        self.assertTrue(coalition.district_id is None)


class VotingProcessTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.run import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG.copy()
        config['session.lock_dir'] = self.lock_dir
        config['nuorisovaalit.skip_voting_period_check'] = 'true'
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))
        self.config = testing.setUp()
        populate_testing_db()

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    def authenticate(self, openid):
        """Authenticates the given OpenID by setting the appropriate cookies.

        .. note:: The database must contain a Voter object with a matching
                  openid field.
        """
        auth_policy = self.testapp.app.registry.queryUtility(IAuthenticationPolicy)
        request = DummyRequest(environ=dict(
            REMOTE_ADDR='xxx.x.x.x',
            HTTP_HOST='127.0.0.1'))
        headers = auth_policy.remember(request, openid)
        for _, cookie in headers:
            for key, morsel in SimpleCookie(cookie).items():
                self.testapp.cookies[key] = morsel.value

    def test_valid_voting_process__decline_openid(self):
        from nuorisovaalit.models import Vote
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        # Fake the OpenID authentication.
        self.authenticate(u'http://example.com/id/matti.meikalainen')

        # Select a candidate
        response = self.testapp.get('/valitse')
        self.assertEquals('200 OK', response.status)

        # Select a candidate
        response = response.click(href='/aanesta/1$')
        self.assertEquals('200 OK', response.status)

        # Assert we are showing the correct voter information
        self.assertEquals([tag.text for tag in response.html.find('table', id='voter').findAll('td')], [
            u'Matti Meikäläinen',
            u'Ahvenanmaan maakunnan vaalipiiri',
        ])

        # Assert we got the candidate we selected
        self.assertEquals(response.html.find('p', 'candidate-name').text, u'1 Turhapuro, Uuno')

        # Vote for the candidate
        response.form[u'vote'] = u'1'
        response = response.form.submit()

        # The form submission uses a redirect to avoid accidental resubmissions.
        self.assertEquals('302 Found', response.status)
        response = response.follow()
        self.assertEquals('200 OK', response.status)

        # Assert the vote was registered
        self.assertEquals(response.html.find('h1').text, u'Äänesi on tallennettu')
        session = DBSession()
        self.assertEquals(1, session.query(VotingLog)\
                                .join(Voter)\
                                .filter_by(openid=u'http://example.com/id/matti.meikalainen')\
                                .count())
        self.assertEquals(1, session.query(Vote).count())

        # Submit the OpenID preference form with default values which will
        # decline the offer to use OpenID in the future.
        response = response.form.submit()

        self.assertEquals('302 Found', response.status)
        response = response.follow()
        self.assertEquals('200 OK', response.status)

        # Assert that the accept_openid is False for the voter.
        session = DBSession()
        voter = session.query(Voter).filter_by(openid=u'http://example.com/id/matti.meikalainen').one()
        self.assertFalse(voter.accept_openid)

        # Assert we got logged out.
        self.assertEquals(self.testapp.cookies['auth_tkt'], '')
        # Assert we are suggested to close the browser window.
        self.assertEquals(response.html.h1.text, u'Sulje ikkuna')

    def test_valid_voting_process__accept_openid(self):
        from nuorisovaalit.models import Voter

        # Fake the OpenID authentication.
        self.authenticate(u'http://example.com/id/matti.meikalainen')
        # Select a candidate.
        response = self.testapp.get('/valitse')
        response = response.click(href='/aanesta/1$')
        # Vote for the candidate.
        response.form[u'vote'] = u'1'
        response = response.form.submit()
        # Follow the redirect to the OpenID preference page.
        response = response.follow()

        # Fill in valid information and choose to keep the OpenID.
        response.form[u'gsm'] = u'0401234567'
        response.form[u'email'] = u'matti.meikalainen@example.com'
        response.form[u'street'] = u'Söme street 16'
        response.form[u'zipcode'] = u'01234'
        response.form[u'city'] = u'Söme city, Länd'
        response.form[u'use_open_identity'] = u'yes'

        response = response.form.submit()
        self.assertEquals('302 Found', response.status)
        response = response.follow()
        self.assertEquals('200 OK', response.status)

        # Assert that the voter information is correct.
        session = DBSession()
        voter = session.query(Voter).filter_by(openid=u'http://example.com/id/matti.meikalainen').one()
        self.assertTrue(voter.accept_openid)
        self.assertEquals(u'0401234567', voter.gsm)
        self.assertEquals(u'matti.meikalainen@example.com', voter.email)
        self.assertEquals(u'Söme street 16, 01234, Söme city, Länd', voter.address)

    def test_valid_voting_process__empty_information(self):
        # Fake the OpenID authentication.
        self.authenticate(u'http://example.com/id/matti.meikalainen')
        # Select a candidate.
        response = self.testapp.get('/valitse')
        response = response.click(href='/aanesta/1$')
        # Vote for the candidate.
        response.form[u'vote'] = u'1'
        response = response.form.submit()
        # Follow the redirect to the OpenID preference page.
        response = response.follow()

        # Leave the whole form empty.
        response.form[u'gsm'] = u''
        response.form[u'email'] = u''
        response.form[u'street'] = u''
        response.form[u'zipcode'] = u''
        response.form[u'city'] = u''
        response.form[u'use_open_identity'] = u'yes'

        response = response.form.submit()
        self.assertEquals('200 OK', response.status)

        error_container = response.html.findAll(id='pref-errors')[0]
        self.assertEquals(u'Antamissasi tiedoissa oli virheitä:', error_container.h3.string)
        errors = error_container.findAll('li')
        self.assertEquals([
            u'GSM-numero on virheellinen, esimerkki oikeasta muodosta "0501234567".',
            u'Sähköpostiosoite on virheellinen, esimerkki oikeasta muodosta "matti@meikalainen.fi".',
            u'Katuosoite puuttuu.',
            u'Postinumero on virheellinen, esimerkki oikeasta muodosta "12345".',
            u'Postitoimipaikka puuttuu.',
        ], [e.string for e in errors])

    def test_valid_voting_process__invalid_information(self):
        # Fake the OpenID authentication.
        self.authenticate(u'http://example.com/id/matti.meikalainen')
        # Select a candidate.
        response = self.testapp.get('/valitse')
        response = response.click(href='/aanesta/1$')
        # Vote for the candidate.
        response.form[u'vote'] = u'1'
        response = response.form.submit()
        # Follow the redirect to the OpenID preference page.
        response = response.follow()

        # Leave the whole form empty.
        response.form[u'gsm'] = u' bad'
        response.form[u'email'] = u'invälid äddress'
        response.form[u'street'] = u'-'
        response.form[u'zipcode'] = u'1234a'
        response.form[u'city'] = u'-'
        response.form[u'use_open_identity'] = u'yes'

        response = response.form.submit()
        self.assertEquals('200 OK', response.status)

        error_container = response.html.findAll(id='pref-errors')[0]
        self.assertEquals(u'Antamissasi tiedoissa oli virheitä:', error_container.h3.string)
        errors = error_container.findAll('li')
        self.assertEquals([
            u'GSM-numero on virheellinen, esimerkki oikeasta muodosta "0501234567".',
            u'Sähköpostiosoite on virheellinen, esimerkki oikeasta muodosta "matti@meikalainen.fi".',
            u'Postinumero on virheellinen, esimerkki oikeasta muodosta "12345".',
        ], [e.string for e in errors])


class PagePermissionsTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.run import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG.copy()
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 20)))
    def test_permissions__unauthenticated_before_20110321(self):
        pages_allowed = (
            '',
            #'/openid-response',
            '/close-window',
        )
        pages_denied = (
            '/valitse',
            '/aanesta/0',
            '/valmis',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'Page {0} should be allowed.'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page, status=403)
            self.assertEquals('403 Forbidden', res.status, 'Page {0} should not be allowed.'.format(page))
            self.failUnless(u'<h2>Tämä sivusto vaatii tunnistaumisen</h2>'
                            in res.unicode_body)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 22)))
    def test_permissions__unauthenticated_after_20110321(self):
        pages_allowed = (
            '',
            #'/openid-response',
            '/close-window',
        )
        pages_denied = (
            '/valitse',
            '/aanesta/0',
            '/valmis',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'Page {0} should be allowed.'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page, status=403)
            self.assertEquals('403 Forbidden', res.status, 'Page {0} should not be allowed.'.format(page))
            self.failUnless(u'<h2>Tämä sivusto vaatii tunnistaumisen</h2>'
                            in res.unicode_body)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 28)))
    def test_permissions__unauthenticated_after_20110327(self):
        pages_allowed = (
            '',
            #'/openid-response',
            '/close-window',
        )
        pages_denied = (
            '/valitse',
            '/aanesta/0',
            '/valmis',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'Page {0} should be allowed.'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page, status=403)
            self.assertEquals('403 Forbidden', res.status, 'Page {0} should not be allowed.'.format(page))
            self.failUnless(u'<h2>Tämä sivusto vaatii tunnistaumisen</h2>'
                            in res.unicode_body)


class TestExceptionHandlers(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.run import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG.copy()
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    def test_not_found(self):
        response = self.testapp.get('/some-invalid-url', status=404)
        self.assertEquals('404 Not Found', response.status)
        # Assert we got our own 404 handler instead of the Pyramid default
        self.assertEquals(response.html.h1.text, u'Sivua ei löytynyt')


class LoginPageContentTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.run import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG.copy()
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 20, 23, 59, 59)))
    def test_login_page__before_20110321(self):
        res = self.testapp.get('/')
        self.assertEquals('200 OK', res.status)
        self.failUnless(u'<h2>Äänestää voit 21.3.2011 - 27.3.2011</h2>' in res.unicode_body)
        self.failIf(u'<form' in res.unicode_body, 'There should not be any form on the page.')

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 21, 0, 0, 1)))
    def test_login_page__after_20110321(self):
        res = self.testapp.get('/')
        self.assertEquals('200 OK', res.status)
        self.failIf(u'<h2>Äänestää voit 21.3.2011 - 27.3.2011</h2>' in res.unicode_body)
        self.failUnless(u'<form' in res.unicode_body, 'The login form should be on the page.')
        self.failUnless(u'id="identify-submit"' in res.unicode_body)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 27, 23, 59, 59)))
    def test_login_page__before_20110328(self):
        res = self.testapp.get('/')
        self.assertEquals('200 OK', res.status)
        self.failIf(u'<h2>Äänestää voit 21.3.2011 - 27.3.2011</h2>' in res.unicode_body)
        self.failUnless(u'<form' in res.unicode_body, 'The login form should be on the page.')
        self.failUnless(u'id="identify-submit"' in res.unicode_body)

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 28)))
    def test_login_page__after_20110327(self):
        res = self.testapp.get('/')
        self.assertEquals('200 OK', res.status)
        self.failUnless(u'<h2>Äänestää voit 21.3.2011 - 27.3.2011</h2>' in res.unicode_body)
        self.failIf(u'<form' in res.unicode_body, 'There should not be any form on the page.')
