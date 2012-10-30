# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalit.models import DBSession
from nuorisovaalit.models import Voter
from nuorisovaalit.models import voting_allowed
from openid.consumer.consumer import Consumer
from openid.consumer.consumer import SUCCESS
from openid.yadis.discover import DiscoveryFailure
from openidalchemy.store import AlchemyStore
from pyramid.exceptions import Forbidden
from pyramid.renderers import render_to_response
from pyramid.security import authenticated_userid
from pyramid.security import remember
from pyramid.url import route_url
from webob.exc import HTTPFound

import logging


def authenticated_user(request):
    """Returns the currently authenticated User instance or None.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    :rtype: :py:class:`nuorisovaalit.models.Voter` or ``None``
    """
    userid = authenticated_userid(request)
    if userid is not None:
        return DBSession().query(Voter).filter_by(openid=userid).first()


def make_consumer(request):
    """Returns a Consumer object with a session bound to the request.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    :rtype: :py:class:`openid.consumer.consumer.Consumer`
    """
    session = request.session.setdefault('openid', {})
    consumer = Consumer(session, AlchemyStore(DBSession()))
    return consumer


def login(request):
    """Renders the OpenID login form and initiates the authentication process
    on form submission.

    This is the first step in the voting process.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    """
    log = logging.getLogger('nuorisovaalit')
    options = {
        'action_url': route_url('login', request),
        'message': None,
        'csrf_token': request.session.get_csrf_token(),
        'voting_allowed': voting_allowed(request),
    }

    if 'identify' in request.POST:
        if request.POST.get('csrf_token') != request.session.get_csrf_token():
            log.warn('CSRF attempt at: {0}.'.format(request.url))
            raise Forbidden()

        provider_url = request.registry.settings['nuorisovaalit.openid_provider'].strip()
        return openid_initiate(provider_url, request)

    return render_to_response('templates/login.pt', options, request)


def openid_initiate(identity_url, request):
    """Initiates an OpenID authentication process.

    Upon successful discovery of the OpenID provider the user will be
    redirected to the provider to perform the authentication process. This is
    the second step in the voting process.

    :param identity_url: The claimed identifier provided by the user.
    :type identifier: unicode

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    """
    log = logging.getLogger('nuorisovaalit')
    consumer = make_consumer(request)

    try:
        auth_request = consumer.begin(identity_url)
    except DiscoveryFailure:
        log.warn('Failed to contact OpenID provider: {0}'.format(identity_url))
        return openid_failure(request, u'Yhteydenotto OpenID-palvelimelle epäonnistui tilapäisesti.')
    except KeyError:
        log.warn('Failed to initiate OpenID authentication: {0}'.format(identity_url))
        return openid_failure(request)

    # Redirect the user to the OpenID provider for authentication.
    url = auth_request.redirectURL(
        request.application_url, route_url('openid-response', request))

    log.info('Initiating OpenID authentication for: {0}'.format(identity_url))
    return HTTPFound(location=url)


def openid_response(request):
    """Processes the response of the OpenID provider and upon successful
    response authenticates the user.

    In order for a user to be authenticated the following criteria must be
    met:

        * the OpenID provider has responded with a positive assertation.

        * the verified OpenID identity must match an existing
          :py:attr:`nuorisovaalit.models.Voter.openid` record.

    In case the above criteria are not met the user is presented with an error
    page.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    """
    log = logging.getLogger('nuorisovaalit')
    mode = request.params.get('openid.mode', None)

    if mode == 'id_res':
        # We received a positive authentication response.
        consumer = make_consumer(request)
        response = consumer.complete(request.params, request.url)

        if response.status == SUCCESS:
            identity = response.identity_url.rstrip('/')

            session = DBSession()
            user = session.query(Voter).filter(Voter.openid == identity).first()
            if user is None:
                log.warn('Failed to authenticate "{0}": unknown user.'.format(identity))
                return openid_failure(request)

            log.info('Authenticated "{0}".'.format(identity))
            if user.has_voted():
                url = route_url('vote-finish', request)
                request.session['vote_registered'] = 'yes'
                log.info('User "{0}" has already voted.'.format(identity))
            else:
                url = route_url('select', request)

            headers = remember(request, identity)
            return HTTPFound(location=url, headers=headers)
        else:
            log.warn('Failed to authenticate "{0}".'.format(response.identity_url))
            return openid_failure(request)

    elif mode == 'cancel':
        # We received an explicit negative authentication response.
        log.info('OpenID authentication canceled.')
        return openid_canceled(request)
    else:
        log.warn('Unknown OpenID response mode: {0}.'.format(mode))
        return openid_failure(request)


def openid_failure(request, message=u''):
    """Renders a failure message.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :param message: Human readable message describing the error.
    :type message: unicode
    """
    options = dict(message=message)
    return render_to_response('templates/login_failed.pt', options, request)


def openid_canceled(request):
    """Renders the canceled OpenID authentication page.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`
    """
    options = {}
    return render_to_response('templates/openid_canceled.pt', options, request)
