# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""OpendID functionality.
"""
from openid.consumer import discover
from openid.extensions import ax
from openid.extensions import sreg
from openid.server import server
from openid.urinorm import urinorm
from openidalchemy.store import AlchemyStore
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.renderers import render_to_response
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.url import route_url
from webidentity.i18n import WebIdentityMessageFactory as _
from webidentity.models import Activity
from webidentity.models import CheckIdRequest
from webidentity.models import DBSession
from webidentity.models import Persona
from webidentity.models import User
from webidentity.models import VisitedSite
from webidentity.views import disable_caching
from webidentity.views.user import authenticated_user
from webidentity.views.user import log_activity
from webob import Response
from webob.exc import HTTPBadRequest
from webob.exc import HTTPFound

import logging
import random
import re
import time
import urlparse

# Mapping of Attribute Exchange 1.0 type_uris to Simple Registration 1.1 fields.
AX_TO_SREG = {
    'http://axschema.org/namePerson/friendly': 'nickname',
    'http://axschema.org/contact/email': 'email',
    'http://axschema.org/namePerson': 'fullname',
    'http://axschema.org/birthDate': 'dob',
    'http://axschema.org/person/gender': 'gender',
    'http://axschema.org/contact/postalCode/home': 'postcode',
    'http://axschema.org/contact/country/home': 'country',
    'http://axschema.org/pref/language': 'language',
    'http://axschema.org/pref/timezone': 'timezone',
}
# Mapping of Simple Registration 1.1 fields to Attribute Exchange 1.0 type_uris.
SREG_TO_AX = dict((field, type_uri) for type_uri, field in AX_TO_SREG.iteritems())


def identity_url(request, local_id):
    """Returns an OpenID identity URL for the given local identifier."""

    if 'x-vhm-host' in request.headers:
        # We are using repoze.vhm and a front-end web server to control the
        # URLs to the application.
        url = urlparse.urlparse(request.headers['x-vhm-host'])
        return urinorm(u'http://{local_id}.{domain}'.format(
            local_id=local_id,
            domain=url.netloc))
    else:
        # No special virtual hosting is taking place so we can use the route
        # url for the identity page directly.
        return urinorm(route_url('openid_identity', request, local_id=local_id))


def extract_local_id(request, id_url, relaxed=False):
    """Given an OpenID identity URL attempts to return the username of the
    local user that the identity URL refers to.

    If relaxed=True, the id_url may omit the URL scheme and the currently
    active URL scheme will be assumed.

    Returns an empty string if fails to extract the username.
    """
    # Generate a regexp to extract the username from the identity url
    USERNAME_RE = re.compile(urinorm(identity_url(request, '_re_marker_'))\
                    .replace('_re_marker_', '([^/\s]+)')\
                    .replace('https', 'http'))
    try:
        match = USERNAME_RE.match(urinorm(id_url))
        if match is not None:
            return match.group(1)
    except ValueError:
        if relaxed:
            match = USERNAME_RE.match(urinorm('http://{0}'.format(id_url)))
            if match is not None:
                return match.group(1)
    return u''


def webob_response(webresponse, request):
    """Returns an equivalent WebOb Response object for the given
    an openid.server.server.WebResponse object.
    """
    if webresponse.code == 200 and webresponse.body.startswith('<form'):
        # The OpenID response has been encoded as an HTML form that POSTs to
        # the relying party. We need to wrap the form in an HTML document
        # and serve that to the browser.
        options = {
            'title': _(u'OpenID authentication in progress'),
            'openid_form_response': webresponse.body.decode('utf-8'),
            }
        response = render_to_response('templates/form_auto_submit.pt', options, request)
    else:
        # Create a raw response.
        response = Response(webresponse.body)

    response.status = webresponse.code
    response.headers.update(webresponse.headers)

    return response


def add_ax_response(openid_request, openid_response, attributes):
    """Annotates the ``openid_response`` object with Attribute Exchange (AX)
    fields.
    """
    ax_request = ax.FetchRequest.fromOpenIDRequest(openid_request)
    if ax_request is None:
        # This is not an Attribute Exchange request
        return

    ax_response = ax.FetchResponse(ax_request)
    for type_uri, attrinfo in ax_request.requested_attributes.iteritems():
        if type_uri in attributes:
            ax_response.addValue(type_uri, attributes[type_uri])

    openid_response.addExtension(ax_response)


def add_sreg_response(openid_request, openid_response, attributes):
    """Annotates the ``openid_response`` object with Simple Registration
    (Sreg) fields.

    The fields are mapped from the Attribute Exchange (AX) equivalents given
    as ``attributes``.
    """
    sreg_request = sreg.SRegRequest.fromOpenIDRequest(openid_request)
    if not sreg_request.wereFieldsRequested():
        # This is not a Simple Registration request
        return

    # Generate a mapping of user attributes keyed with the SReg field names.
    sreg_data = dict(
        (AX_TO_SREG[type_uri], value)
        for type_uri, value
        in attributes.iteritems()
        if type_uri in AX_TO_SREG)

    sreg_response = sreg.SRegResponse.extractResponse(sreg_request, sreg_data)
    openid_response.addExtension(sreg_response)


def endpoint(request):
    """OpenID protocol endpoint."""
    store = AlchemyStore(DBSession())
    openid_server = server.Server(store, route_url('openid_endpoint', request))
    user = authenticated_userid(request)

    try:
        openid_request = openid_server.decodeRequest(request.params)
    except server.ProtocolError, why:
        return HTTPBadRequest('Invalid OpenID request: {0}'.format(why))

    if openid_request is None:
        # The request was not identifiable as an OpenID request.
        return HTTPBadRequest('Invalid OpenID request')

    # The two cases that we need to handle explicitly to implement our
    # provider logic.
    if openid_request.mode in ('checkid_immediate', 'checkid_setup'):
        # Determine if the user is authorized already. This requires that
        #  - The user is logged into the provider
        #  - The claimed identity matches the user's own identity
        #  - The user has approved the connection previously for new requests.
        authorized = False
        attributes = {}
        if user is not None and openid_request.identity == identity_url(request, user):
            session = DBSession()
            visit = session.query(VisitedSite)\
                        .join(User)\
                        .filter(User.username == user)\
                        .filter(VisitedSite.trust_root == openid_request.trust_root)\
                        .first()
            if visit is not None and visit.remember:
                authorized = True
                if visit.persona is not None:
                    attributes = dict((a.type_uri, a.value) for a in visit.persona.attributes)

        if authorized:
            # The user has been authorized previously.
            openid_response = openid_request.answer(True)
            add_ax_response(openid_request, openid_response, attributes)
            add_sreg_response(openid_request, openid_response, attributes)
        elif openid_request.immediate:
            # Non-authorized immediate request will fail unconditionally.
            openid_response = openid_request.answer(False)
        else:
            # Require the user to make an explicit decision on how to handle
            # the authentication request.
            return auth_decision(request, openid_request)

    else:
        # All other modes are handled directly within the library
        openid_response = openid_server.handleRequest(openid_request)

    return webob_response(openid_server.encodeResponse(openid_response), request)


def auth_decision(request, openid_request):
    """Renders the appropriate page that allows the user to make a decision
    about the OpenID authentication request.

    The possible scenarios are:

    1. The user is logged in to the OP and RP wants OP to select the id
    2. The user is logged in to the OP and her identity matches the claimed id.
    3. The user is logged in to the OP and her identity does not match the claimed id.
    4. The user is not logged in and RP wants OP to select the id.
    5. The user is not logged in and RP sent a claimed id.

    In cases 1) and 2) the user can simply make the decision on allowing the
    authentication to proceed (and AX related decisions.)

    In cases 3), 4) and 5) the user needs to log in to the OP first.
    """
    user = authenticated_user(request)
    expected_user = extract_local_id(request, openid_request.identity)
    session = DBSession()
    log = logging.getLogger('webidentity')

    # Persist the OpenID request so we can continue processing it after the
    # user has authenticated overriding any previous request.
    cidrequest = session.query(CheckIdRequest).get(request.environ['repoze.browserid'])
    if cidrequest is None:
        cidrequest = CheckIdRequest(request.environ['repoze.browserid'], openid_request)
    else:
        # Unconditionally overwrite any existing checkid request.
        cidrequest.request = openid_request
        cidrequest.issued = int(time.time())

    session.add(cidrequest)
    # Clean up dangling requests for roughly 10% of the time.
    # We do not do this on every call to reduce the possibility of a database
    # deadlock as rows need to be locked.
    if random.randint(0, 100) < 10:
        threshold = int(time.time()) - 3600
        session.query(CheckIdRequest).filter(CheckIdRequest.issued < threshold).delete()
        log.info('Cleaned up dangling OpenID authentication requests.')

    options = {
        'title': _(u'Approve OpenID request?'),
        'action_url': route_url('openid_confirm', request),
        'trust_root': openid_request.trust_root,
        #'reset_url': route_url('reset_password', request),
    }

    if user is not None:
        ax_request = ax.FetchRequest.fromOpenIDRequest(openid_request)
        sreg_request = sreg.SRegRequest.fromOpenIDRequest(openid_request)

        if ax_request is not None or sreg_request is not None:
            # Prepare the user attributes for an SReg/AX request.

            # Mapping of attributes the RP has requested from the user.
            requested_attributes = {}

            if sreg_request.wereFieldsRequested():
                requested_attributes.update(dict(
                    (SREG_TO_AX.get(field), field in sreg_request.required)
                    for field
                    in sreg_request.allRequestedFields()))

            # The AX request takes precedence over SReg if both are requested.
            if ax_request is not None:
                requested_attributes.update(dict(
                    (type_uri, attrinfo.required)
                    for type_uri, attrinfo
                    in ax_request.requested_attributes.iteritems()))

            # Set of attributes that the RP has marked mandatory
            required_attributes = set(
                type_uri
                for type_uri, required
                in requested_attributes.iteritems()
                if required)

            for persona in user.personas:
                available_attributes = set(a.type_uri for a in persona.attributes)
                options.setdefault('personas', []).append({
                    'id': persona.id,
                    'name': persona.name,
                    'attributes': [
                        dict(type_uri=a.type_uri, value=a.value)
                        for a in persona.attributes
                        if a.type_uri in requested_attributes],
                    'missing': required_attributes - available_attributes,
                })

        if openid_request.idSelect():
            # Case 1.
            # The Relying Party has requested us to select an identifier.
            options.update({
                'identity': identity_url(request, user.username),
                'csrf_token': request.session.get_csrf_token(),
            })
            request.add_response_callback(disable_caching)
            return render_to_response('templates/openid_confirm.pt', options, request)
        elif user.username == expected_user:
            # Case 2.
            # A logged-in user that matches the user in the claimed identifier.
            options.update({
                'identity': openid_request.identity,
                'csrf_token': request.session.get_csrf_token(),
            })
            request.add_response_callback(disable_caching)
            return render_to_response('templates/openid_confirm.pt', options, request)
        else:
            # Case 3
            # TODO: Implement case 3
            raise NotImplementedError
    else:
        # Cases 4 and 5.
        options.update({
            'action_url': route_url('openid_confirm_login', request),
            'login_name': expected_user if not openid_request.idSelect() else None,
            'csrf_token': request.session.get_csrf_token(),
        })
        return render_to_response('templates/openid_confirm_login.pt', options, request)


def get_ax_attributes(request):
    """Returns a dictionary of type_uri => value mappings containing the AX
    attributes for the currently authenticated user.
    """
    user = authenticated_user(request)
    if user is None:
        return {}

    session = DBSession()
    # TODO: Should we convert persona_id to an integer first?
    persona = session.query(Persona)\
                .join(User)\
                .filter(User.id == user.id)\
                .filter(Persona.id == request.params.get('persona', ''))\
                .first()
    if persona is None:
        return {}

    # Get the attribute values from the selected persona.
    return dict((a.type_uri, a.value) for a in persona.attributes)


def confirm(request):
    """Confirmation for an OpenID authentication request."""
    user = authenticated_user(request)
    if user is not None and 'form.submitted' in request.params:
        if request.POST.get('csrf_token') != request.session.get_csrf_token():
            raise Forbidden

        session = DBSession()
        result = session.query(CheckIdRequest)\
                    .filter_by(key=request.environ.get('repoze.browserid', ''))\
                    .first()

        if result is not None:
            openid_request = result.request
            session.delete(result)
        else:
            # TODO: Return an error message
            return HTTPBadRequest('Invalid confirmation request')

        if 'accept' in request.params:
            ax_attributes = get_ax_attributes(request)

            visit = session.query(VisitedSite)\
                        .join(User)\
                        .filter(User.id == user.id)\
                        .filter(VisitedSite.trust_root == openid_request.trust_root)\
                        .first()
            if visit is None:
                # This is the first time the user is visiting this RP
                visit = VisitedSite(openid_request.trust_root)
                user.visited_sites.append(visit)

            visit.remember = 'remember' in request.params

            try:
                persona_id = int(request.params.get('persona'))
                # Make sure that the referenced persona actually belongs to the user
                persona = session.query(Persona)\
                            .join(User)\
                            .filter(User.id == user.id)\
                            .filter(Persona.id == persona_id)\
                            .first()
                if persona is not None:
                    visit.persona = persona
            except (TypeError, ValueError):
                pass

            session.add(visit)

            identity = identity_url(request, user.username)
            openid_response = openid_request.answer(True, identity=identity)
            add_ax_response(openid_request, openid_response, ax_attributes)
            add_sreg_response(openid_request, openid_response, ax_attributes)

            if visit.remember:
                log_activity(request, Activity.AUTHORIZE, openid_request.trust_root)
            else:
                log_activity(request, Activity.AUTHORIZE_ONCE, openid_request.trust_root)

        else:
            log_activity(request, Activity.DENY, openid_request.trust_root)
            openid_response = openid_request.answer(False)

        store = AlchemyStore(session)
        openid_server = server.Server(store, route_url('openid_endpoint', request))

        response = webob_response(openid_server.encodeResponse(openid_response), request)
        response.headerlist.extend(forget(request))

        return response

    return HTTPBadRequest('Invalid confirmation request')


def confirm_login(request):
    """Renders a login form for a user that needs to login in order to
    authenticate an active OpenID authentication request.
    """
    if 'form.submitted' in request.POST:
        if request.POST.get('csrf_token') != request.session.get_csrf_token():
            raise Forbidden

        login = request.POST.get('login', '')
        password = request.POST.get('password', '')
        user = DBSession().query(User).filter_by(username=login).first()

        if user is not None and user.check_password(password):
            headers = remember(request, user.username)
            return HTTPFound(
                location=route_url('openid_confirm_login_success', request),
                headers=headers)
        else:
            request.session.flash(_(u'Failed to log in, please try again.'))

    options = {
        'title': _(u'Log in to authenticate OpenID request'),
        'login_name': request.params.get('login', ''),
        'action_url': route_url('openid_confirm_login', request),
        #'reset_url': route_url('reset_password', request),
        'csrf_token': request.session.get_csrf_token(),
    }
    return render_to_response('templates/openid_confirm_login.pt', options, request)


def confirm_login_success(request):
    session = DBSession()
    result = session.query(CheckIdRequest)\
                .filter_by(key=request.environ.get('repoze.browserid', ''))\
                .first()

    if result is not None:
        openid_request = result.request
        session.delete(result)
        return auth_decision(request, openid_request)

    raise NotFound('Unknown OpenID request')


def identity(request):
    """OpenID identity page for a user.

    The URL this page is served as is the OpenID identifier for the user and
    the contents contain the required information for service discovery.
    """
    if request.matchdict.get('local_id', '').strip():
        session = DBSession()
        account = session.query(User)\
                    .filter(User.username == request.matchdict['local_id'])\
                    .first()
        if account is None:
            raise NotFound()

        return {
            'title': _(u'Identity page'),
            'openid_endpoint': route_url('openid_endpoint', request),
            'xrds_location': route_url('yadis_user', request, local_id=request.matchdict['local_id']),
            'identity': identity_url(request, request.matchdict['local_id']),
            }
    else:
        raise NotFound()


def yadis(request):
    """Serves the YADIS XRDS documents to facilitate service discovery."""
    OPENID_AX = 'http://openid.net/srv/ax/1.0'

    if request.matchdict.get('local_id', '').strip():
        session = DBSession()
        account = session.query(User).filter(User.username == request.matchdict['local_id']).first()
        if account is None:
            raise NotFound()

        # User specific XRDS document
        options = {
            'service_types': [discover.OPENID_2_0_TYPE, OPENID_AX, sreg.ns_uri],
            'local_id': identity_url(request, request.matchdict['local_id']),
            'uri': route_url('openid_endpoint', request),
        }
    else:
        # Server XRDS document
        options = {
            'service_types': [discover.OPENID_IDP_2_0_TYPE, OPENID_AX, sreg.ns_uri],
            'uri': route_url('openid_endpoint', request),
        }

    response = render_to_response('templates/openid_yadis.pt', options, request)
    response.content_type = 'application/xrds+xml'

    return response
