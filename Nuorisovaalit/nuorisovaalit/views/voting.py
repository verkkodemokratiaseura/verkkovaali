# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from itertools import cycle
from nuorisovaalit.models import Coalition
from nuorisovaalit.models import Candidate
from nuorisovaalit.models import DBSession
from nuorisovaalit.models import Party
from nuorisovaalit.models import Vote
from nuorisovaalit.models import VotingLog
from nuorisovaalit.views import disable_caching
from nuorisovaalit.views.login import authenticated_user
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.security import forget
from pyramid.url import route_url
from sqlalchemy import or_
from webob.exc import HTTPFound

import logging
import re


#: Regular expression to match an email address.
RE_EMAIL = re.compile(ur'^[-a-z0-9_.]+@(?:[-a-z0-9]+\.)+[a-z]{2,6}$', re.IGNORECASE)
#: Regular expression to match a normalized (whitespace and hyphens removed) GSM number.
RE_GSM = re.compile(ur'^((00|\+?)358|0)[1-9]{1}[0-9]{6,}$')
#: Regular expression to split the street address into (street, zipcode, city).
RE_ADDRESS = re.compile(ur'^(.*)(\d{5})(.*)$')


def split_candidates(candidates, columns):
    """Splits a list of candidates to be rendered in a number of columns.

    Columns are filled from left to right so a previous column will always
    contain more or equal amount of candidates.

    :param candidates: An iterable of candidates that will be split.
    :type candidates: iterable

    :param columns: The number of columns to split the candidates in.
    :type columns: int

    :rtype: generator
    """
    size = len(candidates)
    colsize, overlap = divmod(size, columns)

    offset = 0
    while offset < size:
        spil = 1 if overlap > 0 else 0
        chunk = colsize + spil
        yield candidates[offset:(offset + chunk)]
        offset += chunk
        overlap -= 1


def select(request):
    """Renders the candidate selection list.

    The candidate list is generated based on the
    :py:class:`nuorisovaalit.models.District` the authenticated user is
    associated with. The user is only allowed to vote candidates in her own
    voting district.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: dict
    """
    # Deco Grid positions for the candidate columns.
    positions = ['0', '1:3', '2:3']
    columns = len(positions)
    session = DBSession()
    log = logging.getLogger('nuorisovaalit')
    # Disable caching
    request.add_response_callback(disable_caching)

    # Require authentication.
    voter = authenticated_user(request)
    if voter is None:
        log.warn('Unauthenticated attempt to select candidates.')
        raise Forbidden()

    # User should vote only once.
    if voter.has_voted():
        log.warn('User "{0}" attempted to select candidates after voting.'.format(voter.openid))
        return HTTPFound(location=route_url('vote-finish', request))

    # Query the candidates in the voter's election district.
    query = session.query(Party, Candidate)\
                .filter(Candidate.party_id == Party.id)\
                .filter(Candidate.district_id == voter.school.district.id)\
                .order_by(Party.name, Candidate.number)

    candidates_by_party = {}
    for party, candidate in query.all():
        candidates_by_party.setdefault(party.name, []).append(candidate)

    parties = []
    for party_name, candidates in sorted(candidates_by_party.items()):
        parties.append({
            'title': party_name,
            'candidates': split_candidates([
                dict(name=c.fullname(), number=c.number, url=route_url('vote', request, number=c.number))
                for c in candidates], columns),
            'positions': cycle(positions),
            })

    coalitions = []
    for coalition in session.query(Coalition).filter_by(district_id=voter.school.district.id).all():
        coalitions.append(u', '.join(sorted(party.name for party in coalition.parties)))

    options = {
        'parties': parties,
        'columns': columns,
        'coalitions': coalitions,
        'district': voter.school.district.name,
        'empty_vote_url': route_url('vote', request, number=Candidate.EMPTY_CANDIDATE),
        }

    return options


def vote(request):
    """Renders the voting form for the selected candidate and processes the
    vote.

    A valid vote must meet all of the following criteria:

        * The voter must be authenticated.

        * The voter must not have voted previously.

        * The candidate must be the one chosen in the previous step (See
          :py:func:`select`).

        * The candidate must belong to the same voting district as the voter.

        * The CSRF token included in the form must be valid.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: dict
    """
    error = False
    session = DBSession()
    voter = authenticated_user(request)
    log = logging.getLogger('nuorisovaalit')
    request.add_response_callback(disable_caching)

    # The user must be authenticated at this time
    if voter is None:
        log.warn('Unauthenticated attempt to vote.')
        raise Forbidden()

    # The user may vote only once
    if voter.has_voted():
        log.warn('User "{0}" attempted to vote a second time.'.format(voter.openid))
        return HTTPFound(location=route_url('vote-finish', request))

    # The selected candidate must either be the special empty candidate or a
    # valid candidate in the voter's voting district.
    candidate = session.query(Candidate)\
            .filter(Candidate.number == int(request.matchdict['number']))\
            .filter(or_(Candidate.district_id == voter.school.district.id,
                        Candidate.number == Candidate.EMPTY_CANDIDATE))\
            .first()

    if candidate is None:
        log.warn('User "{0}" attempted to vote for a non-existing candidate "{1}".'.format(
            voter.openid, request.matchdict['number']))
        raise NotFound

    # Handle voting
    if 'vote' in request.POST:

        if request.session.get_csrf_token() != request.POST.get('csrf_token'):
            log.warn('CSRF attempt at: {0}.'.format(request.url))
            error = True
        elif request.POST['vote'].strip() == request.matchdict['number']:

            session.add(Vote(candidate, voter.school, Vote.ELECTRONIC, 1))
            session.add(VotingLog(voter))

            log.info('Stored vote cast by "{0}".'.format(voter.openid))
            return HTTPFound(location=route_url('vote-finish', request))
        else:
            error = True

    options = {
        'action_url': request.path_url,
        'select_url': route_url('select', request),
        'candidate': {
            'number': candidate.number,
            'name': candidate.fullname(),
            },
        'profile': {
            'fullname': voter.fullname(),
            'district': voter.school.district.name,
        },
        'error': error,
        'csrf_token': request.session.get_csrf_token(),
    }

    return options


def vote_finish(request):
    """Renders the OpenID preference page after a successful voting process.

    The voter will be redirected to this page either after casting a vote or
    after any subsequent login to the system.

    The voter is allowed to select her OpenID preference once.

    If the voter chooses to keep the OpenID, he must provide valid
    contact information if it is not already known. Email, GSM, and
    address are required, but can be edited on the page.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: dict
    """
    log = logging.getLogger('nuorisovaalit')
    request.add_response_callback(disable_caching)

    voter = authenticated_user(request)
    if voter is None:
        raise Forbidden()

    options = {
        'action_url': route_url('vote-finish', request),
        'csrf_token': request.session.get_csrf_token(),
        'accept_openid': voter.accept_openid,
        'message': u'Äänesi on tallennettu',
        'has_preference': voter.has_preference(),
        'pref_selected': False,
        'errors': [],
        'voter': voter,
        'gsm': request.POST.get('gsm', voter.gsm),
        'email': request.POST.get('email', voter.email),
        'street': request.POST.get('street', u''),
        'zipcode': request.POST.get('zipcode', u''),
        'city': request.POST.get('city', u''),
    }

    street = request.POST.get('street')
    zipcode = request.POST.get('zipcode')
    city = request.POST.get('city')

    # Parse the voter's address to the options if street, zipcode,
    # city were not provided.
    if (street, zipcode, city) == (None, None, None):
        match = RE_ADDRESS.match(voter.address or u'')
        if match:
            options['street'], options['zipcode'], options['city'] \
                               = (s.strip().strip(',').strip() for s in match.groups())
        elif voter.address is not None:
            # Put the whole address to the street field if it could
            # not be parsed.
            log.info('The address for user "{0}" in the database is partial.'.format(voter.openid))
            options['street'] = voter.address

    if request.session.get('vote_registered', 'no') == 'yes':
        log.info('User "{0}" returned after having voted already.'.format(voter.openid))
        options['message'] = u'Olet jo äänestänyt'

    if 'form.submitted' in request.POST:
        # CSRF protection.
        if request.session.get_csrf_token() != request.POST.get('csrf_token'):
            log.warn('CSRF attempt at: {0}.'.format(request.url))
            raise Forbidden()

        session = DBSession()

        # Voter has already selected his/her preference.
        if voter.has_preference():
            log.info('User "{0}" has already selected an OpenID preference, skipping.'.format(voter.openid))
            return exit_voting(request)

        # OpenID declined.
        if request.POST.get('use_open_identity') == 'no':
            voter.accept_openid = False
            session.add(voter)
            log.info('User "{0}" declined the OpenID account.'.format(voter.openid))
            return exit_voting(request)

        def normalize_gsm(gsm):
            """Remove whitespace and hyphens from the GSM number."""
            return u''.join(gsm.strip().replace('-', '').split())

        # GSM number is required.
        gsm = normalize_gsm(request.POST.get('gsm', u''))
        if RE_GSM.match(gsm) is None:
            options['errors'].append(
                u'GSM-numero on virheellinen, '
                u'esimerkki oikeasta muodosta "0501234567".')

        # Email is required.
        email = request.POST.get('email', u'').strip()
        if RE_EMAIL.match(email) is None:
            options['errors'].append(
                u'Sähköpostiosoite on virheellinen, '
                u'esimerkki oikeasta muodosta "matti@meikalainen.fi".')

        # Street is required.
        street = request.POST.get('street', u'').strip()
        if not street:
            options['errors'].append(u'Katuosoite puuttuu.')

        # Zipcode is required.
        zipcode = request.POST.get('zipcode', u'').strip()
        if len(zipcode) != 5 or not zipcode.isdigit():
            options['errors'].append(u'Postinumero on virheellinen, '
                                     u'esimerkki oikeasta muodosta "12345".')

        # City is required.
        city = request.POST.get('city', u'').strip()
        if not city:
            options['errors'].append(u'Postitoimipaikka puuttuu.')

        # OpenID preference must be selected.
        if request.POST.get('use_open_identity', None) is None:
            options['errors'].append(u'Valitse haluatko verkkovaikuttajaidentiteetin.')

        # Update voter info if no errors were found.
        if not options['errors']:
            voter.accept_openid = True
            voter.gsm = gsm
            voter.email = email
            voter.address = u'{0}, {1}, {2}'.format(street, zipcode, city)
            session.add(voter)
            log.info('User "{0}" accepted the OpenID account.'.format(voter.openid))
            return exit_voting(request)
        elif request.POST.get('use_open_identity', None) is not None:
            options['accept_openid'] = True
            options['pref_selected'] = True

        if options['errors']:  # pragma: no cover
            log.warn('User "{0}" failed validation for the OpenID preference.'.format(voter.openid))
            for error_msg in options['errors']:
                log.warn(u'Validation error: {0}'.format(error_msg))

    return options


def exit_voting(request):
    """Clears the authentication session by setting the approriate cookies.

    This view does not render anything to the browser.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: dict
    """
    # Remove the user session.
    request.session.invalidate()

    # Log the user out and expire the auth_tkt cookie
    headers = forget(request)

    url = route_url('close-window', request)
    return HTTPFound(location=url, headers=headers)


def close_window(request):
    """The final page after persisting the OpenID preference.

    The main purpose of this view is to provide a resource that
    :py:func:`exit_voting` view will redirect the voter to in order to clear
    the authentication and session cookies.

    :param request: The currently active request.
    :type request: :py:class:`pyramid.request.Request`

    :rtype: dict
    """
    return {}
