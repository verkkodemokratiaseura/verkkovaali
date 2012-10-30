# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from pyramid.url import route_url
from webidentity.i18n import WebIdentityMessageFactory as _
from webob import Response


def front_page(request):
    return {
        'title': _(u'Nuorisovaalit 2011 - Tunnistautuminen'),
        #'login_url': route_url('login', request),
        #'logout_url': route_url('logout', request),
        'openid_endpoint': route_url('openid_endpoint', request),
        'xrds_location': route_url('yadis_server', request),
    }


def about_page(request):
    return Response('About page')


def contact_page(request):
    return Response('Contact page')
