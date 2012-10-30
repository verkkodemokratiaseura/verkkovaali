# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from pyramid import testing
from pyramid.exceptions import NotFound
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from webidentity.models import DBSession
from webidentity.tests import DUMMY_USER_ATTRIBUTES
from webidentity.tests import DummyOpenIdRequest
from webidentity.tests import _initTestingDB


import mock
import time
import unittest


class TestUtilities(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('openid_identity', '/id/{local_id}')

    def tearDown(self):
        testing.tearDown()

    def test_identity_url__without_vhost(self):
        from webidentity.views.oid import identity_url
        request = testing.DummyRequest()

        self.failIf('x-vhm-host' in request.headers)
        self.assertEquals(u'http://example.com/id/dokai',
            identity_url(request, 'dokai'))

    def test_identity_url__with_vhost(self):
        from webidentity.views.oid import identity_url
        request = testing.DummyRequest()
        request.headers['x-vhm-host'] = 'http://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'http://dokai.provider.com/',
            identity_url(request, 'dokai'))

    def test_identity_url__with_ssl_vhost(self):
        from webidentity.views.oid import identity_url
        request = testing.DummyRequest()
        request.headers['x-vhm-host'] = 'https://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'http://dokai.provider.com/',
            identity_url(request, 'dokai'))

    def test_extract_local_id__without_vhost(self):
        from webidentity.views.oid import extract_local_id
        request = testing.DummyRequest()

        self.assertEquals(u'dokai',
            extract_local_id(request, u'http://example.com/id/dokai'))

    def test_extract_local_id__with_vhost(self):
        from webidentity.views.oid import extract_local_id
        request = testing.DummyRequest()
        request.headers['x-vhm-host'] = 'http://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'dokai',
            extract_local_id(request, u'http://dokai.provider.com'))

    def test_extract_local_id__with_vhost_ssl(self):
        from webidentity.views.oid import extract_local_id
        request = testing.DummyRequest()
        request.headers['x-vhm-host'] = 'https://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'dokai',
            extract_local_id(request, u'http://dokai.provider.com'))

    def test_extract_local_id__no_match(self):
        from webidentity.views.oid import extract_local_id

        request = testing.DummyRequest()
        self.assertEquals(u'', extract_local_id(request, 'not_a_proper_identity'))

    def test_extract_local_id__relaxed_with_identity_wo_url_scheme(self):
        from webidentity.views.oid import extract_local_id
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'http',
        })
        request.headers['x-vhm-host'] = 'http://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'dokai',
            extract_local_id(request, u'dokai.provider.com', relaxed=True))

    def test_extract_local_id__relaxed_with_identity_wo_url_scheme_ssl(self):
        from webidentity.views.oid import extract_local_id
        request = testing.DummyRequest(environ={
            'wsgi.url_scheme': 'https',
        })
        request.headers['x-vhm-host'] = 'https://provider.com'

        self.failUnless('x-vhm-host' in request.headers)
        self.assertEquals(u'dokai',
            extract_local_id(request, u'dokai.provider.com', relaxed=True))

    def test_webob_response__redirect(self):
        from openid.server.server import WebResponse
        from webidentity.views.oid import webob_response
        from webob import Response

        request = testing.DummyRequest()
        webresponse = WebResponse(code=200, headers={
            'Location': 'http://rp.com/consumer?openid_response',
        })

        response = webob_response(webresponse, request)
        self.failUnless(isinstance(response, Response))
        self.assertEquals(response.status, '200 OK')
        self.assertEquals(response.body, '')
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://rp.com/consumer?openid_response',
            })

    def test_webob_response__form(self):
        from openid.server.server import WebResponse
        from webidentity.views.oid import webob_response
        from webob import Response

        request = testing.DummyRequest()
        webresponse = WebResponse(code=200, body='<form></form>')
        renderer = self.config.testing_add_template('templates/form_auto_submit.pt')

        response = webob_response(webresponse, request)
        # Check that the form from the OpenID response was embedded in the
        # site template
        renderer.assert_(openid_form_response=u'<form></form>')

        self.failUnless(isinstance(response, Response))
        self.assertEquals(response.status, '200 OK')
        self.assertEquals(response.body, '')
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            })


class OpenIDProviderTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.config.add_route('reset_password', '/reset-password')
        self.config.add_route('openid_confirm', '/confirm')
        self.config.add_route('openid_confirm_login', '/confirm-login')
        self.config.add_route('openid_confirm_login_success', '/confirm-login-success')
        self.config.add_route('openid_endpoint', '/openid')
        self.config.add_route('openid_identity', '/id/{local_id}')
        self.config.add_route('yadis_user', '/yadis/{local_id}')
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()
        DBSession.remove()

    def _makeOpenIdRequest(self, params, trust_root=''):
        """Returns a dummy OpenID request object."""
        from openid.message import Message

        return DummyOpenIdRequest(Message.fromOpenIDArgs(params), trust_root)

    def _makeCheckIdRequest(self, endpoint, params=None):
        """Returns a real CheckIdRequest."""
        from openidalchemy.store import AlchemyStore
        from openid.server import server

        session = DBSession()
        oidserver = server.Server(AlchemyStore(session), endpoint)
        request_params = {
            'openid.mode': 'checkid_setup',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.assoc_handle': '{assoc}{handle}',
            'openid.return_to': 'http://www.rp.com/openid',
            'openid.trust_root': 'http://www.rp.com',
            }
        if params is not None:
            request_params.update(params)

        return server.Decoder(oidserver).decode(request_params)

    def _urlParams(self, url):
        """Extracts the URL parameters and returns them in a dictionary."""
        from urllib import unquote
        from urlparse import parse_qsl
        from urlparse import urlparse

        return dict(parse_qsl(urlparse(unquote(url)).query))

    def test_identity__local_id_missing(self):
        from webidentity.views.oid import identity

        request = testing.DummyRequest()
        self.assertRaises(NotFound, lambda: identity(request))

    def test_identity__local_id_invalid(self):
        from webidentity.views.oid import identity

        request = testing.DummyRequest()
        request.matchdict['local_id'] = u'john.doe'

        self.assertRaises(NotFound, lambda: identity(request))

    def test_identity(self):
        from webidentity.models import User
        from webidentity.views.oid import identity

        user = User(u'john.doe', u'secret', u'john@doe.com')
        session = DBSession()
        session.add(user)

        self.assertEquals(1, session.query(User).filter_by(username=u'john.doe').count())
        request = testing.DummyRequest()
        request.matchdict['local_id'] = u'john.doe'

        self.assertEquals(identity(request), {
            'title': u'Identity page',
            'xrds_location': 'http://example.com/yadis/john.doe',
            'openid_endpoint': 'http://example.com/openid',
            'identity': 'http://example.com/id/john.doe'})

    def test_yadis__server(self):
        from webidentity.views.oid import yadis

        renderer = self.config.testing_add_template('templates/openid_yadis.pt')
        request = testing.DummyRequest()
        response = yadis(request)

        self.assertEquals(response.content_type, 'application/xrds+xml')
        renderer.assert_(uri='http://example.com/openid')
        renderer.assert_(service_types=[
            'http://specs.openid.net/auth/2.0/server',
            'http://openid.net/srv/ax/1.0',
            'http://openid.net/extensions/sreg/1.1'])

    def test_yadis__user(self):
        from webidentity.models import User
        from webidentity.views.oid import yadis

        user = User(u'john.doe', u'secret', u'john@doe.com')
        session = DBSession()
        session.add(user)

        renderer = self.config.testing_add_template('templates/openid_yadis.pt')
        request = testing.DummyRequest()
        request.matchdict['local_id'] = u'john.doe'
        response = yadis(request)

        self.assertEquals(response.content_type, 'application/xrds+xml')
        renderer.assert_(uri='http://example.com/openid')
        renderer.assert_(service_types=[
            'http://specs.openid.net/auth/2.0/signon',
            'http://openid.net/srv/ax/1.0',
            'http://openid.net/extensions/sreg/1.1'])

    def test_yadis__invalid_user(self):
        from webidentity.views.oid import yadis

        request = testing.DummyRequest()
        request.matchdict['local_id'] = u'john.doe'
        self.assertRaises(NotFound, lambda: yadis(request))

    def test_get_ax_attributes__anonymous(self):
        from webidentity.views.oid import get_ax_attributes

        request = testing.DummyRequest()
        self.assertEquals({}, get_ax_attributes(request))

    def test_get_ax_attributes__invalid_persona(self):
        from webidentity.models import User
        from webidentity.views.oid import get_ax_attributes

        self.config.testing_securitypolicy(userid=u'john.doe')
        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        request = testing.DummyRequest()
        request.params['persona'] = '1'

        self.assertEquals({}, get_ax_attributes(request))

    def test_get_ax_attributes(self):
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.models import UserAttribute
        from webidentity.views.oid import get_ax_attributes

        self.config.testing_securitypolicy(userid=u'john.doe')

        session = DBSession()
        user = User(u'john.doe', 'secret', 'john@doe.com')
        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        session.add(user)
        session.flush()

        request = testing.DummyRequest()
        request.params['persona'] = user.personas[0].id

        self.assertEquals(get_ax_attributes(request), {
            u'http://axschema.org/contact/email': u'john@doe.com',
            u'http://axschema.org/namePerson': u'Jöhn Döe',
            u'http://axschema.org/contact/city': u'Röswell',
            u'http://axschema.org/namePerson/first': u'Jöhn',
            u'http://axschema.org/namePerson/last': u'Döe',
            u'http://axschema.org/company/name': u'Äcme Inc'})

    def test_add_ax_response__invalid_request(self):
        from openid.message import OPENID2_NS
        from webidentity.views.oid import add_ax_response

        openid_request = self._makeOpenIdRequest({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            })

        openid_response = mock.Mock()
        add_ax_response(openid_request, openid_response, [])
        self.failIf(openid_response.addExtension.called)

    def test_add_ax_response__without_requested_fields(self):
        from openid.message import OPENID2_NS
        from openid.extensions import ax
        from webidentity.views.oid import add_ax_response

        openid_request = self._makeOpenIdRequest({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'realm': 'http://provider.com',
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.mode': 'fetch_request',
            })

        openid_response = mock.Mock()
        add_ax_response(openid_request, openid_response, DUMMY_USER_ATTRIBUTES)
        self.assertEquals(openid_response.addExtension.call_args[0][0].data, {})

    def test_add_ax_response(self):
        from openid.message import OPENID2_NS
        from openid.extensions import ax
        from webidentity.views.oid import add_ax_response

        openid_request = self._makeOpenIdRequest({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'realm': 'http://provider.com',
            'ns.ax': ax.AXMessage.ns_uri,
            'ax.mode': 'fetch_request',
            'ax.type.fullname': 'http://axschema.org/namePerson',
            'ax.type.email': 'http://axschema.org/contact/email',
            'ax.required': 'fullname',
            'ax.if_available': 'email',
            })

        openid_response = mock.Mock()
        add_ax_response(openid_request, openid_response, DUMMY_USER_ATTRIBUTES)
        self.assertEquals(openid_response.addExtension.call_args[0][0].data, {
            'http://axschema.org/namePerson': [u'Jöhn Döe'],
            'http://axschema.org/contact/email': [u'john@doe.com']})

    def test_add_sreg_response__invalid_request(self):
        from openid.message import OPENID2_NS
        from webidentity.views.oid import add_sreg_response

        openid_request = self._makeOpenIdRequest({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            })

        openid_response = mock.Mock()
        add_sreg_response(openid_request, openid_response, [])
        self.failIf(openid_response.addExtension.called)

    def test_add_sreg_response(self):
        from openid.extensions import sreg
        from openid.message import OPENID2_NS
        from webidentity.views.oid import add_sreg_response

        openid_request = self._makeOpenIdRequest({
            'mode': 'checkid_setup',
            'ns': OPENID2_NS,
            'realm': 'http://provider.com',
            'ns.sreg': sreg.ns_uri_1_1,
            'sreg.required': 'email',
            'sreg.optional': 'fullname',
            })

        openid_response = mock.Mock()
        add_sreg_response(openid_request, openid_response, DUMMY_USER_ATTRIBUTES)
        self.assertEquals(openid_response.addExtension.call_args[0][0].data, {
            'fullname': u'Jöhn Döe',
            'email': u'john@doe.com'})

    def test_confirm_login_success__invalid_openid_request(self):
        from webidentity.views.oid import confirm_login_success

        request = testing.DummyRequest()
        self.assertRaises(NotFound, lambda: confirm_login_success(request))

    @mock.patch('webidentity.views.oid.auth_decision')
    def test_confirm_login_success(self, auth_decision):
        from webidentity.models import CheckIdRequest
        from webidentity.views.oid import confirm_login_success

        request = testing.DummyRequest()
        request.environ['repoze.browserid'] = 'mybrowser'
        checkid_request = {'dummy': 'request'}
        session = DBSession()
        session.add(CheckIdRequest('mybrowser', checkid_request))

        sentinel = object()
        auth_decision.return_value = sentinel
        self.assertEquals(sentinel, confirm_login_success(request))
        # Check that the transient checkid request was removed.
        self.assertEquals(0, session.query(CheckIdRequest).count())
        # Check that the request was unpickled successfully.
        self.assertEquals(auth_decision.call_args[0][-1], {'dummy': 'request'})

    def test_confirm_login__no_submission(self):
        from webidentity.views.oid import confirm_login

        renderer = self.config.testing_add_template('templates/openid_confirm_login.pt')
        request = testing.DummyRequest()
        response = confirm_login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8'})
        renderer.assert_(login_name='')
        renderer.assert_(action_url='http://example.com/confirm-login')

    def test_confirm_login__invalid_csrf_token(self):
        from pyramid.exceptions import Forbidden
        from webidentity.views.oid import confirm_login

        self.config.testing_add_template('templates/openid_confirm_login.pt')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        request = testing.DummyRequest(post={
            'form.submitted': '1',
        })
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = 'invalid {0}'.format(csrf_token)

        self.assertRaises(Forbidden, lambda: confirm_login(request))

    def test_confirm_login__invalid_user(self):
        from webidentity.views.oid import confirm_login

        renderer = self.config.testing_add_template('templates/openid_confirm_login.pt')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        request = testing.DummyRequest(post={
            'form.submitted': '1',
        })
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token
        response = confirm_login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8'})
        self.assertEquals(request.session.pop_flash(),
            [u'Failed to log in, please try again.'])
        renderer.assert_(login_name='')
        renderer.assert_(action_url='http://example.com/confirm-login')

    def test_confirm_login__invalid_password(self):
        from webidentity.models import User
        from webidentity.views.oid import confirm_login

        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        renderer = self.config.testing_add_template('templates/openid_confirm_login.pt')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        request = testing.DummyRequest(post={
            'form.submitted': '1',
            'login': 'john.doe',
            'password': 'invalid',
        })
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token
        response = confirm_login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8'})
        self.assertEquals(request.session.pop_flash(),
            [u'Failed to log in, please try again.'])
        renderer.assert_(login_name='')
        renderer.assert_(action_url='http://example.com/confirm-login')

    @mock.patch('webidentity.views.oid.remember')
    def test_confirm_login(self, remember):
        from webidentity.models import User
        from webidentity.views.oid import confirm_login

        remember.return_value = [('X-Login', 'john.doe')]
        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        request = testing.DummyRequest(post={
            'form.submitted': '1',
            'login': 'john.doe',
            'password': 'secret',
        })
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token
        response = confirm_login(request)
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'X-Login': 'john.doe',
            'Content-Type': 'text/html; charset=UTF-8',
            'Location': 'http://example.com/confirm-login-success'})

    def test_confirm__anonymous(self):
        from webidentity.views.oid import confirm

        request = testing.DummyRequest()
        response = confirm(request)
        self.assertEquals(response.status, '400 Bad Request')

    def test_confirm__no_submission(self):
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        request = testing.DummyRequest()
        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))

        response = confirm(request)
        self.failIf(authenticated_user(request) is None)
        self.assertEquals(response.status, '400 Bad Request')

    def test_confirm__invalid_csrf_token(self):
        from pyramid.exceptions import Forbidden
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        request = testing.DummyRequest(params={
            'form.submitted': '1',
        })
        token = request.session.new_csrf_token()
        request.POST['csrf_token'] = 'invalid {0}'.format(token)

        self.failIf(authenticated_user(request) is None)
        self.assertRaises(Forbidden, lambda: confirm(request))

    def test_confirm__invalid_checkid_request(self):
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        request = testing.DummyRequest(params={
            'form.submitted': '1',
        })
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        response = confirm(request)
        self.failIf(authenticated_user(request) is None)
        self.assertEquals(response.status, '400 Bad Request')

    def test_confirm__accept__no_previous_visit__no_persona(self):
        from pyramid.url import route_url
        from urlparse import parse_qsl
        from urlparse import urlparse
        from webidentity.models import Activity
        from webidentity.models import CheckIdRequest
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        request = testing.DummyRequest(
            params={
                'form.submitted': '1',
                'accept': 'yes'},
            environ={
                'repoze.browserid': 'mybrowser'},
            cookies={
                'auth_tkt': 'authcookie'})
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        openid_request = self._makeCheckIdRequest(route_url('openid_endpoint', request))
        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        session = DBSession()
        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        session.add(CheckIdRequest('mybrowser', openid_request))
        self.assertEquals(1, session.query(CheckIdRequest).count())

        response = confirm(request)
        # Check that the checkid request was removed
        self.assertEquals(0, session.query(CheckIdRequest).count())
        self.failIf(authenticated_user(request) is None)
        self.assertEquals(response.status, '302 Found')
        # Check that we are responding correctly.
        redirect_url = urlparse(response.headers.get('location'))
        redirect_query = dict(parse_qsl(redirect_url.query))
        self.assertEquals(redirect_url.scheme, 'http')
        self.assertEquals(redirect_url.netloc, 'www.rp.com')
        self.assertEquals(redirect_url.path, '/openid')
        self.assertEquals(redirect_query['openid.identity'], 'http://example.com/id/john.doe')
        self.assertEquals(redirect_query['openid.mode'], 'id_res')
        self.assertEquals(redirect_query['openid.return_to'], 'http://www.rp.com/openid')
        # Check that we logged the occurrence
        entry = session.query(Activity).all()[-1]
        self.assertEquals('http://www.rp.com', entry.url)
        # The authentication request was authorized for a single use
        self.assertEquals(Activity.AUTHORIZE_ONCE, entry.action)
        # The visit was persisted
        visit = session.query(User).get(1).visited_sites[0]
        self.assertEquals(visit.trust_root, 'http://www.rp.com')
        self.assertEquals(visit.remember, False)
        self.assertEquals(visit.persona, None)

    def test_confirm__accept__no_previous_visit__with_persona(self):
        from pyramid.url import route_url
        from urlparse import parse_qsl
        from urlparse import urlparse
        from webidentity.models import Activity
        from webidentity.models import CheckIdRequest
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        session = DBSession()
        user = User(u'john.doe', 'secret', 'john@doe.com')
        user.personas.append(Persona(u'My personä'))
        session.add(user)
        session.flush()

        request = testing.DummyRequest(
            params={
                'form.submitted': '1',
                'accept': 'yes',
                'persona': str(user.personas[0].id)},
            environ={
                'repoze.browserid': 'mybrowser'},
            cookies={
                'auth_tkt': 'authcookie'})
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        openid_request = self._makeCheckIdRequest(route_url('openid_endpoint', request))
        session.add(CheckIdRequest('mybrowser', openid_request))
        self.assertEquals(1, session.query(CheckIdRequest).count())

        response = confirm(request)
        # Check that the checkid request was removed
        self.assertEquals(0, session.query(CheckIdRequest).count())
        self.failIf(authenticated_user(request) is None)
        self.assertEquals(response.status, '302 Found')
        # Check that we are responding correctly.
        redirect_url = urlparse(response.headers.get('location'))
        redirect_query = dict(parse_qsl(redirect_url.query))
        self.assertEquals(redirect_url.scheme, 'http')
        self.assertEquals(redirect_url.netloc, 'www.rp.com')
        self.assertEquals(redirect_url.path, '/openid')
        self.assertEquals(redirect_query['openid.identity'], 'http://example.com/id/john.doe')
        self.assertEquals(redirect_query['openid.mode'], 'id_res')
        self.assertEquals(redirect_query['openid.return_to'], 'http://www.rp.com/openid')
        # Check that we logged the occurrence
        entry = session.query(Activity).all()[-1]
        self.assertEquals('http://www.rp.com', entry.url)
        # The authentication request was authorized for a single use
        self.assertEquals(Activity.AUTHORIZE_ONCE, entry.action)
        # The visit was persisted
        visit = session.query(User).get(1).visited_sites[0]
        self.assertEquals(visit.trust_root, 'http://www.rp.com')
        self.failIf(visit.remember)
        # Check the correct persona was referenced
        self.assertEquals(visit.persona.name, u'My personä')

    def test_confirm__accept__remember(self):
        from pyramid.url import route_url
        from urlparse import parse_qsl
        from urlparse import urlparse
        from webidentity.models import Activity
        from webidentity.models import CheckIdRequest
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        session = DBSession()
        user = User(u'john.doe', 'secret', 'john@doe.com')
        user.personas.append(Persona(u'My personä'))
        session.add(user)
        session.flush()

        request = testing.DummyRequest(
            params={
                'form.submitted': '1',
                'accept': 'yes',
                'remember': 'yes',
                'persona': str(user.personas[0].id)},
            environ={
                'repoze.browserid': 'mybrowser'},
            cookies={
                'auth_tkt': 'authcookie'})
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        openid_request = self._makeCheckIdRequest(route_url('openid_endpoint', request))
        session.add(CheckIdRequest('mybrowser', openid_request))
        self.assertEquals(1, session.query(CheckIdRequest).count())

        response = confirm(request)
        # Check that the checkid request was removed
        self.assertEquals(0, session.query(CheckIdRequest).count())
        self.failIf(authenticated_user(request) is None)
        self.assertEquals(response.status, '302 Found')
        # Check that we are responding correctly.
        redirect_url = urlparse(response.headers.get('location'))
        redirect_query = dict(parse_qsl(redirect_url.query))
        self.assertEquals(redirect_url.scheme, 'http')
        self.assertEquals(redirect_url.netloc, 'www.rp.com')
        self.assertEquals(redirect_url.path, '/openid')
        self.assertEquals(redirect_query['openid.identity'], 'http://example.com/id/john.doe')
        self.assertEquals(redirect_query['openid.mode'], 'id_res')
        self.assertEquals(redirect_query['openid.return_to'], 'http://www.rp.com/openid')
        # Check that we logged the occurrence
        entry = session.query(Activity).all()[-1]
        self.assertEquals('http://www.rp.com', entry.url)
        # The authentication request was authorized for later use as well
        self.assertEquals(Activity.AUTHORIZE, entry.action)
        # The visit was persisted
        visit = session.query(User).get(1).visited_sites[0]
        self.assertEquals(visit.trust_root, 'http://www.rp.com')
        self.failUnless(visit.remember)
        # Check the correct persona was referenced
        self.assertEquals(visit.persona.name, u'My personä')

    def test_confirm__deny(self):
        from pyramid.url import route_url
        from webidentity.models import Activity
        from webidentity.models import CheckIdRequest
        from webidentity.models import User
        from webidentity.views.oid import confirm
        from webidentity.views.user import authenticated_user

        self.config.testing_securitypolicy(userid=u'john.doe')
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = testing.DummyRequest(
            params={
                'form.submitted': '1'},
            environ={
                'repoze.browserid': 'mybrowser'},
            cookies={
                'auth_tkt': 'authcookie'})
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        session = DBSession()
        openid_request = self._makeCheckIdRequest(route_url('openid_endpoint', request))

        session.add(User(u'john.doe', 'secret', 'john@doe.com'))
        session.add(CheckIdRequest('mybrowser', openid_request))
        self.assertEquals(1, session.query(CheckIdRequest).count())

        response = confirm(request)
        # Check that the checkid request was removed
        self.assertEquals(0, session.query(CheckIdRequest).count())
        self.failIf(authenticated_user(request) is None)
        # Check that the OpenID response was negative
        self.assertEquals(dict(response.headers), {
            'Content-Length': '0',
            'Content-Type': 'text/html; charset=UTF-8',
            'location': 'http://www.rp.com/openid?openid.mode=cancel'})
        self.assertEquals(response.status, '302 Found')
        # Check that we logged the occurrence
        entry = session.query(Activity).all()[-1]
        self.assertEquals('http://www.rp.com', entry.url)
        self.assertEquals(Activity.DENY, entry.action)

    def test_endpoint__openid_protocol_error(self):
        from webidentity.views.oid import endpoint

        request = testing.DummyRequest(params={
            'openid.ns': '<invalid namespace>',
            'openid.mode': 'checkid_setup',
        })
        response = endpoint(request)
        self.assertEquals(response.status, '400 Bad Request')

    def test_endpoint__empty_request(self):
        from webidentity.views.oid import endpoint

        request = testing.DummyRequest()
        response = endpoint(request)
        self.assertEquals(response.status, '400 Bad Request')

    def test_endpoint__checkid_immediate_anonymous(self):
        from webidentity.views.oid import endpoint

        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://john.doe.example.com/',
            'openid.identity': 'http://john.doe.example.com',
            'openid.mode': 'checkid_immediate',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        response = endpoint(request)
        self.assertEquals(response.status, '302 Found')
        self.assertEquals(self._urlParams(response.location), {
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'janrain_nonce': '2010-10-28T06:19:18ZaIriYk',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            'openid.realm': 'http://www.rp.com',
            'openid.claimed_id': 'http://john.doe.example.com/',
            'openid.mode': 'checkid_setup',
            'openid.user_setup_url': 'http://example.com/openid?openid.assoc_handle={HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.identity': 'http://john.doe.example.com'})

    @mock.patch('webidentity.views.oid.auth_decision')
    def test_endpoint__checkid_setup_anonymous(self, auth_decision):
        from webidentity.views.oid import endpoint

        auth_decision.return_value = mock.sentinel.return_value
        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://john.doe.example.com/',
            'openid.identity': 'http://john.doe.example.com',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        response = endpoint(request)
        # Check that the user was asked to authenticate the request.
        self.assertEquals(response, mock.sentinel.return_value)

    @mock.patch('webidentity.views.oid.auth_decision')
    def test_endpoint__checkid_authorized_with_identity_mismatch(self, auth_decision):
        from webidentity.views.oid import endpoint
        from pyramid.security import authenticated_userid

        self.config.testing_securitypolicy(userid=u'jane.doe')
        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        auth_decision.return_value = mock.sentinel.return_value
        response = endpoint(request)

        self.assertEquals(u'jane.doe', authenticated_userid(request))
        # Check that the user was asked to authenticate the request.
        self.assertEquals(response, mock.sentinel.return_value)

    @mock.patch('webidentity.views.oid.auth_decision')
    def test_endpoint__checkid_authorized_wo_previous_visit(self, auth_decision):
        from webidentity.views.oid import endpoint
        from pyramid.security import authenticated_userid

        self.config.testing_securitypolicy(userid=u'john.doe')
        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        auth_decision.return_value = mock.sentinel.return_value
        response = endpoint(request)

        self.assertEquals(u'john.doe', authenticated_userid(request))
        # Check that the user was asked to authenticate the request.
        self.assertEquals(response, mock.sentinel.return_value)

    @mock.patch('webidentity.views.oid.auth_decision')
    def test_endpoint__checkid_authorized_with_previous_visit_no_remember(self, auth_decision):
        from pyramid.security import authenticated_userid
        from webidentity.models import User
        from webidentity.models import VisitedSite
        from webidentity.views.oid import endpoint

        self.config.testing_securitypolicy(userid=u'john.doe')
        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.visited_sites.append(VisitedSite('http://www.rp.com'))
        session.add(user)
        session.flush()
        self.failIf(user.visited_sites[0].remember)

        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        auth_decision.return_value = mock.sentinel.return_value
        response = endpoint(request)

        self.assertEquals(u'john.doe', authenticated_userid(request))
        # Check that the user was asked to authenticate the request.
        self.assertEquals(response, mock.sentinel.return_value)

    def test_endpoint__checkid_authorized_with_remembered_visit_wo_persona(self):
        from pyramid.security import authenticated_userid
        from webidentity.models import User
        from webidentity.models import VisitedSite
        from webidentity.views.oid import endpoint

        self.config.testing_securitypolicy(userid=u'john.doe')
        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.visited_sites.append(VisitedSite('http://www.rp.com', True))
        session.add(user)
        session.flush()
        self.failUnless(user.visited_sites[0].remember)

        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            })
        response = endpoint(request)

        self.assertEquals(u'john.doe', authenticated_userid(request))
        self.assertEquals(response.status, '302 Found')
        response_params = self._urlParams(response.location)
        # Check that the dynamic values are present
        self.failIf(response_params.pop('openid.invalidate_handle', None) is None)
        self.failIf(response_params.pop('openid.sig', None) is None)
        self.failIf(response_params.pop('openid.assoc_handle', None) is None)
        self.failIf(response_params.pop('openid.response_nonce', None) is None)
        # Check for a positive OpenID response
        self.assertEquals(response_params, {
            'openid.op_endpoint': 'http://example.com/openid',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'janrain_nonce': '2010-10-28T06:19:18ZaIriYk',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.mode': 'id_res',
            'openid.signed': 'assoc_handle,claimed_id,identity,invalidate_handle,mode,ns,op_endpoint,response_nonce,return_to,signed',
            'openid.identity': 'http://example.com/id/john.doe'})

    def test_endpoint__checkid_authorized_with_remembered_visit_with_persona(self):
        from pyramid.security import authenticated_userid
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.models import UserAttribute
        from webidentity.models import VisitedSite
        from webidentity.views.oid import endpoint

        self.config.testing_securitypolicy(userid=u'john.doe')
        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        session.add(user)
        session.flush()
        site = VisitedSite('http://www.rp.com', True)
        site.persona_id = user.personas[0].id
        user.visited_sites.append(site)
        session.flush()
        self.failUnless(user.visited_sites[0].remember)

        request = testing.DummyRequest(params={
            'openid.assoc_handle': '{HMAC-SHA1}{4cc915e6}{c3PH5Q==}',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'checkid_setup',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.realm': 'http://www.rp.com',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            'openid.ns.ax': 'http://openid.net/srv/ax/1.0',
            'openid.ax.mode': 'fetch_request',
            'openid.ax.type.fullname': 'http://axschema.org/namePerson',
            'openid.ax.type.email': 'http://axschema.org/contact/email',
            'openid.ax.required': 'fullname',
            'openid.ax.if_available': 'email',
            'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1',
            'openid.sreg.required': 'email',
            'openid.sreg.optional': 'fullname',
            })
        response = endpoint(request)

        self.assertEquals(u'john.doe', authenticated_userid(request))
        self.assertEquals(response.status, '302 Found')
        response_params = self._urlParams(response.location)
        # Check that the dynamic values are present
        self.failIf(response_params.pop('openid.invalidate_handle', None) is None)
        self.failIf(response_params.pop('openid.sig', None) is None)
        self.failIf(response_params.pop('openid.assoc_handle', None) is None)
        self.failIf(response_params.pop('openid.response_nonce', None) is None)
        # Check for a positive OpenID response with both SReg and AX extensions
        self.assertEquals(response_params, {
            'janrain_nonce': '2010-10-28T06:19:18ZaIriYk',
            'openid.ax.count.email': '1',
            'openid.ax.count.fullname': '1',
            'openid.ax.mode': 'fetch_response',
            'openid.ax.type.email': 'http://axschema.org/contact/email',
            'openid.ax.type.fullname': 'http://axschema.org/namePerson',
            'openid.ax.value.email.1': 'john@doe.com',
            'openid.ax.value.fullname.1': 'Jöhn Döe',
            'openid.claimed_id': 'http://example.com/id/john.doe',
            'openid.identity': 'http://example.com/id/john.doe',
            'openid.mode': 'id_res',
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.ns.ax': 'http://openid.net/srv/ax/1.0',
            'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1',
            'openid.op_endpoint': 'http://example.com/openid',
            'openid.return_to': 'http://www.rp.com/return?janrain_nonce=2010-10-28T06:19:18ZaIriYk',
            'openid.signed': 'assoc_handle,ax.count.email,ax.count.fullname,ax.mode,ax.type.email,ax.type.fullname,ax.value.email.1,ax.value.fullname.1,claimed_id,identity,invalidate_handle,mode,ns,ns.ax,ns.sreg,op_endpoint,response_nonce,return_to,signed,sreg.email,sreg.fullname',
            'openid.sreg.email': 'john@doe.com',
            'openid.sreg.fullname': 'Jöhn Döe'})

    def test_endpoint__other_modes(self):
        from webidentity.views.oid import endpoint

        request = testing.DummyRequest(params={
            'openid.ns': 'http://specs.openid.net/auth/2.0',
            'openid.mode': 'associate',
            'openid.assoc_type': 'HMAC-SHA1',
            'openid.session_type': 'no-encryption',
        })
        response = endpoint(request)
        self.assertEquals(response.status, '200 OK')
        response_params = dict(line.split(':', 1) for line in response.body.splitlines() if line.strip())
        self.assertEquals(set(response_params.keys()), set([
            'assoc_handle', 'mac_key', 'session_type', 'expires_in', 'assoc_type', 'ns']))

    def test_auth_decision__scenario_1(self):
        from webidentity.models import User
        from webidentity.views.oid import auth_decision

        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        })
        self.config.testing_securitypolicy(userid=u'john.doe')

        renderer = self.config.testing_add_template('templates/openid_confirm.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        # Check that we have provided the correct identity url
        renderer.assert_(identity='http://example.com/id/john.doe')

    def test_auth_decision__scenario_2(self):
        from webidentity.models import User
        from webidentity.views.oid import auth_decision

        session = DBSession()
        session.add(User(u'john.doe', u'secret', u'john@doe.com'))
        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid')
        self.config.testing_securitypolicy(userid=u'john.doe')

        renderer = self.config.testing_add_template('templates/openid_confirm.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        # Check that we have provided the correct identity url
        renderer.assert_(identity='http://example.com/id/john.doe')

    def test_auth_decision__scenario_3(self):
        from webidentity.models import User
        from webidentity.views.oid import auth_decision

        session = DBSession()
        session.add(User(u'jane.doe', u'secret', u'jane@doe.com'))
        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid')
        self.config.testing_securitypolicy(userid=u'jane.doe')

        self.assertRaises(NotImplementedError, lambda: auth_decision(request, openid_request))

    def test_auth_decision__scenario_4(self):
        from webidentity.views.oid import auth_decision

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        })
        renderer = self.config.testing_add_template('templates/openid_confirm_login.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        renderer.assert_(action_url='http://example.com/confirm-login')
        # Check that we have no username because the RP asked us to select one.
        renderer.assert_(login_name=None)

    def test_auth_decision__scenario_5(self):
        from webidentity.views.oid import auth_decision

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid')
        renderer = self.config.testing_add_template('templates/openid_confirm_login.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        renderer.assert_(action_url='http://example.com/confirm-login')
        # Check that we have matched a local user to the identity url.
        renderer.assert_(login_name=u'john.doe')

    @mock.patch('webidentity.views.oid.random')
    def test_auth_decision__cleanup_old_checkid_requests(self, mock_random):
        from webidentity.models import CheckIdRequest
        from webidentity.views.oid import auth_decision

        # Mock the random.randint() function to always return a value that
        # will result in openid request garbage collection.
        mock_random.randint.return_value = 9
        session = DBSession()
        session.add(CheckIdRequest('<somebrowser>', 'foobar', int(time.time()) - 7200))
        session.flush()

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        })
        self.config.testing_add_template('templates/openid_confirm_login.pt')

        self.assertEquals(1, session.query(CheckIdRequest).count())
        auth_decision(request, openid_request)
        self.assertEquals(1, session.query(CheckIdRequest).count())
        # Check that the only request is for the new one.
        self.assertEquals(session.query(CheckIdRequest).all()[0].key, '<mybrowser>')

    def test_auth_decision__overwrite_existing_checkid_request(self):
        from webidentity.models import CheckIdRequest
        from webidentity.views.oid import auth_decision

        session = DBSession()
        # Create an existing check id request.
        session.add(CheckIdRequest('<mybrowser>', 'foobar'))
        session.flush()

        self.assertEquals(1, session.query(CheckIdRequest).count())
        cidrequest = session.query(CheckIdRequest).all()[-1]
        cid_issued = cidrequest.issued

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        })
        self.config.testing_add_template('templates/openid_confirm_login.pt')

        # The issued timestamp has one second resolution so we need to sleep
        # to see a difference.
        time.sleep(1)
        auth_decision(request, openid_request)
        self.assertEquals(1, session.query(CheckIdRequest).count())
        # Check that the data on the existing check id request was updated.
        cidrequest = session.query(CheckIdRequest).all()[0]
        self.assertEquals(cidrequest.key, '<mybrowser>')
        self.assertEquals(cidrequest.request, openid_request)
        self.failUnless(cidrequest.issued > cid_issued)

    def test_auth_decision__sreg_request(self):
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.models import UserAttribute
        from webidentity.views.oid import auth_decision

        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        user.personas.append(
            Persona(u'Reversed persönä', attributes=[
                UserAttribute(type_uri, ''.join(reversed(value)))
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        session.add(user)

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.ns.sreg': 'http://openid.net/extensions/sreg/1.1',
            'openid.sreg.required': 'email',
            'openid.sreg.optional': 'fullname',
        })
        self.config.testing_securitypolicy(userid=u'john.doe')

        renderer = self.config.testing_add_template('templates/openid_confirm.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        # Check that we have provided the correct identity url
        renderer.assert_(identity='http://example.com/id/john.doe')
        renderer.assert_(personas=[
            {'attributes': [
                {'value': u'john@doe.com', 'type_uri': u'http://axschema.org/contact/email'},
                {'value': u'Jöhn Döe', 'type_uri': u'http://axschema.org/namePerson'}],
             'missing': set(),
             'id': 1,
             'name': u'Test persönä'},
            {'attributes': [
                {'value': u'moc.eod@nhoj', 'type_uri': u'http://axschema.org/contact/email'},
                {'value': u'eöD nhöJ', 'type_uri': u'http://axschema.org/namePerson'}],
                'missing': set(),
             'id': 2,
             'name': u'Reversed persönä'}])

    def test_auth_decision__ax_request(self):
        from webidentity.models import Persona
        from webidentity.models import User
        from webidentity.models import UserAttribute
        from webidentity.views.oid import auth_decision

        session = DBSession()
        user = User(u'john.doe', u'secret', u'john@doe.com')
        user.personas.append(
            Persona(u'Test persönä', attributes=[
                UserAttribute(type_uri, value)
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        user.personas.append(
            Persona(u'Reversed persönä', attributes=[
                UserAttribute(type_uri, ''.join(reversed(value)))
                for type_uri, value
                in DUMMY_USER_ATTRIBUTES.iteritems()]))
        session.add(user)

        request = testing.DummyRequest(environ={'repoze.browserid': '<mybrowser>'})
        openid_request = self._makeCheckIdRequest('http://provider.com/openid', {
            'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
            'openid.ns.ax': 'http://openid.net/srv/ax/1.0',
            'openid.ax.mode': 'fetch_request',
            'openid.ax.type.fullname': 'http://axschema.org/namePerson',
            'openid.ax.type.email': 'http://axschema.org/contact/email',
            'openid.ax.required': 'fullname',
            'openid.ax.if_available': 'email',
        })
        self.config.testing_securitypolicy(userid=u'john.doe')

        renderer = self.config.testing_add_template('templates/openid_confirm.pt')

        response = auth_decision(request, openid_request)
        self.assertEquals(response.status, '200 OK')
        # Check that we have provided the correct identity url
        renderer.assert_(identity='http://example.com/id/john.doe')
        renderer.assert_(personas=[
            {'attributes': [
                {'value': u'john@doe.com', 'type_uri': u'http://axschema.org/contact/email'},
                {'value': u'Jöhn Döe', 'type_uri': u'http://axschema.org/namePerson'}],
             'missing': set(),
             'id': 1,
             'name': u'Test persönä'},
            {'attributes': [
                {'value': u'moc.eod@nhoj', 'type_uri': u'http://axschema.org/contact/email'},
                {'value': u'eöD nhöJ', 'type_uri': u'http://axschema.org/namePerson'}],
                'missing': set(),
             'id': 2,
             'name': u'Reversed persönä'}])
