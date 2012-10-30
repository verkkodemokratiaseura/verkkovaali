# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pyramid.renderers import render_to_response


def unauthorized(request):
    """Renders a custom page in response to Forbidden exceptions (403)"""
    options = {}
    response = render_to_response('templates/unauthorized.pt', options, request)
    response.status = 403
    return response


def notfound(request):
    """Renders a custom page in response to NotFound exceptions (404)"""
    options = {}
    response = render_to_response('templates/notfound.pt', options, request)
    response.status = 404
    return response
