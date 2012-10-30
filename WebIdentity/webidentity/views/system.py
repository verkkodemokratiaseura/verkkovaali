# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pyramid.renderers import get_renderer
from pyramid.security import authenticated_userid
from webidentity.views.oid import identity_url
from webob import Response

import logging


def ping(request):
    """Entry point for HAProxy health checks."""
    return Response('pong', content_type='text/plain')


def renderer_globals_factory(system):
    """Returns a dictionary of mappings that are available as global
    parameters in each renderer.
    """
    request = system.get('request')
    username = authenticated_userid(request)
    identity = None
    if username is not None:
        try:
            identity = identity_url(request, username)
        except ValueError:
            # We received a curious error in production from the underlying
            # openid.urinorm.urinorm() function which indicated that the
            # username passed contains an invalid charact (most likely a
            # whitespace character within a domain name).
            # Until we can fully understand the cause of the error we simply
            # log the incident here and let the error propagate.
            log = logging.getLogger('webidentity')
            log.warn('identity_url() failed for username "{0}".'.format(username))
            raise

    return {
        'flash_messages': request.session.pop_flash(),
        'identity': identity,
        'main': get_renderer('templates/master.pt').implementation(),
        'username': username,
    }
