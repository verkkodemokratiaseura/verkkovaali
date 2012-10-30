# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import datetime
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.tests import XlsTestCase
from nuorisovaalitadmin.tests import static_datetime
from webob import Response

import mock
import shutil
import tempfile
import time
import unittest
import webtest


def populate_db():
    from nuorisovaalit.models import District
    from nuorisovaalit.models import School
    from nuorisovaalitadmin.models import Group
    from nuorisovaalitadmin.models import User

    session = DBSession()
    district = District(u'Ylöjärven vaalipiiri', 1)
    session.add(district)
    session.flush()

    school = School(u'Äältö-yliopisto', district)
    session.add(school)
    session.flush()

    grp_admin = Group('admin', u'Admins')
    grp_school = Group('school', u'Schools')
    grp_allianssi = Group('allianssi', u'Allianssi')

    usr_admin = User('usr_admin', 'testi', u'Admin user', 'admin@example.org', True, school, grp_admin)
    usr_school = User('usr_school', 'testi', u'School user', 'school@example.org', True, school, grp_school)
    usr_allianssi = User('usr_allianssi', 'testi', u'Allianssi user', 'allianssi@example.org', True, school, grp_allianssi)

    session.add(usr_admin)
    session.add(usr_school)
    session.add(usr_allianssi)
    session.flush()

    usr_admin.groups.append(grp_admin)
    usr_school.groups.append(grp_school)
    usr_allianssi.groups.append(grp_allianssi)
    session.flush()


def login_as(app, username):
    """Login to the app with the given username.

    Returns the Response instance that the login page redirects to."""

    res = app.get('/login')
    csrf_token = res.form['csrf_token'].value
    res = app.post('/login', {
        'username': username,
        'password': u'testi',
        'form.submitted': u'Kirjaudu',
        'csrf_token': csrf_token,
    })
    assert '302 Found' == res.status
    assert 'http://localhost' == res.location

    # Follow the login redirect.
    res = res.follow()
    assert '200 OK' == res.status
    assert 'http://localhost' == res.request.url

    assert u'Olet kirjautunut sisään.' in res.unicode_body
    assert u'Kirjautuneena tunnuksella <strong>{0}</strong>'.format(username) \
           in res.unicode_body

    return res


TEST_CONFIG = {

    'populate_db': False,

    # sqlalchemy
    'sqlalchemy.url': 'sqlite://',
    'session.key': 'nuorisovaalitadmin',
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

    def test_User__no_school(self):
        from nuorisovaalitadmin.models import User

        user = User(u'user', u'sikret', u'Först Läst', None, school_or_id=None)
        self.assertTrue(user.school is None)


class NavigationContentTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalitadmin import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='xxx.x.x.x'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    def test_navigation__unauthenticated(self):
        res = self.testapp.get('/')
        self.assertEquals('302 Found', res.status)
        self.assertEquals('http://localhost/login', res.location)

    def test_navigation_login_page(self):
        res = self.testapp.get('/login')
        self.assertEquals('200 OK', res.status)

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
        ], [unicode(l) for l in nav_links])

    def test_navigation__allianssi(self):
        populate_db()
        res = login_as(self.testapp, u'usr_allianssi')

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
            u'<a class="allianssi" href="http://localhost/results-index">Allianssi</a>',
            u'<a class="voter-stats" href="http://localhost/voter-submission-stats">Äänestäjälistatilastot</a>',
            u'<a class="result-stats" href="http://localhost/result-submission-stats">Tuloslistatilastot</a>',
        ], [unicode(l) for l in nav_links])

    def test_navigation__admin(self):
        populate_db()
        res = login_as(self.testapp, u'usr_admin')

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
            u'<a class="submit-voters" href="http://localhost/submit-voters">Oppilastietojen lataaminen</a>',
            u'<a class="voter-list" href="http://localhost/voter-list">Äänestäjälista</a>',
            u'<a class="submit-results" href="http://localhost/submit-results">Tulosten lataaminen</a>',
            u'<a class="results" href="http://localhost/results">Tulokset</a>',
            u'<a class="allianssi" href="http://localhost/results-index">Allianssi</a>',
            u'<a class="voter-stats" href="http://localhost/voter-submission-stats">Äänestäjälistatilastot</a>',
            u'<a class="result-stats" href="http://localhost/result-submission-stats">Tuloslistatilastot</a>',
        ], [unicode(l) for l in nav_links])

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 14, 8, 59, 59)))
    def test_navigation__school_before_20110314_0900(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
            u'<a class="submit-voters" href="http://localhost/submit-voters">Oppilastietojen lataaminen</a>',
            u'<a class="voter-list disabled">Äänestäjälista</a>',
            u'<a class="submit-results disabled">Tulosten lataaminen</a>',
            u'<a class="results disabled">Tulokset</a>',
        ], [unicode(l) for l in nav_links])

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 28)))
    def test_navigation__school_at_20110328(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
            u'<a class="submit-voters disabled">Oppilastietojen lataaminen</a>',
            u'<a class="voter-list" href="http://localhost/voter-list">Äänestäjälista</a>',
            u'<a class="submit-results" href="http://localhost/submit-results">Tulosten lataaminen</a>',
            u'<a class="results disabled">Tulokset</a>',
        ], [unicode(l) for l in nav_links])

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 9)))
    def test_navigation__school_after_20110408(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        nav_links = res.html.findAll('nav')[0].findAll('a')
        self.assertEquals([
            u'<a class="frontpage" href="http://localhost/">Etusivu</a>',
            u'<a class="submit-voters disabled">Oppilastietojen lataaminen</a>',
            u'<a class="voter-list" href="http://localhost/voter-list">Äänestäjälista</a>',
            u'<a class="submit-results disabled">Tulosten lataaminen</a>',
            u'<a class="results disabled">Tulokset</a>',
        ], [unicode(l) for l in nav_links])


class PagePermissionTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalitadmin import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    def test_notfound(self):
        res = self.testapp.get('/some-page-that-is-not-found', expect_errors=True)
        self.assertEquals('404 Not Found', res.status)
        self.assertTrue(u'<h1>Hakemaasi sivua ei löytynyt</h1>' in res.unicode_body)

    def test_permissions__unauthenticated(self):
        pages_allowed = (
            '/login',
        )
        pages_denied = (
            '/',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status)
            self.assertEquals('http://localhost/login', res.location)

    def test_permissions__admin(self):
        populate_db()
        res = login_as(self.testapp, u'usr_admin')

        pages = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status)

    def test_permissions__allianssi(self):
        populate_db()
        res = login_as(self.testapp, u'usr_allianssi')

        pages_allowed = (
            '/',
            '/login',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 16, 11, 59, 59)))
    def test_permissions__school_before_20110316_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
        )
        pages_denied = (
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 16, 12)))
    def test_permissions__school_after_20110316_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 28)))
    def test_permissions__school_after_20110328(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 8, 23, 59, 59)))
    def test_permissions__school_before_20110409(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 12, 11, 59, 59)))
    def test_permissions__school_before_20110412_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/voter-list',
            '/voter-list.xls',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/submit-results',
            '/results-template.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results',
            '/results.xls',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 12, 12, 0)))
    def test_permissions__school_at_20110412_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/voter-list',
            '/voter-list.xls',
            '/results',
            '/results.xls',
        )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/submit-results',
            '/results-template.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)


class PagePermissionWithSkipCheckTest(unittest.TestCase):

    def setUp(self):
        from nuorisovaalitadmin import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG
        config['session.lock_dir'] = self.lock_dir
        config['nuorisovaalitadmin.skip_deadline_check'] = 'true'
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 16, 11, 59)))
    def test_permissions__school_before_20110316_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls'
            )
        pages_denied = (
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 12, 12, 01)))
    def test_permissions__school_after_20110412_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_school')

        pages_allowed = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls'
            )
        pages_denied = (
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 16, 11, 59)))
    def test_permissions__allianssi_before_20110316_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_allianssi')

        pages_allowed = (
            '/',
            '/login',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
            )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls'
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 12, 12, 01)))
    def test_permissions__allianssi_after_20110412_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_allianssi')

        pages_allowed = (
            '/',
            '/login',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
            )
        pages_denied = (
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls'
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))
        for page in pages_denied:
            res = self.testapp.get(page)
            self.assertEquals('302 Found', res.status, 'page {0} should not be allowed'.format(page))
            self.assertEquals('http://localhost/login', res.location)

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 3, 16, 11, 59)))
    def test_permissions__admin_before_20110316_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_admin')

        pages_allowed = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))

    @mock.patch('nuorisovaalitadmin.models.datetime', static_datetime(datetime(2011, 4, 12, 12, 01)))
    def test_permissions__admin_after_20110412_1200(self):
        populate_db()
        res = login_as(self.testapp, u'usr_admin')

        pages_allowed = (
            '/',
            '/login',
            '/submit-voters',
            '/voters-template.csv',
            '/voters-template.xls',
            '/voter-list',
            '/voter-list.xls',
            '/submit-results',
            '/results-template.xls',
            '/results',
            '/results.xls',
            '/voter-submission-stats',
            '/result-submission-stats',
            '/results-index',
            '/results-total.xls',
        )
        for page in pages_allowed:
            res = self.testapp.get(page)
            self.assertEquals('200 OK', res.status, 'page {0} should be allowed'.format(page))


class XlsSubmissionTest(XlsTestCase):

    def setUp(self):
        from nuorisovaalitadmin import main
        self.lock_dir = tempfile.mkdtemp()
        config = TEST_CONFIG
        config['session.lock_dir'] = self.lock_dir
        app = main({}, **config)
        self.testapp = webtest.TestApp(app, extra_environ=dict(REMOTE_ADDR='127.0.0.1'))

    def tearDown(self):
        DBSession.remove()
        shutil.rmtree(self.lock_dir)

    def test_voter_list_template__empty(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        populate_db()
        login_as(self.testapp, u'usr_school')

        # Initial conditions.
        session = DBSession()
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, session.query(VotingLog).count())

        res = self.testapp.get('/voter-list.xls')
        self.assertTrue(isinstance(res, Response))
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=nuorisovaalit2011-aanestajalista.xls',
                          res.headers['content-disposition'])

        self.assertXlsEquals(u'Nuorisovaalit 2011', [
            (u'Sukunimi', u'Etunimi', u'Syntymäaika', u'Äänestänyt'),
        ], res.body, skip_header=False, col_widths=(7000, 7000, 3500, 7000))

    def test_voter_list_template__with_voters(self):
        from nuorisovaalit.models import District
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        populate_db()
        login_as(self.testapp, u'usr_school')

        # Initial conditions.
        session = DBSession()
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, session.query(VotingLog).count())

        # Add voters.
        school = session.query(School).one()
        matti = Voter(u'http://matti.meikalainen.example.com',
                      u'Mätti',
                      u'Meikäläinen',
                      datetime(1995, 1, 25),
                      None,
                      None,
                      None,
                      school)
        maija = Voter(u'http://maija.mehilainen.example.com',
                      u'Mäijä',
                      u'Mehiläinen',
                      datetime(1996, 2, 26),
                      None,
                      None,
                      None,
                      school)
        session.add(matti)
        session.add(maija)
        session.flush()

        # Add voting logs.
        timestamp = time.mktime(datetime(2011, 2, 28, 23, 59, 58).timetuple())
        session.add(VotingLog(maija, timestamp))
        session.flush()

        # Add extra school and a voter to it to check that they do not
        # appear in the wrong place.
        district = session.query(District).one()
        school_other = School(u'Väärä koulu', district)
        session.add(school_other)
        session.flush()
        vaara = Voter(u'http://vaara.aanestaja.example.com',
                      u'Väärä',
                      u'Äänestäjä',
                      datetime(1994, 1, 21),
                      None,
                      None,
                      None,
                      school_other)
        session.add(vaara)
        session.add(Voter(u'http://kiero.oykkari.example.com',
                          u'Kierö',
                          u'Öykkäri',
                          datetime(1993, 3, 22),
                          None,
                          None,
                          None,
                          school_other))
        session.flush()
        timestamp_vaara = time.mktime(datetime(2010, 3, 30, 20, 58, 59).timetuple())
        session.add(VotingLog(vaara, timestamp_vaara))
        session.flush()

        res = self.testapp.get('/voter-list.xls')
        self.assertTrue(isinstance(res, Response))
        self.assertEquals('application/vnd.ms-excel',
                          res.headers['content-type'])
        self.assertEquals('attachment; filename=nuorisovaalit2011-aanestajalista.xls',
                          res.headers['content-disposition'])

        # Assert the Excel file contents so that it contains the
        # correct info and only the voters that are in the user's
        # school.
        self.assertXlsEquals(u'Nuorisovaalit 2011', [
            (u'Sukunimi', u'Etunimi', u'Syntymäaika', u'Äänestänyt'),
            (u'Mehiläinen', u'Mäijä', u'26.02.1996', u'28.02.2011 23:59:58'),
            (u'Meikäläinen', u'Mätti', u'25.01.1995', u''),
        ], res.body, skip_header=False, col_widths=(7000, 7000, 3500, 7000))
