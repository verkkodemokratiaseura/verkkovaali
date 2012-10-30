# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from nuorisovaalit.models import DBSession
from nuorisovaalit.tests import init_testing_db
from nuorisovaalit.tests import populate_testing_db
from pyramid import testing
from pyramid.exceptions import Forbidden
from pyramid.testing import DummyRequest


import unittest2 as unittest


class TestCandidateSelection(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_select__unauthenticated(self):
        from nuorisovaalit.views.voting import select

        self.assertRaises(Forbidden, lambda: select(DummyRequest()))

    def test_select__already_voted(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalit.views.voting import select
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('vote-finish', '/valmis')

        session = DBSession()
        session.add(VotingLog(voter.id))

        request = DummyRequest()
        response = select(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('vote-finish', request), response.location)

    def test_select__with_candidates(self):
        from itertools import cycle
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import select

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.testing_securitypolicy(userid=voter.openid)

        self.config.add_route('vote', '/aanesta/{number}')
        options = select(DummyRequest())

        for party in options['parties']:
            self.assertTrue(isinstance(party.pop('positions'), cycle))
            party['candidates'] = list(party['candidates'])

        self.assertEquals({
            'coalitions': [],
            'columns': 3,
            'district': u'Ahvenanmaan maakunnan vaalipiiri',
            'empty_vote_url': 'http://example.com/aanesta/0',
            'parties': [{
                'candidates': [[{'name': u'Turhapuro, Uuno',
                                 'number': 1,
                                 'url': 'http://example.com/aanesta/1'}]],
                'title': u'Köyhien asialla'
                }, {
                'candidates': [[{'name': u'Hartikainen, Härski',
                                 'number': 2,
                                 'url': 'http://example.com/aanesta/2'}]],
                'title': u'Piraattipuolue'
                }, {
                'candidates': [[{'name': u'Sörsselssön, Sami',
                                 'number': 3,
                                 'url': 'http://example.com/aanesta/3'}]],
                'title': u'Suomen työväenpuolue'}
            ]
        }, options)

    def test_select_party_grouping_with_coalitions(self):
        from datetime import datetime
        from itertools import cycle
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Party
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import select

        session = DBSession()

        # Populate the db.
        district = District(u'Distrïct', 1)
        session.add(district)
        session.flush()
        school = School(u'Schööl', district)
        session.add(school)
        session.flush()
        voter = Voter(u'http://test.user@did.fi', u'test', u'user', datetime(2011, 1, 1),
                      gsm=None, email=None, address=None, school_or_id=school)
        session.add(voter)
        session.flush()

        party1 = Party(u'Först party')
        party2 = Party(u'Secönd party')
        session.add(party1)
        session.add(party2)
        session.flush()

        coalition = Coalition(u'Red coalition', district)
        coalition.parties.append(party1)
        coalition.parties.append(party2)
        session.add(coalition)

        party1.candidates.append(Candidate(2, u'Mätti2', u'Meikäläinen', datetime(2011, 1, 1),
                                           u'', u'', party1, district))
        party1.candidates.append(Candidate(3, u'Mätti3', u'Meikäläinen', datetime(2011, 1, 1),
                                           u'', u'', party1, district))
        party1.candidates.append(Candidate(4, u'Mätti4', u'Meikäläinen', datetime(2011, 1, 1),
                                           u'', u'', party1, district))
        party1.candidates.append(Candidate(5, u'Mätti5', u'Meikäläinen', datetime(2011, 1, 1),
                                           u'', u'', party1, district))
        party2.candidates.append(Candidate(2, u'Mäijä2', u'Meikäläinen', datetime(2011, 1, 1),
                                           u'', u'', party2, district))
        session.flush()

        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('vote', '/aanesta/{number}')
        options = select(DummyRequest())

        # Remove the cycle generators and serialize the candidate generators
        # for easiear comparison.
        for party in options['parties']:
            self.assertTrue(isinstance(party.pop('positions'), cycle))
            party['candidates'] = list(party['candidates'])

        self.assertEquals(options, {
            'empty_vote_url': 'http://example.com/aanesta/0',
            'district': u'Distrïct',
            'coalitions': [u'Först party, Secönd party'],
            'columns': 3,
            'parties': [
                {'candidates': [
                    [{'url': 'http://example.com/aanesta/2',
                      'number': 2,
                      'name': u'Meikäläinen, Mätti2'},
                     {'url': 'http://example.com/aanesta/3',
                      'number': 3,
                      'name': u'Meikäläinen, Mätti3'}],
                    [{'url': 'http://example.com/aanesta/4',
                      'number': 4,
                      'name': u'Meikäläinen, Mätti4'}],
                    [{'url': 'http://example.com/aanesta/5',
                      'number': 5,
                      'name': u'Meikäläinen, Mätti5'}]],
                 'title': u'Först party'},
                {'candidates': [
                    [{'url': 'http://example.com/aanesta/2',
                      'number': 2,
                      'name': u'Meikäläinen, Mäijä2'}]],
                 'title': u'Secönd party'}]})


class TestVoting(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_vote__unauthenticated(self):
        from nuorisovaalit.views.voting import vote

        self.assertRaises(Forbidden, lambda: vote(DummyRequest()))

    def test_vote__already_voted(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalit.views.voting import vote
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('vote-finish', '/valmis')

        session = DBSession()

        # Add a voting record for the voter.
        session.add(VotingLog(voter.id))

        request = DummyRequest()
        response = vote(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('vote-finish', request), response.location)

    def test_vote__invalid_candidate_number(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.exceptions import NotFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.config.testing_securitypolicy(userid=voter.openid)

        request = DummyRequest()
        request.matchdict['number'] = 666

        self.assertRaises(NotFound, lambda: vote(request))

    def test_vote__returned_options(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.matchdict['number'] = '1'

        options = vote(request)

        self.assertEquals({
            'action_url': request.path_url,
            'select_url': route_url('select', request),
            'candidate': {
                'number': 1,
                'name': u'Turhapuro, Uuno',
            },
            'profile': {
                'fullname': u'Matti Meikäläinen',
                'district': u'Ahvenanmaan maakunnan vaalipiiri',
            },
            'error': False,
            'csrf_token': csrf_token
        }, options)

    def test_vote_invalid_csrf_token(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest(post=dict(vote='1'))
        csrf_token = request.session.new_csrf_token()
        bad_token = 'bad token {0}'.format(csrf_token)
        request.POST['csrf_token'] = bad_token
        request.matchdict['number'] = '2'

        options = vote(request)
        self.assertTrue(options['error'])
        self.assertEquals(csrf_token, options['csrf_token'])

    def test_vote__candidate_number_mismatch(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest(post=dict(vote='1'))
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token
        request.matchdict['number'] = '2'

        options = vote(request)
        self.assertTrue(options['error'])
        self.assertEquals(csrf_token, options['csrf_token'])

    def test_vote__successful_voting_response_for_empty_vote(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.add_route('vote-finish', '/valmis')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest(post=dict(vote=str(Candidate.EMPTY_CANDIDATE)))
        request.POST['csrf_token'] = request.session.new_csrf_token()
        request.matchdict['number'] = str(Candidate.EMPTY_CANDIDATE)

        response = vote(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('vote-finish', request), response.location)

    def test_vote__successful_voting_response(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.add_route('vote-finish', '/valmis')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        request = DummyRequest(post=dict(vote='1'))
        request.POST['csrf_token'] = request.session.new_csrf_token()
        request.matchdict['number'] = '1'

        response = vote(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('vote-finish', request), response.location)

    def test_vote__successful_vote_log(self):
        from nuorisovaalit.models import Vote
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog
        from nuorisovaalit.views.voting import vote
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.add_route('select', '/valitse')
        self.config.add_route('vote-finish', '/valmis')
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)

        session = DBSession()

        request = DummyRequest(post=dict(vote='1'))
        request.POST['csrf_token'] = request.session.new_csrf_token()
        request.matchdict['number'] = '1'

        # Check the initial conditions.
        self.assertEquals(0, session.query(VotingLog).count())
        self.assertEquals(0, session.query(Vote).count())

        vote(request)

        # Check that the vote was recorded.
        self.assertEquals(1, session.query(VotingLog).count())
        self.assertEquals(1, session.query(Vote).count())

        # Check that the vote record info is correct.
        vote_record = session.query(Vote).first()
        self.assertEquals(u'Uuno', vote_record.candidate.firstname)
        self.assertEquals(u'Turhapuro', vote_record.candidate.lastname)
        self.assertEquals(u'xxxx xxxx', vote_record.school.name)


class TestOpenIdPreference(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_exit_voting__empty_param(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import exit_voting
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)

        self.config.add_route('close-window', '/close-window')
        request = DummyRequest()

        response = exit_voting(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('close-window', request), response.location)

    def test_exit_voting__declined(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import exit_voting
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')

        request = DummyRequest(post=dict(use_open_identity='no'))

        response = exit_voting(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('close-window', request), response.location)

    def test_exit_voting__successful(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import exit_voting
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from pyramid.url import route_url
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')

        request = DummyRequest(post=dict(use_open_identity='yes'))
        request.POST['csrf_token'] = request.session.new_csrf_token()

        response = exit_voting(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals(route_url('close-window', request), response.location)


class TestVoteFinishing(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_vote_finish__unauthenticated(self):
        from nuorisovaalit.views.voting import vote_finish

        populate_testing_db()
        self.assertRaises(Forbidden, lambda: vote_finish(DummyRequest()))

    def test_vote_finish__invalid_csrf_token(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('exit-voting', '/exit')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': 'invalid {0}'.format(csrf_token),
        }

        self.assertRaises(Forbidden, lambda: vote_finish(request))

    def test_vote_finish__message_vote_saved(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('vote-finish', '/valmis')

        self.assertEquals(u'Äänesi on tallennettu', vote_finish(DummyRequest())['message'])

    def test_vote_finish__message_already_voted(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        request.session['vote_registered'] = 'yes'

        self.assertEquals(u'Olet jo äänestänyt', vote_finish(request)['message'])

    def test_vote_finish__no_pref_selected_no_address(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())
        voter.address = None

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('exit-voting', '/exit')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': None,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': False,
            'errors': [],
            'voter': voter,
            'gsm': voter.gsm,
            'email': voter.email,
            'street': u'',
            'zipcode': u'',
            'city': u'',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__no_pref_selected_invalid_address(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())
        voter.address = u'söme Äddress 123, city'

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('exit-voting', '/exit')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': None,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': False,
            'errors': [],
            'voter': voter,
            'gsm': voter.gsm,
            'email': voter.email,
            'street': u'söme Äddress 123, city',
            'zipcode': u'',
            'city': u'',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__no_pref_selected_valid_address(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())
        voter.address = u'Äyrävänpolku 666, 09123 Mikä-mikämaa, Pohjoisnapa'

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('exit-voting', '/exit')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST['csrf_token'] = csrf_token

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': None,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': False,
            'errors': [],
            'voter': voter,
            'gsm': voter.gsm,
            'email': voter.email,
            'street': u'Äyrävänpolku 666',
            'zipcode': u'09123',
            'city': u'Mikä-mikämaa, Pohjoisnapa',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__form_submitted_already_has_pref(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        voter.accept_openid = False
        self.assertEquals(True, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
        }

        response = vote_finish(request)
        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals('http://example.com/close-window', response.location)
        self.assertEquals(False, voter.accept_openid)

    def test_vote_finish__declined(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
            'use_open_identity': u'no',
        }

        response = vote_finish(request)

        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals('http://example.com/close-window', response.location)
        self.assertEquals(False, voter.accept_openid)
        self.assertEquals(True, voter.has_preference())

    def test_vote_finish__accepted_empty_fields(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'csrf_token': csrf_token,
            'use_open_identity': 'yes',
            'gsm': u'',
            'email': u'',
            'street': u'',
            'zipcode': u'',
            'city': u'',
            'form.submitted': u'1',
        }

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': True,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': True,
            'errors': [
                u'GSM-numero on virheellinen, esimerkki oikeasta muodosta "0501234567".',
                u'Sähköpostiosoite on virheellinen, esimerkki oikeasta muodosta "matti@meikalainen.fi".',
                u'Katuosoite puuttuu.',
                u'Postinumero on virheellinen, esimerkki oikeasta muodosta "12345".',
                u'Postitoimipaikka puuttuu.',
            ],
            'voter': voter,
            'gsm': u'',
            'email': u'',
            'street': u'',
            'zipcode': u'',
            'city': u'',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__accepted_invalid_fields(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
            'use_open_identity': 'yes',
            'gsm': u'invalid gsm',
            'email': u'invalid email',
            'street': u'',
            'zipcode': u'00000',
            'city': u'-',
        }

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': True,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': True,
            'errors': [
                u'GSM-numero on virheellinen, esimerkki oikeasta muodosta "0501234567".',
                u'Sähköpostiosoite on virheellinen, esimerkki oikeasta muodosta "matti@meikalainen.fi".',
                u'Katuosoite puuttuu.',
            ],
            'voter': voter,
            'gsm': u'invalid gsm',
            'email': u'invalid email',
            'street': u'',
            'zipcode': u'00000',
            'city': u'-',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__accepted_some_invalid_fields(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
            'use_open_identity': 'yes',
            'gsm': u'   00358- 40 1234 567',
            'email': u'valid@example.com   \t',
            'street': u'',
            'zipcode': u'',
            'city': u'',
        }

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': True,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': True,
            'errors': [
                u'Katuosoite puuttuu.',
                u'Postinumero on virheellinen, esimerkki oikeasta muodosta "12345".',
                u'Postitoimipaikka puuttuu.',
            ],
            'voter': voter,
            'gsm': u'   00358- 40 1234 567',
            'email': u'valid@example.com   \t',
            'street': u'',
            'zipcode': u'',
            'city': u'',
        }, vote_finish(request))
        self.assertEquals(False, voter.has_preference())

    def test_vote_finish__accepted_valid_submission(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig
        from webob.exc import HTTPFound

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
            'use_open_identity': 'yes',
            'gsm': u'   00358- 40 1234 567',
            'email': u'valid@example.com   \t',
            'street': u'   söme stréét',
            'zipcode': u'  09123',
            'city': u' citÜ',
        }

        response = vote_finish(request)

        self.assertTrue(isinstance(response, HTTPFound))
        self.assertEquals('http://example.com/close-window', response.location)
        self.assertEquals(True, voter.accept_openid)
        self.assertTrue(voter.has_preference())
        self.assertEquals(u'00358401234567', voter.gsm)
        self.assertEquals(u'valid@example.com', voter.email)
        self.assertEquals(u'söme stréét, 09123, citÜ', voter.address)

    def test_vote_finish__preference_selection_missing(self):
        """Tests a case where the OpenID selection (yes or no) is missing."""
        from nuorisovaalit.models import Voter
        from nuorisovaalit.views.voting import vote_finish
        from pyramid.session import UnencryptedCookieSessionFactoryConfig

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()
        self.assertEquals(False, voter.has_preference())

        self.config.set_session_factory(UnencryptedCookieSessionFactoryConfig)
        self.config.testing_securitypolicy(userid=voter.openid)
        self.config.add_route('close-window', '/close-window')
        self.config.add_route('vote-finish', '/valmis')

        request = DummyRequest()
        csrf_token = request.session.new_csrf_token()
        request.POST = {
            'form.submitted': u'1',
            'csrf_token': csrf_token,
            'gsm': u'   00358- 40 1234 567',
            'email': u'valid@example.com   \t',
            'street': u'   söme stréét',
            'zipcode': u'  09123',
            'city': u' citÜ',
        }

        self.assertEquals({
            'action_url': 'http://example.com/valmis',
            'csrf_token': csrf_token,
            'accept_openid': None,
            'message': u'Äänesi on tallennettu',
            'has_preference': False,
            'pref_selected': False,
            'errors': [
                u'Valitse haluatko verkkovaikuttajaidentiteetin.',
            ],
            'voter': voter,
            'gsm': u'   00358- 40 1234 567',
            'email': u'valid@example.com   \t',
            'street': u'   söme stréét',
            'zipcode': u'  09123',
            'city': u' citÜ',
        }, vote_finish(request))
        self.failIf(voter.has_preference())

    def test_close_window(self):
        from nuorisovaalit.views.voting import close_window
        request = DummyRequest()
        self.assertEquals({}, close_window(request))


class TestUtilities(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        init_testing_db()

    def tearDown(self):
        DBSession.remove()
        testing.tearDown()

    def test_split_candidates__boundary_cases(self):
        from nuorisovaalit.views.voting import split_candidates

        candidates = range(1)
        columns = list(split_candidates(candidates, 3))
        self.assertEquals(1, len(columns))
        self.assertEquals(columns, [[0]])

        candidates = range(2)
        columns = list(split_candidates(candidates, 3))
        self.assertEquals(2, len(columns))
        self.assertEquals(columns, [[0], [1]])

        candidates = range(3)
        columns = list(split_candidates(candidates, 3))
        self.assertEquals(3, len(columns))
        self.assertEquals(columns, [[0], [1], [2]])

        candidates = range(4)
        columns = list(split_candidates(candidates, 3))
        self.assertEquals(3, len(columns))
        self.assertEquals(columns, [[0, 1], [2], [3]])

    def test_split_candidates__divisible_by_columns(self):
        from nuorisovaalit.views.voting import split_candidates
        candidates = range(12)
        columns = list(split_candidates(candidates, 3))

        self.assertEquals(3, len(columns))
        self.assertEquals(columns, [
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [8, 9, 10, 11]])

    def test_split_candidate__odd_sized_columns(self):
        from nuorisovaalit.views.voting import split_candidates
        candidates = range(13)
        columns = list(split_candidates(candidates, 3))

        self.assertEquals(3, len(columns))
        self.assertEquals(columns, [
            [0, 1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12]])

    def test_has_voted__negative(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        session = DBSession()
        populate_testing_db()
        # Make sure no-one has voted
        self.assertEquals(0, session.query(VotingLog).count())

        # Make sure that a given user has not voted.
        voter = session.query(Voter).first()
        self.failIf(voter.has_voted())

    def test_has_voted__positive(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        session = DBSession()
        # Create a voting log entry for the voter id.
        session.add(VotingLog(voter.id))
        self.assertEquals(1, session.query(VotingLog).count())

        # Assert
        self.failUnless(voter.has_voted())

    def test_has_voted__negative_with_other_user_voted(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalit.models import VotingLog

        session = DBSession()
        populate_testing_db()
        voter = session.query(Voter).first()

        session = DBSession()
        # Add a voting log entry for a different voter id.
        session.add(VotingLog(voter.id + 1))
        self.assertEquals(1, session.query(VotingLog).count())

        # Assert that the voter has not voted.
        self.failIf(voter.has_voted())
