# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import date
from datetime import datetime
from nuorisovaalit.models import DBSession
from nuorisovaalit.tests import init_testing_db
from nuorisovaalit.tests import static_datetime
from pyramid import testing
from pyramid.security import Allow
from pyramid.security import Authenticated


import mock
import unittest2 as unittest


class TestParty(unittest.TestCase):
    """Party tests."""

    def setUp(self):
        init_testing_db()

    def tearDown(self):
        DBSession.remove()

    def test_coalition__no_coalition(self):
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Party

        district = District(u'District X', 1)
        party = Party(u'Foobar')

        session = DBSession()
        session.add_all([district, party])
        session.flush()

        self.assertEquals(None, party.coalition(district))

    def test_coalition__single_coalition(self):
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Party

        district = District(u'District X', 1)
        party = Party(u'Foobar')

        session = DBSession()
        session.add_all([district, party])
        session.flush()

        coalition = Coalition(u'Reds', district)
        session.add(coalition)
        coalition.parties.append(party)
        session.flush()

        self.assertEquals(coalition, party.coalition(district))

    def test_coalition__multiple_coalitions_in_different_districts(self):
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.models import District
        from nuorisovaalit.models import Party

        district_x = District(u'District X', 1)
        district_y = District(u'District Y', 2)

        party = Party(u'Foobar')

        session = DBSession()
        session.add_all([district_x, district_y, party])
        session.flush()

        coalition_x = Coalition(u'Reds', district_x)
        coalition_y = Coalition(u'Blues', district_y)

        session.add_all([coalition_x, coalition_y])
        coalition_x.parties.append(party)
        coalition_y.parties.append(party)

        session.flush()

        self.assertEquals(coalition_x, party.coalition(district_x))
        self.assertEquals(coalition_y, party.coalition(district_y))


class TestCandidate(unittest.TestCase):
    """Candidate tests."""

    def test_is_empty(self):
        from nuorisovaalit.models import Candidate

        empty = Candidate(Candidate.EMPTY_CANDIDATE, u'Empty', u'candidate', date(1945, 12, 13), u'', u'')
        self.failUnless(empty.is_empty())

        real = Candidate(69, u'Real', u'McCoy', date(1945, 12, 13), u'', u'')
        self.failIfEqual(69, Candidate.EMPTY_CANDIDATE)
        self.failIf(real.is_empty())

    def test_fullname__both_names(self):
        from nuorisovaalit.models import Candidate

        candidate = Candidate(69, u'Reäl', u'McCöy', date(1945, 12, 13), u'', u'')
        self.assertEquals(u'McCöy, Reäl', candidate.fullname())

    def test_fullname__firstname_only(self):
        from nuorisovaalit.models import Candidate

        candidate = Candidate(69, u'', u'McCöy', date(1945, 12, 13), u'', u'')
        self.assertEquals(u'McCöy', candidate.fullname())

    def test_fullname__lastname_only(self):
        from nuorisovaalit.models import Candidate

        candidate = Candidate(69, u'Reäl', u'', date(1945, 12, 13), u'', u'')
        self.assertEquals(u'Reäl', candidate.fullname())

    def test_repr(self):
        from nuorisovaalit.models import Candidate

        candidate = Candidate(69, u'Reäl', u'', date(1945, 12, 13), u'', u'')
        self.failUnless(repr(candidate).startswith('<nuorisovaalit.models.Candidate[name=Reäl,number=69] at '))


class TestVote(unittest.TestCase):

    def test_invalid_kind(self):
        from nuorisovaalit.models import Vote

        self.assertRaises(ValueError, lambda: Vote(0, 0, u'Invalid kind'))


class TestVoter(unittest.TestCase):
    """Voter tests."""

    def test_fullname(self):
        from nuorisovaalit.models import Voter

        voter = Voter(u'http://foo.bar.com', u'Buck', u'Rogers', None, None, None, None, None)
        self.assertEquals(u'Buck Rogers', voter.fullname())


class TestRootFactory(unittest.TestCase):
    """Root factory and access control policy tests."""

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 1, 1)))
    def test_permissions__with_skip_test(self):
        from nuorisovaalit.models import RootFactory

        self.config.add_settings({
            'nuorisovaalit.skip_voting_period_check': 'true',
        })
        context = RootFactory(testing.DummyRequest())

        self.assertEquals(context.__acl__, [
            (Allow, Authenticated, 'vote')])

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 1, 1)))
    def test_permissions__before_voting_period(self):
        from nuorisovaalit.models import RootFactory

        self.config.add_settings({
            'nuorisovaalit.skip_voting_period_check': 'false',
        })
        context = RootFactory(testing.DummyRequest())

        self.assertEquals(context.__acl__, [])

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 3, 24)))
    def test_permissions__during_voting_period(self):
        from nuorisovaalit.models import RootFactory

        self.config.add_settings({
            'nuorisovaalit.skip_voting_period_check': 'false',
        })
        context = RootFactory(testing.DummyRequest())

        self.assertEquals(context.__acl__, [
            (Allow, Authenticated, 'vote')])

    @mock.patch('nuorisovaalit.models.datetime', static_datetime(datetime(2011, 4, 1)))
    def test_permissions__after_voting_period(self):
        from nuorisovaalit.models import RootFactory

        self.config.add_settings({
            'nuorisovaalit.skip_voting_period_check': 'false',
        })
        context = RootFactory(testing.DummyRequest())

        self.assertEquals(context.__acl__, [])
