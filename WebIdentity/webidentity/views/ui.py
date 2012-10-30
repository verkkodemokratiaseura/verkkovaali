# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Generic UI related functionality."""

# from pyramid.url import route_url
# from pyramid.security import authenticated_userid
# from webidentity.i18n import WebIdentityMessageFactory as _


def top_navigation(request):
    """Returns the top navigation links for the current user."""
    links = []
    # userid = authenticated_userid(request)
    # if userid is None:
    #     links.extend([
    #         dict(url=route_url('login', request), title=_(u'Log in')),
    #     ])
    # else:
    #     links.extend([
    #         dict(url=route_url('home_page', request), title=_(u'Profile')),
    #         dict(url=route_url('logout', request), title=_(u'Log out')),
    #     ])
    #
#    links.extend([
#        dict(url=route_url('about_page', request), title=_(u'About')),
#        dict(url=route_url('contact_page', request), title=_(u'Contact')),
#    ])

    return links
