# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from nuorisovaalit.views import disable_caching
from nuorisovaalitadmin.views.login import authenticated_user
from nuorisovaalitadmin.views.ui import top_navigation
from pyramid.renderers import get_renderer
from pyramid.url import route_url
from webob import Response


def ping(request):
    """Entry point for HAProxy health checks."""
    request.add_response_callback(disable_caching)
    return Response('pong', content_type='text/plain')


def renderer_globals_factory(system):
    """Returns a dictionary of mappings that are available as global
    parameters in each renderer.
    """
    request = system.get('request')
    user = authenticated_user(request)

    userid = user.username if user is not None else None
    school = user.school.name if user is not None else None

    if request.path == '/':
        section = 'frontpage'
    else:
        section = '-'.join(request.path.split('/')).strip('-')

    return {
        'flash_messages': request.session.pop_flash(),
        'main': get_renderer('templates/master.pt').implementation(),
        'top_navigation': top_navigation(request),
        'logged_user': userid,
        'logged_school': school,
        'logout_url': route_url('logout', request),
        'section': 'section-' + section,
    }
