# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""User related functionality"""

from pyramid.exceptions import Forbidden
from pyramid.security import authenticated_userid
from pyramid.url import route_url
from sqlalchemy import func
from webidentity.i18n import WebIdentityMessageFactory as _
from webidentity.models import Activity
from webidentity.models import DBSession
from webidentity.models import Persona
from webidentity.models import User
from webidentity.models import VisitedSite


def authenticated_user(request):
    """Returns the currently authenticated User instance or None."""
    userid = authenticated_userid(request)
    if userid is not None:
        return DBSession().query(User).filter_by(username=userid).first()


def log_activity(request, action, url=None):
    """Creates a new activity log entry for the currently logged-in user."""
    user = authenticated_user(request)
    if user is None:
        return

    remote_addr = request.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
    if not remote_addr:
        remote_addr = request.environ.get('REMOTE_ADDR', '0.0.0.0').strip()

    user.activity.append(Activity(
        ipaddr=remote_addr,
        session=request.cookies['auth_tkt'],
        action=action,
        url=url))


def home_page(request):
    """Personal home page."""
    user = authenticated_user(request)
    if user is None:
        raise Forbidden()
    return {}


def change_password(request):
    """Form that allows the currently logged in user to change her password.
    """
    user = authenticated_user(request)
    if user is None:
        raise Forbidden('You are not allowed to access this resource.')

    if 'form.submitted' in request.POST:
        current_password = request.POST.get('current_password', '')
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if request.session.get_csrf_token() != request.POST.get('csrf_token'):
            raise Forbidden(u'CSRF attempt detected.')
        elif not user.check_password(current_password):
            request.session.flash(_(u'Current password is wrong'))
        elif len(password.strip()) < 5:
            request.session.flash(_(u'Password must be at least five characters long'))
        elif password != confirm_password:
            request.session.flash(_(u'Given passwords do not match'))
        else:
            # Store the new password
            session = DBSession()
            user.password = password
            session.add(user)
            request.session.flash(_(u'Password changed'))

    options = {
        'action_url': route_url('change_password', request),
        'csrf_token': request.session.get_csrf_token(),
    }

    return options


def visited_sites(request):
    """Lists the latest information about all the visited sites for the
    currently logged in user.
    """
    user = authenticated_user(request)
    if user is None:
        raise Forbidden()

    session = DBSession()
    sites = session.query(VisitedSite, func.max(Activity.timestamp).label('last_visit'), Persona)\
        .outerjoin(Persona)\
        .filter(VisitedSite.user_id == user.id)\
        .filter(VisitedSite.trust_root == Activity.url)\
        .filter(VisitedSite.user_id == Activity.user_id)\
        .filter(Activity.action.in_([Activity.AUTHORIZE, Activity.AUTHORIZE_ONCE]))\
        .group_by(VisitedSite.trust_root)\
        .all()

    date_format = request.registry.settings['webidentity_date_format']

    site_info = []
    for site, last_visit, persona in sites:
        site_info.append({
            'id': site.id,
            'url': site.trust_root,
            'timestamp': last_visit.strftime(date_format),
            'persona': {
                'id': persona.id,
                'name': persona.name,
                'edit_url': 'http://fo.bar/'
                } if persona is not None else None,
            'remember': 'checked' if site.remember else None,
        })

    options = {
        'action_url': 'form_action',
#        'action_url': route_url('visited_sites', request),
        'sites': site_info,
    }

    return options
