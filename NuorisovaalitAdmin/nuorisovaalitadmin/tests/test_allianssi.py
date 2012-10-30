# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.tests import XlsTestCase
from nuorisovaalitadmin.tests import init_testing_db
from nuorisovaalitadmin.tests import populate_testing_db
from pyramid import testing
from pyramid.testing import DummyRequest
from webob import Response

import unittest2 as unittest
import xlrd


class VoterStatsTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_voter_submission_stats__no_schools(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.views.allianssi import voter_submission_stats

        session = DBSession()
        # Check that there is no schools.
        self.assertEquals(0, session.query(School).count())

        options = voter_submission_stats(DummyRequest())
        self.assertEquals(u'Äänestäjälista-info', options['title'])
        self.assertEquals(0, options['school_count'])
        self.assertEquals(0, options['school_count_submitted'])
        self.assertEquals('0.00', options['submitted'])
        self.assertEquals([], list(options['schools_not_submitted']))

    def test_voter_submission_stats__no_submissions(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.allianssi import voter_submission_stats

        session = DBSession()
        populate_testing_db()

        school_names = session.query(School.name)\
                       .join(User)\
                       .filter(User.eparticipation == True)\
                       .order_by(School.name)\
                       .all()
        self.assertTrue(len(school_names) > 0)

        options = voter_submission_stats(DummyRequest())

        # Check that all schools have not submitted by default.
        self.assertEquals(school_names, [(s.name,) for s in options['schools_not_submitted']])

    def test_voter_submission_stats__submissions(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.allianssi import voter_submission_stats

        session = DBSession()
        populate_testing_db()

        eschools = session.query(School)\
                 .join(User)\
                 .filter(User.eparticipation == True)\
                 .all()
        self.assertTrue(len(eschools) > 0)
        school = eschools[0]

        # Check that there is no submission to begin with.
        self.assertEquals(0, session.query(CSVSubmission).count())

        # Add a submission for the school.
        session.add(CSVSubmission({}, school, CSVSubmission.VOTER))
        session.flush()

        school_count = len(eschools)
        school_names_not_submitted = [s.name for s in eschools if s.name != school.name]

        options = voter_submission_stats(DummyRequest())
        options_not_submitted = [s.name for s in options['schools_not_submitted']]
        self.assertEquals(school_count - 1, len(options_not_submitted))
        self.assertEquals(school_names_not_submitted, options_not_submitted)

    def test_voter_submission_stats__submission_with_wrong_kind(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.models import User
        from nuorisovaalitadmin.views.allianssi import voter_submission_stats

        session = DBSession()
        populate_testing_db()

        eschools = session.query(School)\
                 .join(User)\
                 .filter(User.eparticipation == True)\
                 .all()
        self.assertTrue(len(eschools) > 0)
        school = eschools[0]

        # Add a submission for the school.
        session.add(CSVSubmission({}, school, CSVSubmission.RESULT))
        session.flush()

        options = voter_submission_stats(DummyRequest())
        self.assertEquals(len(eschools), len(list(options['schools_not_submitted'])))


class ResultStatsTest(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_result_submission_stats__no_submissions(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.allianssi import result_submission_stats

        session = DBSession()
        school_count = session.query(School).count()

        # Check that there is no submission to begin with.
        self.assertEquals(0, session.query(CSVSubmission)\
                          .filter_by(kind=CSVSubmission.RESULT).count())

        options = result_submission_stats(DummyRequest())

        self.assertEquals(u'Tuloslista-info', options['title'])
        self.assertEquals(school_count, options['school_count'])
        self.assertEquals(0, options['school_count_submitted'])
        self.assertEquals(school_count, options['school_count_not_submitted'])
        self.assertEquals('0.00', options['submitted'])
        self.assertEquals('100.00', options['not_submitted'])

    def test_result_submission_stats__with_submission(self):
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.allianssi import result_submission_stats

        session = DBSession()
        populate_testing_db()
        school_count = session.query(School).count()

        school = session.query(School).first()
        self.assertTrue(school is not None)
        session.add(CSVSubmission({}, school, CSVSubmission.RESULT))
        session.flush()

        options = result_submission_stats(DummyRequest())
        self.assertEquals(u'Tuloslista-info', options['title'])
        self.assertEquals(school_count, options['school_count'])
        self.assertEquals(1, options['school_count_submitted'])
        self.assertEquals(school_count - 1, options['school_count_not_submitted'])
        self.assertEquals('{0:.2f}'.format(100 * 1 / float(school_count)),
                          options['submitted'])
        self.assertEquals('{0:.2f}'.format(100 * (school_count - 1) / float(school_count)),
                          options['not_submitted'])

    def test_result_submission_stats__with_different_kinds_of_schools(self):
        from nuorisovaalit.models import District
        from nuorisovaalit.models import School
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.views.allianssi import result_submission_stats

        session = DBSession()

        # Initial conditions.
        self.assertEquals(0, session.query(District).count())
        self.assertEquals(0, session.query(School).count())
        self.assertEquals(0, session.query(CSVSubmission).count())

        # Populate db.
        district1 = District(u'district 1', 1)
        district2 = District(u'district 2', 2)
        district3 = District(u'district 3', 3)
        session.add(district1)
        session.add(district2)
        session.add(district3)
        session.flush()

        school1 = School(u'schööl 1', district1)
        school2 = School(u'schööl 2', district1)
        school3 = School(u'schööl 3', district2)
        school4 = School(u'schööl 4', district2)
        school5 = School(u'schööl 5', district3)
        school6 = School(u'schööl 6', district3)
        school7 = School(u'schööl 7', district3)
        session.add(school1)
        session.add(school2)
        session.add(school3)
        session.add(school4)
        session.add(school5)
        session.add(school6)
        session.add(school7)
        session.flush()

        session.add(CSVSubmission({}, school3, CSVSubmission.VOTER))
        session.add(CSVSubmission({}, school3, CSVSubmission.RESULT))
        session.add(CSVSubmission({}, school4, CSVSubmission.RESULT))
        session.add(CSVSubmission({}, school5, CSVSubmission.VOTER))
        session.add(CSVSubmission({}, school6, CSVSubmission.RESULT))
        session.add(CSVSubmission({}, school7, CSVSubmission.VOTER))
        session.add(CSVSubmission({}, school7, CSVSubmission.RESULT))
        session.flush()

        options = result_submission_stats(DummyRequest())
        schools_not_submitted = options.pop('schools_not_submitted')

        self.assertEquals([
            u'schööl 1',
            u'schööl 2',
            u'schööl 5',
        ], sorted(s.name for s in schools_not_submitted))

        self.assertEquals({
            'title': u'Tuloslista-info',
            'school_count': 7,
            'school_count_submitted': 4,
            'school_count_not_submitted': 3,
            'submitted': '57.14',
            'not_submitted': '42.86',
        }, options)


class ResultsViewsTest(XlsTestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_results_index__no_votes(self):
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.views.allianssi import results_index

        self.config.add_route('results_total_xls', '/results-total.xls')
        session = DBSession()
        populate_testing_db()

        self.assertEquals(0, session.query(Vote).count())

        self.assertEquals({
            'title': u'Tulokset',
            'vote_count_total': 0,
            'vote_count_electronic': 0,
            'voted': '0.00',
            'not_voted': '100.00',
            'results_total_xls': 'http://example.com/results-total.xls',
        }, results_index(DummyRequest()))

    def test_results_index__with_votes(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.views.allianssi import results_index

        self.config.add_route('results_total_xls', '/results-total.xls')
        session = DBSession()
        populate_testing_db()

        candidate = session.query(Candidate).first()
        school = session.query(School)\
                 .filter_by(district_id=candidate.district_id)\
                 .first()
        self.assertTrue(candidate is not None)
        self.assertTrue(school is not None)

        self.assertEquals(0, session.query(Vote).count())

        session.add(Vote(candidate, school, Vote.PAPER, 15))
        session.add(Vote(candidate, school, Vote.ELECTRONIC))
        session.add(Vote(candidate, school, Vote.ELECTRONIC))

        options = results_index(DummyRequest())
        options.pop('voted')
        options.pop('not_voted')

        self.assertEquals({
            'title': u'Tulokset',
            'vote_count_total': 17,
            'vote_count_electronic': 2,
            'results_total_xls': 'http://example.com/results-total.xls',
        }, options)

    def test_results_total_xls__no_votes(self):
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.views.allianssi import results_total_xls

        session = DBSession()
        populate_testing_db()

        # Add a district with code 0.
        self.assertEquals(0, session.query(District).filter_by(code=0).count())
        session.add(District(u'Tyhjä piiri åäö', 0))
        session.flush()

        self.assertEquals(0, session.query(Vote).count())

        response = results_total_xls(DummyRequest())
        self.assertTrue(isinstance(response, Response))
        self.assertEquals('application/vnd.ms-excel', response.headers['content-type'])
        self.assertEquals('attachment; filename=nuorisovaalit2011-valtakunnalliset-tulokset.xls',
                          response.headers['content-disposition'])

        wb = xlrd.open_workbook(file_contents=response.body)

        district_names = [n[0] for n in session.query(District.name)]
        self.assertTrue(len(district_names) > 1)
        district_names.remove(u'Tyhjä piiri åäö')

        # Cut long names.
        district_names = sorted(d[:31] for d in district_names)

        # Assert that there is a sheet in the Xls file for every
        # district except the one with code 0.
        sheet_names = sorted(wb.sheet_by_index(i).name for i in xrange(len(district_names)))
        self.assertEquals(district_names, sheet_names)
