# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalit.models import DBSession
from nuorisovaalit.tests import init_testing_db
from pyramid import testing
from pyramid.exceptions import Forbidden
from pyramid.testing import DummyRequest

import mock
import unittest2 as unittest


class TestMakeConsumer(unittest.TestCase):

    def setUp(self):
        init_testing_db()

    def tearDown(self):
        DBSession.remove()

    def test_make_consumer(self):
        from nuorisovaalit.views.login import make_consumer
        from openid.consumer.consumer import Consumer

        request = DummyRequest()
        consumer = make_consumer(request)

        # Assert we created a proper consumer
        self.failUnless(isinstance(consumer, Consumer))
        # Assert that the session in the consumer is bound to the request session.
        self.failUnless('openid' in request.session)
        self.failUnless(consumer.session is request.session['openid'])
        # Assert that the openid store is bound to the current SQLAlchemy session.
        self.failUnless(consumer.consumer.store.session is DBSession())


class TestLogin(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_login__no_identity_url(self):
        from nuorisovaalit.views.login import login
        from pyramid.url import route_url

        renderer = self.config.testing_add_template('templates/login.pt')
        self.config.add_route('login', '')
        request = DummyRequest()

        login(request)
        renderer.assert_(action_url=route_url('login', request),
                         message=None)

    @mock.patch('nuorisovaalit.views.login.openid_initiate')
    def test_login__valid_submission(self, openid_initiate):
        from nuorisovaalit.views.login import login

        self.config.add_route('login', '')
        self.config.add_settings({
            'nuorisovaalit.openid_provider': 'http://oid.fi',
        })
        request = DummyRequest(post={
            'identify': '1',
        })

        login(request)
        self.assertEquals((('http://oid.fi', request), {}), openid_initiate.call_args)

    def test_login__csrf_mismatch(self):
        from nuorisovaalit.views.login import login

        self.config.add_route('login', '')
        request = testing.DummyRequest()
        token = request.session.new_csrf_token()
        request.POST = {
            'identify': u'1',
            'username': u'john.doe',
            'password': u'thisiswrong',
            'csrf_token': u'invalid',
        }

        self.failIf(token == u'invalid')
        self.assertRaises(Forbidden, lambda: login(request))


class TestOpenIDResponse(unittest.TestCase):

    def setUp(self):
        from nuorisovaalit.views.system import renderer_globals_factory

        self.config = testing.setUp()
        self.config.set_renderer_globals_factory(renderer_globals_factory)
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    @mock.patch('nuorisovaalit.views.login.openid_failure')
    def test_openid_response__unknown_mode(self, openid_failure):
        from nuorisovaalit.views.login import openid_response

        request = DummyRequest()
        openid_response(request)
        self.failUnless(openid_failure.called)
        self.assertEquals(((request,), {}), openid_failure.call_args)

    def test_openid_response__cancel(self):
        from nuorisovaalit.views.login import openid_response

        request = DummyRequest({'openid.mode': 'cancel'})
        response = openid_response(request)

        self.assertEquals(response.status, '200 OK')
        self.failUnless('<h2>Tunnistautuminen keskeytettiin.</h2>' in response.body)

    @mock.patch('nuorisovaalit.views.login.make_consumer')
    @mock.patch('nuorisovaalit.views.login.openid_failure')
    def test_openid_response__unsuccessful(self, make_consumer, openid_failure):
        from nuorisovaalit.views.login import openid_response

        response = mock.Mock()
        response.status = None
        consumer = mock.Mock()
        consumer.complete.return_value
        make_consumer.return_value = consumer

        request = DummyRequest({'openid.mode': 'id_res'})
        openid_response(request)

        self.assertEquals(((request,), {}), openid_failure.call_args)

    @mock.patch('nuorisovaalit.views.login.openid_failure')
    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_response__invalid_user(self, make_consumer, openid_failure):
        from nuorisovaalit.views.login import openid_response
        from openid.consumer.consumer import SUCCESS

        response = mock.Mock()
        response.status = SUCCESS
        response.identity_url = u'http://matti.meikalainen.oid.fi'
        consumer = mock.Mock()
        consumer.complete.return_value = response
        make_consumer.return_value = consumer

        request = DummyRequest({'openid.mode': 'id_res'})
        openid_response(request)

        self.assertEquals(((request,), {}), openid_failure.call_args)

    @mock.patch('nuorisovaalit.views.login.openid_failure')
    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_response__success(self, make_consumer, openid_failure):
        from datetime import datetime
        from nuorisovaalit.models import District
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.login import openid_response
        from openid.consumer.consumer import SUCCESS
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        self.config.add_route('select', '/valitse')
        session = DBSession()

        # Add the needed records.
        district = District(u'district', 1)
        school = School(u'Mynämäen koulu', district)
        school.id = 1
        district.schools.append(school)
        session.add(district)

        openid_url = u'http://matti.meikalainen.oid.fi'
        # Add a voter to the session.
        session.add(Voter(openid_url, u'Matti', u'Meikäläinen', datetime.now(),
                          None, None, None, school))

        response = mock.Mock()
        response.status = SUCCESS
        response.identity_url = openid_url
        consumer = mock.Mock()
        consumer.complete.return_value = response
        make_consumer.return_value = consumer

        request = DummyRequest({'openid.mode': 'id_res'})
        response = openid_response(request)

        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('select', request), response.location)

    @mock.patch('nuorisovaalit.views.login.openid_failure')
    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_response__already_voted(self, make_consumer, openid_failure):
        from datetime import datetime
        from nuorisovaalit.models import District
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalit.views.login import openid_response
        from openid.consumer.consumer import SUCCESS
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        self.config.add_route('vote-finish', '/valmis')
        self.config.add_route('select', '/valitse')
        session = DBSession()

        # Add the needed records.
        district = District(u'district', 1)
        school = School(u'Mynämäen koulu', district)
        school.id = 1
        district.schools.append(school)
        session.add(district)

        openid_url = u'http://matti.meikalainen.oid.fi'
        # Add a voter to the session.
        voter = Voter(openid_url, u'Matti', u'Meikäläinen', datetime.now(),
                      None, None, None, school)
        session.add(voter)
        session.flush()
        # Add a vote for the user.
        session.add(VotingLog(voter.id))

        response = mock.Mock()
        response.status = SUCCESS
        response.identity_url = openid_url
        consumer = mock.Mock()
        consumer.complete.return_value = response
        make_consumer.return_value = consumer

        request = DummyRequest({'openid.mode': 'id_res'})
        response = openid_response(request)

        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('vote-finish', request), response.location)


class TestOpenIDInitiate(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_initiate__with_DiscoveryFailure(self, make_consumer):
        from nuorisovaalit.views.login import openid_initiate
        from openid.yadis.discover import DiscoveryFailure

        openid_url = u'http://example.com/id/john.doe'
        renderer = self.config.testing_add_template('templates/login_failed.pt')
        consumer = mock.Mock()
        consumer.begin.side_effect = DiscoveryFailure(None, None)
        make_consumer.return_value = consumer

        openid_initiate(openid_url, DummyRequest())

        renderer.assert_(message=u'Yhteydenotto OpenID-palvelimelle epäonnistui tilapäisesti.')

    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_initiate__with_KeyError(self, make_consumer):
        from nuorisovaalit.views.login import openid_initiate

        openid_url = u'http://example.com/id/john.doe'
        renderer = self.config.testing_add_template('templates/login_failed.pt')
        consumer = mock.Mock()
        consumer.begin.side_effect = KeyError()
        make_consumer.return_value = consumer

        openid_initiate(openid_url, DummyRequest())

        renderer.assert_(message=u'')

    @mock.patch('nuorisovaalit.views.login.make_consumer')
    def test_openid_initiate__successful(self, make_consumer):
        from nuorisovaalit.views.login import openid_initiate
        from webob.exc import HTTPFound

        self.config.add_route('openid-response', '/openid-response')

        openid_url = u'http://example.com/id/john.doe'
        redirect_url = u'http://example.com/some-url'
        consumer = mock.Mock()
        auth_request = mock.Mock()
        auth_request.redirectURL.return_value = redirect_url
        consumer.begin.return_value = auth_request
        make_consumer.return_value = consumer

        response = openid_initiate(openid_url, DummyRequest())

        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(redirect_url, response.location)
