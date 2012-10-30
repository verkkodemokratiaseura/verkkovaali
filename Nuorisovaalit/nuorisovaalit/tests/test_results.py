# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import date
from decimal import Decimal
from nuorisovaalit.models import DBSession
from nuorisovaalitadmin.tests import init_testing_db

import unittest2 as unittest


class TestDhontSelection(unittest.TestCase):
    """Tests for the election results calculation using the D'Hont method."""

    def setUp(self):
        init_testing_db()

    def tearDown(self):
        DBSession.remove()

    def _populate(self, quota=3):
        """Populates the database with data."""
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.models import District
        from nuorisovaalit.models import DBSession
        from nuorisovaalit.models import Party
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote

        session = DBSession()

        # Pre-conditions
        self.assertEquals(0, session.query(Candidate).count())
        self.assertEquals(0, session.query(Coalition).count())
        self.assertEquals(0, session.query(District).count())
        self.assertEquals(0, session.query(Party).count())
        self.assertEquals(0, session.query(School).count())
        self.assertEquals(0, session.query(Vote).count())

        # Create parties
        parties = [
            Party(u'Köyhien asialla'),
            Party(u'Piraattipuolue'),
            Party(u'Suomen työväenpuolue'),
            Party(u'Valitsijalista'),
            ]

        for p in parties:
            session.add(p)
        session.flush()

        self.assertEquals(4, session.query(Party).count())

        # Create district and school
        district = District(u'Tëst District', 1, quota)
        district.schools.append(School(u'Tëst Schööl'))
        session.add(district)
        session.flush()

        dob = date(1945, 12, 13)

        # Create candidates
        session.add(Candidate(1, u'Candidate', u'0', dob, u'', u'', parties[0], district))
        session.add(Candidate(2, u'Candidate', u'1', dob, u'', u'', parties[0], district))

        session.add(Candidate(3, u'Candidate', u'2', dob, u'', u'', parties[1], district))
        session.add(Candidate(4, u'Candidate', u'3', dob, u'', u'', parties[1], district))

        session.add(Candidate(5, u'Candidate', u'4', dob, u'', u'', parties[2], district))
        session.add(Candidate(6, u'Candidate', u'5', dob, u'', u'', parties[2], district))
        session.add(Candidate(7, u'Candidate', u'6', dob, u'', u'', parties[2], district))

        session.add(Candidate(8, u'Candidate', u'7', dob, u'', u'', parties[3], district))

        session.add(Candidate(Candidate.EMPTY_CANDIDATE, u'Empty', u'candidate', dob, u'', u'', parties[3], district))

        session.flush()
        self.assertEquals(9, len(district.candidates))

        return district

    def _add_votes(self, candidate, votes):
        """Adds votes to the given candidate."""
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote

        kind = Vote.ELECTRONIC if votes == 1 else Vote.PAPER
        session = DBSession()
        session.add(Vote(candidate, session.query(School).first(), kind, votes))
        session.flush()

    def _add_coalition(self, name, district, *parties):
        """Creates a new coalition containing the given parties."""
        from nuorisovaalit.models import Coalition

        session = DBSession()
        coalition = Coalition(name, district)
        for party in parties:
            coalition.parties.append(party)
        session.add(coalition)
        session.flush()

    def assertCandidate(self, record, expected):
        """Asserts that the given record matches the expected values."""
        self.assertEquals(record['candidate'].fullname(), expected['name'])
        self.assertEquals(record['proportional_votes'], expected['proportional_votes'])
        self.assertEquals(record['absolute_votes'], expected['absolute_votes'])

    def assertOrdering(self, *candidates):
        """Asserts that the candidates sort in the given order using the
        secondary sorting key.
        """
        from nuorisovaalit.results import sort_hash
        # Calculate the order based on the secondary hash
        actual_order = sorted(candidates, key=lambda c: sort_hash(c.lastname, c.firstname, c.number), reverse=True)

        for actual, expected in zip(actual_order, candidates):
            self.assertEquals(actual, expected)

    def test_no_coalitions(self):
        """Test the results when there are no coalitions."""
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=3)

        # group 1
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 3)

        # group 2
        self._add_votes(district.candidates[2], 2)
        self._add_votes(district.candidates[3], 4)

        # group 3
        self._add_votes(district.candidates[4], 1)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 4)

        # group 4
        self._add_votes(district.candidates[7], 3)

        winners = dhont_selection(district)

        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate
        self.assertCandidate(winners[0], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('7'),
            'absolute_votes': 4,
            })

        # Second selected candidate
        self.assertCandidate(winners[1], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('6'),
            'absolute_votes': 4,
            })

        # Third selected candidate
        self.assertCandidate(winners[2], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('5'),
            'absolute_votes': 3,
            })

        self.assertCandidate(winners[3], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('3.5'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[4], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[5], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[6], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('2.5'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[7], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('7') / Decimal('3'),
            'absolute_votes': 1,
            })

    def test_only_coalitions(self):
        """Tests when all parties are part of coalitions"""
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.results import dhont_selection

        session = DBSession()
        district = self._populate(quota=3)

        # Create a coalition for Köyhien asialla and Piraattipuolue
        self._add_coalition(u'Red coalition', district, district.candidates[0].party, district.candidates[2].party)
        # Create a coalition for Suomen työväenpuolue and valitsijalista
        self._add_coalition(u'Blue coalition', district, district.candidates[4].party, district.candidates[7].party)
        self.assertEquals(2, session.query(Coalition).count())

        # Create votes for red coalition
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 3)
        self._add_votes(district.candidates[2], 2)
        self._add_votes(district.candidates[3], 4)
        # Create votes for blue coalition
        self._add_votes(district.candidates[4], 1)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 4)
        self._add_votes(district.candidates[7], 3)

        winners = dhont_selection(district)

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate
        self.assertCandidate(winners[0], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('11'),
            'absolute_votes': 4,
            })

        # Second selected candidate
        self.assertCandidate(winners[1], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('10'),
            'absolute_votes': 4,
            })

        # Third selected candidate
        self.assertCandidate(winners[2], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('5.5'),
            'absolute_votes': 3,
            })

        self.assertCandidate(winners[3], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('5'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[4], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('11') / Decimal('3'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[5], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('10') / Decimal('3'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[6], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('11') / Decimal('4'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[7], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('10') / Decimal('4'),
            'absolute_votes': 1,
            })

    def test_mixed_coalitions(self):
        """Tests when some parties are part of coalitions"""
        from nuorisovaalit.models import Coalition
        from nuorisovaalit.results import dhont_selection

        session = DBSession()
        district = self._populate(quota=3)

        # Create a coalition for Köyhien asialla and Piraattipuolue
        self._add_coalition(u'Red coalition', district, district.candidates[0].party, district.candidates[2].party)
        self.assertEquals(1, session.query(Coalition).count())

        # Create votes for red coalition
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 3)
        self._add_votes(district.candidates[2], 2)
        self._add_votes(district.candidates[3], 4)
        # Create votes for Suomen työväenpuolue
        self._add_votes(district.candidates[4], 1)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 4)
        # Create votes for valitsijalista
        self._add_votes(district.candidates[7], 8)

        winners = dhont_selection(district)

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate
        self.assertCandidate(winners[0], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('11'),
            'absolute_votes': 4,
            })

        # Second selected candidate
        self.assertCandidate(winners[1], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('8'),
            'absolute_votes': 8,
            })

        # Third selected candidate
        self.assertCandidate(winners[2], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('7'),
            'absolute_votes': 4,
            })

        self.assertCandidate(winners[3], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('5.5'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[4], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('11') / Decimal('3'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[5], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('3.5'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[6], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('2.75'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[7], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('7') / Decimal('3'),
            'absolute_votes': 1,
            })

    def test_candidates_less_than_quota(self):
        """Test for a case where a quota for a district is larger than the
        number of candidates.

        In reality this will most likely never happen.
        """
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=20)
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 3)

        self._add_votes(district.candidates[2], 2)
        self._add_votes(district.candidates[3], 4)

        self._add_votes(district.candidates[4], 1)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 4)

        self._add_votes(district.candidates[7], 3)

        winners = dhont_selection(district)

        # We can only get back the number of candidates there are, even if it
        # is less than the quota.
        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate
        self.assertCandidate(winners[0], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('7'),
            'absolute_votes': 4,
            })

        # Second selected candidate
        self.assertCandidate(winners[1], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('6'),
            'absolute_votes': 4,
            })

        # Third selected candidate
        self.assertCandidate(winners[2], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('5'),
            'absolute_votes': 3,
            })

        # Fourth selected candidate
        self.assertCandidate(winners[3], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('3.5'),
            'absolute_votes': 2,
            })

        # Fifth selected candidate
        self.assertCandidate(winners[4], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 2,
            })

        # Sixth selected candidate
        self.assertCandidate(winners[5], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })

        # Seventh selected candidate
        self.assertCandidate(winners[6], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('2.5'),
            'absolute_votes': 2,
            })

        # Eighth selected candidate
        self.assertCandidate(winners[7], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('7') / Decimal('3'),
            'absolute_votes': 1,
            })

    def test_tie_in_absolute_votes(self):
        """Tests for the case when two or more candidates get the same amount
        of votes.
        """
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=3)
        # Votes are distributed so that each candidate within a group has the
        # same amount of absolute votes.

        # group 1
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 2)

        # group 2
        self._add_votes(district.candidates[2], 5)
        self._add_votes(district.candidates[3], 5)

        # group 3
        self._add_votes(district.candidates[4], 3)
        self._add_votes(district.candidates[5], 3)
        self._add_votes(district.candidates[6], 3)

        # group 4
        self._add_votes(district.candidates[7], 3)

        winners = dhont_selection(district)

        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate.
        self.assertCandidate(winners[0], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('10'),
            'absolute_votes': 5,
            })

        # Second selected candidate.
        self.assertCandidate(winners[1], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('9'),
            'absolute_votes': 3,
            })

        # Third selected candidate.
        self.assertCandidate(winners[2], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('5'),
            'absolute_votes': 5,
            })

        self.assertCandidate(winners[3], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('4.5'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[4], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('4'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[5], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[6], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[7], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('2'),
            'absolute_votes': 2,
            })

    def test_tie_in_proportional_votes(self):
        """Tests for the case when two or more candidates get the same amount
        of proportional votes.
        """
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=3)
        # Votes are distributed so that each group has the same number of
        # total votes resulting in the tie in the proportional votes.

        # group 1
        self._add_votes(district.candidates[0], 2)
        self._add_votes(district.candidates[1], 6)

        # group 2
        self._add_votes(district.candidates[2], 5)
        self._add_votes(district.candidates[3], 3)

        # group 3
        self._add_votes(district.candidates[4], 2)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 4)

        # group 4
        self._add_votes(district.candidates[7], 8)

        winners = dhont_selection(district)

        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate.
        self.assertCandidate(winners[0], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('8'),
            'absolute_votes': 5,
            })

        # Second selected candidate.
        self.assertCandidate(winners[1], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('8'),
            'absolute_votes': 4,
            })

        # Third selected candidate.
        self.assertCandidate(winners[2], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('8'),
            'absolute_votes': 8,
            })

        self.assertCandidate(winners[3], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('8'),
            'absolute_votes': 6,
            })
        self.assertCandidate(winners[4], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('4'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[5], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('4'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[6], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('4'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[7], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('8') / Decimal('3'),
            'absolute_votes': 2,
            })

    def test_tie_in_both_vote_types(self):
        """Tests for the case when there are ties in both the absolute votes
        and the proportional votes.
        """
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=3)
        # Votes are created so that they result in ties.
        # The second and third group both have a total sum of 6 votes in
        # addition to the individual candidates having the same number of
        # votes.

        # group 1
        self._add_votes(district.candidates[0], 1)
        self._add_votes(district.candidates[1], 1)

        # group 2
        self._add_votes(district.candidates[2], 3)
        self._add_votes(district.candidates[3], 3)

        # group 3
        self._add_votes(district.candidates[4], 2)
        self._add_votes(district.candidates[5], 2)
        self._add_votes(district.candidates[6], 2)

        # group 4
        self._add_votes(district.candidates[7], 3)

        winners = dhont_selection(district)

        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # First selected candidate. The first position is a tie between the
        # second and third group. In each group the candidates have tied also.
        # Of the five possible candidates the secondary sorting key favors
        # candidate 3.
        self.assertCandidate(winners[0], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('6'),
            'absolute_votes': 3,
            })

        # Second selected candidate.
        self.assertCandidate(winners[1], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('6'),
            'absolute_votes': 2,
            })

        # Third selected candidate. The third position is a tie between
        # the left overs from groups two and three with group four. Out of
        # these candidates the secondary sorting key favors candidate 5.
        self.assertCandidate(winners[2], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 2,
            })

        # The remaining candidates that did not fit the quota.

        self.assertCandidate(winners[3], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[4], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('3'),
            'absolute_votes': 3,
            })
        self.assertCandidate(winners[5], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('2'),
            'absolute_votes': 1,
            })
        self.assertCandidate(winners[6], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('2'),
            'absolute_votes': 2,
            })
        self.assertCandidate(winners[7], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('1'),
            'absolute_votes': 1,
            })

    def test_no_votes(self):
        """Test for a case when no candidates have received any votes.

        Not likely to happen in reality.
        """
        from nuorisovaalit.results import dhont_selection

        district = self._populate(quota=8)

        # group 1
        self._add_votes(district.candidates[0], 0)
        self._add_votes(district.candidates[1], 0)

        # group 2
        self._add_votes(district.candidates[2], 0)
        self._add_votes(district.candidates[3], 0)

        # group 3
        self._add_votes(district.candidates[4], 0)
        self._add_votes(district.candidates[5], 0)
        self._add_votes(district.candidates[6], 0)

        # group 4
        self._add_votes(district.candidates[7], 0)

        winners = dhont_selection(district)

        # Assert quota
        self.assertEquals(8, len(winners))

        # Assert the secondary sorting key ordering. The expected ordering
        # was determined manually by evaluating the hashes in an interpreter.
        self.assertOrdering(
            district.candidates[2],
            district.candidates[6],
            district.candidates[5],
            district.candidates[7],
            district.candidates[0],
            district.candidates[4],
            district.candidates[3],
            district.candidates[1],
            )

        # Because all the vote counts are zero the ordering of the candidates
        # is based entirely on the secondary sorting key.

        # First selected candidate
        self.assertCandidate(winners[0], {
            'name': u'2, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Second selected candidate
        self.assertCandidate(winners[1], {
            'name': u'6, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Third selected candidate
        self.assertCandidate(winners[2], {
            'name': u'5, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Fourth selected candidate
        self.assertCandidate(winners[3], {
            'name': u'7, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Fifth selected candidate
        self.assertCandidate(winners[4], {
            'name': u'0, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Sixth selected candidate
        self.assertCandidate(winners[5], {
            'name': u'4, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Seventh selected candidate
        self.assertCandidate(winners[6], {
            'name': u'3, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })

        # Eighth selected candidate
        self.assertCandidate(winners[7], {
            'name': u'1, Candidate',
            'proportional_votes': Decimal('0'),
            'absolute_votes': 0,
            })
