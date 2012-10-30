# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
"""
Functionality for xxxx members.
"""
from nuorisovaalit.models import District
from nuorisovaalit.models import School
from nuorisovaalit.models import Vote
from nuorisovaalit.models import Voter
from nuorisovaalit.results import dhont_selection
from nuorisovaalitadmin.models import CSVSubmission
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.models import User
from nuorisovaalitadmin.views import disable_caching
from nuorisovaalitadmin.views import disable_caching_explorer
from nuorisovaalitadmin.views.school import xls_response_multiple
from pyramid.url import route_url
from sqlalchemy import func


def voter_submission_stats(request):
    """Renders statistics about the schools who have or have not submitted
    voter information.
    """
    session = DBSession()
    # Total number of schools participating in the electronic voting.
    school_count = session.query(School)\
                    .join(User)\
                    .filter(User.eparticipation == True)\
                    .count()

    # Query the schools that have yet to submit voter information.
    schools_not_submitted = session.query(School)\
                .join(District)\
                .join(User)\
                .filter(User.eparticipation == True)\
                .filter(~School.csvsubmission.any(CSVSubmission.kind == CSVSubmission.VOTER))\
                .order_by(District.name, School.name)\
                .all()

    school_count_not_submitted = len(schools_not_submitted)
    school_count_submitted = school_count - school_count_not_submitted

    submitted = '0.00'
    not_submitted = '100.00'
    if school_count > 0:
        percentage = 100 * school_count_submitted / float(school_count)
        submitted = '{0:.2f}'.format(percentage)
        not_submitted = '{0:.2f}'.format(100 - percentage)

    request.add_response_callback(disable_caching)

    return {
        'title': u'Äänestäjälista-info',
        'school_count': school_count,
        'school_count_submitted': school_count_submitted,
        'school_count_not_submitted': school_count_not_submitted,
        'submitted': submitted,
        'not_submitted': not_submitted,
        'schools_not_submitted': schools_not_submitted,
    }


def result_submission_stats(request):
    """Renders statistics about the schools who have or have not submitted
    paper ballot results.
    """
    session = DBSession()
    # Total number of schools participating in the voting.
    school_count = session.query(School).count()

    schools_not_submitted = session.query(School)\
              .join(District)\
              .filter(~School.csvsubmission.any(CSVSubmission.kind == CSVSubmission.RESULT))\
              .order_by(District.name, School.name)\
              .all()

    school_count_not_submitted = len(schools_not_submitted)
    school_count_submitted = school_count - school_count_not_submitted

    submitted = '0.00'
    not_submitted = '100.00'
    if school_count > 0:
        percentage = 100 * school_count_submitted / float(school_count)
        submitted = '{0:.2f}'.format(percentage)
        not_submitted = '{0:.2f}'.format(100 - percentage)

    request.add_response_callback(disable_caching)

    return {
        'title': u'Tuloslista-info',
        'school_count': school_count,
        'school_count_submitted': school_count_submitted,
        'school_count_not_submitted': school_count_not_submitted,
        'submitted': submitted,
        'not_submitted': not_submitted,
        'schools_not_submitted': schools_not_submitted,
    }


def results_index(request):
    """Index page for the xxxx specific results.

    The results will include:

        * Total results
        * TODO: xxxx needs to provide information what type of results
            they need.
    """
    session = DBSession()

    vote_count = session.query(func.sum(Vote.count)).scalar()
    vote_count_electronic = session.query(func.sum(Vote.count))\
                            .filter(Vote.kind == Vote.ELECTRONIC).scalar()
    if vote_count is None:
        vote_count = 0
    if vote_count_electronic is None:
        vote_count_electronic = 0

    request.add_response_callback(disable_caching)

    voted = '0.00'
    not_voted = '100.00'
    voter_count = session.query(Voter).count()
    if voter_count > 0:
        percentage = 100 * float(vote_count_electronic) / voter_count
        voted = '{0:.2f}'.format(percentage)
        not_voted = '{0:.2f}'.format(100 - percentage)

    return {
        'title': u'Tulokset',
        'vote_count_total': vote_count,
        'vote_count_electronic': vote_count_electronic,
        'voted': voted,
        'not_voted': not_voted,
        'results_total_xls': route_url('results_total_xls', request),
    }


def results_total_xls(request):
    """Downloads the combined results from all districts as an Excel
    spreadsheet with different districts in different sheets."""
    sheets = []

    session = DBSession()
    districts = session.query(District).order_by(District.code)

    for district in districts:
        if district.code == 0:
            continue
        title = u'{0} ({1} kansanedustajapaikka'.format(district.name, district.quota)
        title += ')' if district.quota == 1 else 'a)'
        rows = [
            (title, u'', u'', u'', u''),
            (u'', u'', u'', u'', u''),
            (u'Valitut ehdokkaat', u'', u'', u'', u''),
            (u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'),
        ]
        for i, record in enumerate(dhont_selection(district)):

            # Add a separator between the selected and other candidates.
            if i == district.quota:
                rows.append((u'', u'', u'', u'', u''))
                rows.append((u'Valitsematta jääneet ehdokkaat', u'', u'', u'', u''))
                rows.append((u'Numero', u'Nimi', u'Puolue', u'Äänimäärä', u'Vertailuluku'))

            candidate = record['candidate']
            rows.append((candidate.number,
                         candidate.fullname(),
                         candidate.party.name,
                         record['absolute_votes'],
                         record['proportional_votes']))
        sheets.append((district.name, rows))

    request.add_response_callback(disable_caching_explorer)
    return xls_response_multiple(sheets,
                                 filename='nuorisovaalit2011-valtakunnalliset-tulokset.xls',
                                 num_formats=(None, '@', '@', None, None),
                                 col_widths=(None, 8000, 14000, 3000, 3000))
