# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
"""Generic UI related functionality."""

from nuorisovaalitadmin.views.login import groupfinder
from pyramid.security import authenticated_userid
from pyramid.security import has_permission
from pyramid.url import route_url


def top_navigation(request):
    """Returns the top navigation links for the current user."""
    links = [
        dict(url=route_url('index', request), title=u'Etusivu', name='frontpage'),
    ]
    userid = authenticated_userid(request)

    if userid is not None:

        def permitted(permission):
            return has_permission(permission, request.context, request)

        def permitted_url(permission, route):
            return route_url(route, request) if permitted(permission) else None

        def is_admin():
            return 'group:admin' in groupfinder(userid, request)

        school_pages = (
            dict(url=permitted_url('submit-voters', 'submit_voters'), title=u'Oppilastietojen lataaminen', name='submit-voters'),
            dict(url=permitted_url('download-voters', 'voter_list'), title=u'Äänestäjälista', name='voter-list'),
            dict(url=permitted_url('submit-results', 'submit_results'), title=u'Tulosten lataaminen', name='submit-results'),
            dict(url=permitted_url('download-results', 'results'), title=u'Tulokset', name='results'),
        )
        stats_pages = (
            dict(url=permitted_url('view-stats', 'results_index'), title=u'Allianssi', name='allianssi'),
            dict(url=permitted_url('view-stats', 'voter_submission_stats'), title=u'Äänestäjälistatilastot', name='voter-stats'),
            dict(url=permitted_url('view-stats', 'result_submission_stats'), title=u'Tuloslistatilastot', name='result-stats'),
        )

        if is_admin():
            # ADMIN
            links.extend(school_pages)
            links.extend(stats_pages)
        elif permitted('view-stats'):
            # xxxx
            links.extend(stats_pages)
        else:
            # SCHOOLS
            links.extend(school_pages)

    return links
