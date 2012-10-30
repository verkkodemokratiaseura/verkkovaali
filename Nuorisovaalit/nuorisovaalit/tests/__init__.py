# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import date
from datetime import datetime
from nuorisovaalit.models import DBSession
from sqlalchemy import create_engine


def static_datetime(static_datetime):
    """Returns a modified ``datetime.datetime`` class with a static .now()
    method which returns the given ``date`` which must be an instance of
    ``datetime.datetime``."""
    if not isinstance(static_datetime, datetime):
        raise TypeError('The static datetime must be an instance of datetime.datetime.')

    class StaticNow(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return static_datetime

    return StaticNow


def init_testing_db(echo=False):
    from nuorisovaalit.models import initialize_sql
    engine = create_engine('sqlite:///', echo=echo)
    session = initialize_sql(engine)
    return session


def populate_testing_db():
    """Populates the session with testing data."""
    from nuorisovaalit.models import Candidate
    from nuorisovaalit.models import District
    from nuorisovaalit.models import Party
    from nuorisovaalit.models import School
    from nuorisovaalit.models import Voter
    from itertools import count

    DISTRICTS = {
        (u'Ahvenanmaan maakunnan vaalipiiri', 1): {
            u'schools': (u'Brändö', u'Eckerö', u'Föglö'),
            u'candidates': (u'xxxx xxxx', u'xxxx xxxx', u'xxxx xxxx'),
            },
        (u'Etelä-Savon vaalipiiri', 2): {
            u'schools': (u'Heinävesi', u'Hirvensalmi'),
            u'candidates': (u'xxxx xxxx', u'xxxx xxxx', u'xxxx xxxx'),
        },
    }

    session = DBSession()

    # Check that there are no records in the db.
    assert session.query(Candidate).count() == 0
    assert session.query(District).count() == 0
    assert session.query(Party).count() == 0
    assert session.query(School).count() == 0
    assert session.query(Voter).count() == 0

    # Create parties
    parties = [
        Party(u'Köyhien asialla'),
        Party(u'Piraattipuolue'),
        Party(u'Suomen työväenpuolue'),
        ]

    for p in parties:
        session.add(p)
    session.flush()

    assert session.query(Party).count() == 3

    # Create the districts and schools.
    for (distname, code), rest in sorted(DISTRICTS.items()):
        district = District(distname, code, 5)

        for mname in rest['schools']:
            district.schools.append(School(u'{0} koulu'.format(mname)))

        session.add(district)
        session.flush()

        cnumber = count(1)
        for index, cname in enumerate(rest['candidates']):
            party = parties[index % len(parties)]
            candidate = Candidate(cnumber.next(), cname.split()[0], cname.split()[1], date(xxxx, xx, xx), u'xxxx', u'xxxx', party, district)
            session.add(candidate)

        session.add(district)

    session.flush()
    districts = session.query(District).order_by(District.name).all()

    session.add(Voter(
        u'http://example.com/id/matti.meikalainen',
        u'Matti', u'Meikäläinen',
        date(1970, 1, 1), u'123 456789',
        u'matti.meikalainen@example.com',
        u'Mynämäkitie 1, Mynämäki',
        districts[0].schools[0]))

    session.add(Voter(
        u'http://example.com/id/maija.meikalainen',
        u'Maija', u'Meikäläinen',
        date(1979, 1, 1), u'987 654321',
        u'maija.meikalainen@example.com',
        u'Vääksyntie1, Sysmä',
        districts[1].schools[0]))

    # Create the empty candidate. We need to create a district and party to
    # satisfy the database constraints but these are not used for anything.
    empty_district = District(u'Tyhjä', 3)
    empty_party = Party(u'Tyhjä')
    session.add(empty_district)
    session.add(empty_party)
    session.flush()
    empty_candidate = Candidate(Candidate.EMPTY_CANDIDATE, u'Tyhjä', u'Tyhjä', date(1999, 1, 1), u'Tyhjä', u'Tyhjä', empty_party, empty_district)
    session.add(empty_candidate)

    session.flush()
