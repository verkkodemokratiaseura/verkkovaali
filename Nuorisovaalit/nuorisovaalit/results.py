# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
"""Election results.

This module provides functionality for calculating the results of the
election. The results are calculated using the D'Hondt method (see
http://en.wikipedia.org/wiki/D'Hondt_method).

For a Finnish explanation of the results calculation process refer to

  http://www.vaalit.fi/34845.htm.

The Finnish legislation for results calculation is at

  http://www.finlex.fi/fi/laki/ajantasa/1998/19980714

and the most relevant parts are in sections 89§ - 91§.

The simplify the terminology used in the documentation and comments we will
use the term "party" to refer to both political parties and other groupings
and "coalition" to refer to groupings of these "parties".

The results are calculated in the following manner per voting district:

 1. Split the parties into groups based on their coalitions, if available.
    Each group will be compared to others in subsequent steps.

 2. Calculate the total amount of votes received per group (GRP_TOTAL_VOTES).

 3. Sort the candidates within a group in descending order based on the votes
    they received.

 4. Assign a proportial representation (GRP_PR_VOTES) number to each candidate
    within a group so that for the

    - candidate with most votes GRP_PR_VOTES = GRP_TOTAL_VOTES / 1

    - candidate with second most votes GRP_PR_VOTES = GRP_TOTAL_VOTES / 2

    - candidate with N most votes GRP_PR_VOTES = GRP_TOTAL_VOTES / N

    where N grows up to the maximum number of seats available within the
    voting district.

 5. Sort the candidates based on their GRP_PR_VOTES values.

Edge cases
----------

Section 90§ of the Finnish election states that

 "Jos äänimäärät tai vertausluvut ovat yhtä suuret, niiden keskinäinen
  järjestys ratkaistaan arpomalla."

The "random" ordering is not specified in more detail but for the
implementation it is important to provide a consistent ordering in these
cases. To maintain a consistent pseudo-random ordering for the candidates with
equal vote counts we use the following two-tuple for the sorting key

  (vote_count, sort_hash(candidate.lastname, candidate.firstname, candidate.number))

Where the sort_hash() function calculates a salted SHA1 hash over the
candidate name and number and the resulting hash provides a consistent
secondary ordering for tied votes.
"""
from decimal import Decimal

import hashlib


def sort_hash(*items):
    """Returns a salted hash calculated over the given items."""
    def bytes(o):
        return item.encode('utf-8') if isinstance(o, unicode) else str(o)

    h = hashlib.sha1('5f2b5e892dc48fc7bd3372a0fae18b0719ea57ba')
    for item in items:
        h.update(bytes(item))
    return h.digest()


def dhont_selection(district):
    """Selects the candidates that get selected in the election from the given
    voting district.

    Returns a list of dictionaries with the following structure:

      {
        'candidate': <nuorisovaalit.models.Candidate>,
        'absolute_votes': <int>,
        'proportional_votes': <decimal.Decimal>,
      }

    :param district: The voting district to select the candidates from.
    :type district: :py:class:`nuorisovaalit.models.

    :rtype: list
    """
    # Step 1: Split candidates into groups.
    groups = {}
    for candidate in district.candidates:
        if candidate.is_empty():
            # Empty votes are explicitly removed from the results.
            continue

        coalition = candidate.party.coalition(district)
        if coalition is None:
            # The party is not a member of any coalition
            group_id = u'<party>' + unicode(candidate.party.id)
        else:
            # The party is a member of a coalition which will group all of
            # its members.
            group_id = u'<coalition>' + unicode(coalition.id)

        groups.setdefault(group_id, []).append({
            'candidate': candidate,
            'absolute_votes': candidate.vote_count(),
            'proportional_votes': Decimal(0),
            })

    # Step 2: Calculate the total votes per group.
    GRP_TOTAL_VOTES = {}
    for gid, candidates in groups.iteritems():
        GRP_TOTAL_VOTES[gid] = sum(candidate['absolute_votes'] for candidate in candidates)

    # Step 3: Sort candidates according to received votes.
    for candidates in groups.itervalues():
        candidates.sort(
            key=lambda r: (r['absolute_votes'], sort_hash(r['candidate'].lastname, r['candidate'].firstname, r['candidate'].number)),
            reverse=True)

    # Step 4: Assign proportional representation numbers.
    for gid, candidates in groups.iteritems():
        for divisor, candidate in enumerate(candidates, start=1):
            candidate['proportional_votes'] = GRP_TOTAL_VOTES[gid] / Decimal(divisor)

    # Step 5: Sort all the candidates based on their proportional votes.
    all_candidates = (record for candidates in groups.itervalues() for record in candidates)
    proportional = sorted(all_candidates,
        key=lambda r: (r['proportional_votes'], sort_hash(r['candidate'].lastname, r['candidate'].firstname, r['candidate'].number)),
        reverse=True)

    return proportional
