# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import date
from nuorisovaalit.models import Candidate
from nuorisovaalit.models import Coalition
from nuorisovaalit.models import DBSession
from nuorisovaalit.models import District
from nuorisovaalit.models import Party
from nuorisovaalit.models import School
from nuorisovaalit.models import Voter
from nuorisovaalit.models import initialize_sql
from nuorisovaalit.scripts import parse_districts
from paste.deploy import appconfig
from sqlalchemy import engine_from_config
from urlparse import urlparse

import os
import re
import sys
import transaction
import xlrd

RE_DOB = re.compile(ur'^(\d{2})(\d{2})(\d{2})$')


def get_config():
    if len(sys.argv) < 2:
        print("Usage: {0} <config>".format(sys.argv[0]))
        sys.exit(1)

    config_uri = 'config:{0}#nuorisovaalit'.format(
        os.path.join(os.getcwd(), sys.argv[1].strip()))

    return appconfig(config_uri)


def datafile(path):
    return os.path.join(os.path.dirname(__file__), path)


def create_districts():
    """Populates the database with information about the voting districts.
    """
    session = DBSession()
    districts = parse_districts(
        seats=datafile('../data/paikkamaarat.txt'),
        municipalities=datafile('../data/luokitusavain_kunta_teksti.txt'))

    # Create voting districts and municipalities
    for (distname, code, seats), municipalities in districts.iteritems():
        session.add(District(u'{0} vaalipiiri'.format(distname), code, seats))

    session.flush()


def populate_districts():
    """Populates the database with election districts and municipalities."""
    config = get_config()
    engine = engine_from_config(config, 'sqlalchemy.')
    initialize_sql(engine)
    engine.echo = False

    create_districts()
    transaction.commit()


def populate_candidates():
    """Populates the database with candidate information.

    The information is read from two files. The first file contains the list
    of candidates and parties and the second file contains the information
    about coalitions.

    Based on the information we create the following types of objects in the
    database:

        * Candidate
        * Party
        * Coalition

    It is also assumed that the database has already been populated with the
    voting districts because both candidates and coalitions are always
    directly related to a given voting district.

    Additionally, this script creates the necessary objects to facilitate
    casting an empty vote.
    """
    config = get_config()
    engine = engine_from_config(config, 'sqlalchemy.')
    initialize_sql(engine)
    engine.echo = False

    if len(sys.argv) < 4:
        print("Usage: {0} <config> <candidate> <coalitions>".format(sys.argv[0]))
        transaction.abort()
        sys.exit(1)

    def fail_unless(condition, message):
        """Assert the given condition and upon failure prints out the message
        and aborts the current transaction.
        """
        if not condition:
            print message
            print "Aborting transaction"
            transaction.abort()
            # Raise an error instead of calling sys.exit(1) to better facilitate testing
            raise ValueError(message)

    # Mapping for party abbreviations to full titles.
    party_names = {
       u'AFÅ': u'Gemensam lista Alliansen för Åland - samarbete för självstyrelse och utveckling',
       u'ÅS': u'Åländsk samling gemensam lista',
       u'E109': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E119': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E133': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E157': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E159': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E266': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E267': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E268': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E404': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E405': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E406': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'E407': u'Yhteislistoihin kuulumattomien valitsijayhdistysten ehdokkaat',  # u'xxxx xxxx',
       u'ITSP': u'Itsenäisyyspuolue',
       u'KD': u'Suomen Kristillisdemokraatit (KD)',
       u'KESK': u'Suomen Keskusta',
       u'KOK': u'Kansallinen Kokoomus',
       u'KÖY': u'Köyhien Asialla',
       u'KTP': u'Kommunistinen Työväenpuolue - Rauhan ja Sosialismin puolesta',
       u'M11': u'Muutos 2011',
       u'PIR': u'Piraattipuolue',
       u'PS': u'Perussuomalaiset',
       u'RKP': u'Suomen ruotsalainen kansanpuolue',
       u'SDP': u'Suomen Sosialidemokraattinen Puolue',
       u'SKP': u'Suomen Kommunistinen Puolue',
       u'SSP': u'Suomen Senioripuolue',
       u'STP': u'Suomen Työväenpuolue STP',
       u'VAS': u'Vasemmistoliitto',
       u'VIHR': u'Vihreä liitto',
       u'VP': u'Vapauspuolue (VP) - Suomen tulevaisuus',
       u'YS': u'Yhteislista sitoutumattomat',
    }

    session = DBSession()

    # Create the objects to support casting an empty vote.
    print "Setting up support for empty votes."
    empty_district = District(u'Tyhjä', 0)
    empty_party = Party(u'Tyhjä')
    session.add_all([empty_district, empty_party])
    session.flush()
    session.add(Candidate(Candidate.EMPTY_CANDIDATE, u'Tyhjä', u'', date(1999, 1, 1), u'Tyhjä', u'Tyhjä', empty_party, empty_district))

    # Create Party objects.
    parties = {}
    print "Creating parties"
    for abbr, title in party_names.iteritems():
        party = Party(title)
        session.add(party)
        parties[abbr] = party
        print " - ", party.name.encode('utf-8')
    print
    session.flush()

    party_abbrevs = set(parties.keys())
    districts = dict((d.code, d) for d in session.query(District).all())

    # Read in the coalition information.
    # The excel sheet contains the district code, district name and a comma
    # separated list of party abbreviations.
    wb = xlrd.open_workbook(filename=os.path.join(os.getcwd(), sys.argv[3]))
    ws = wb.sheet_by_index(0)
    coalition_count = 0
    print "Creating coalitions"
    for row in xrange(ws.nrows):
        code = int(ws.cell_value(row, 0))
        abbrevs = set(p.strip() for p in ws.cell_value(row, 2).strip().split(u',') if p.strip())

        # Assert that the party abbreviations are all known.
        fail_unless(abbrevs.issubset(party_abbrevs), 'Unknown parties in: {0}'.format(abbrevs))
        # Assert the voting district code refers to a valid district.
        fail_unless(code in districts, 'Unknown voting district code: {0}'.format(code))

        if len(abbrevs):
            coalition = Coalition(u', '.join(sorted(abbrevs)), districts[code])
            for party_id in abbrevs:
                coalition.parties.append(parties[party_id])

            session.add(coalition)
            coalition_count += 1
            print " - '{0}' in {1}.".format(coalition.name.encode('utf-8'), districts[code].name.encode('utf-8'))
    session.flush()

    # Read in the candidate information
    wb = xlrd.open_workbook(filename=os.path.join(os.getcwd(), sys.argv[2]))
    ws = wb.sheet_by_index(0)
    candidate_count = 0
    print
    print "Creating candidates"
    for row in xrange(1, ws.nrows):
        code = int(ws.cell_value(row, 0))
        number = int(ws.cell_value(row, 2))
        firstname = unicode(ws.cell_value(row, 5).strip())
        lastname = unicode(ws.cell_value(row, 4).strip())
        municipality = unicode(ws.cell_value(row, 6).strip())
        occupation = unicode(ws.cell_value(row, 7).strip())
        party_id = unicode(ws.cell_value(row, 8).strip())

        # Assert the party abbreviation refers to a known party.
        fail_unless(party_id in parties, 'Unknown party {0}'.format(party_id.encode('utf-8')))
        # Assert the voting district code refers to a valid district.
        fail_unless(code in districts, 'Unknown voting district code: {0}'.format(code))

        dob_match = RE_DOB.match(ws.cell_value(row, 3).strip())
        fail_unless(dob_match is not None, 'Invalid dob: {0}'.format(ws.cell_value(row, 3)))
        dob = date(int(dob_match.group(3)) + 1900, int(dob_match.group(2)), int(dob_match.group(1)))

        fail_unless(dob.strftime('%d%m%y') == ws.cell_value(row, 3).strip(), 'Failed dob parsing.')

        # Create the Candidate object
        candidate = Candidate(number, firstname, lastname, dob, municipality, occupation, parties[party_id], districts[code])
        session.add(candidate)
        print " - ", candidate.fullname().encode('utf-8'), candidate.number
        candidate_count += 1

    session.flush()
    # Assert that we created the right number of candidates, which is
    # ws.nrows - 1 + 1 (all rows, minus header row, plus the empty candidate)
    fail_unless(ws.nrows == session.query(Candidate).count(), 'Failed to create correct number of candidates.')

    print
    print "Created", len(parties), "parties."
    print "Created", coalition_count, "coalitions."
    print "Created", candidate_count, "candidates."

    transaction.commit()


def populate_demo():
    """Populates a database with demo content."""

    config = get_config()
    engine = engine_from_config(config, 'sqlalchemy.')
    initialize_sql(engine)
    engine.echo = False

    session = DBSession()

    districts = session.query(District).order_by(District.code)

    provider = urlparse(config['nuorisovaalit.openid_provider'])
    provider_tmpl = u'{0}://{{0}}.{1}'.format(provider.scheme, provider.netloc)
    # Create voters
    for district in districts:
        username = u'test.user{0:02}'.format(district.code)
        school = School(u'Koulu vaalipiirissä {0}'.format(district.name), district)
        session.add(school)
        session.flush()
        session.add(Voter(
            provider_tmpl.format(username),
            u'Testi', u'Käyttäjä #{0:02}'.format(district.code),
            date(1990, 4, 5),
            u'040 123 4567',
            u'xxxx@xxxx.xx',
            u'Nowhere street 5, 00000 Helsinki',
            school))

    transaction.commit()
    print("Created demo structure.")
