# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import date
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.tests import init_testing_db
from nuorisovaalitadmin.tests import populate_testing_db

import csv
import os
import random
import shutil
import tempfile
import transaction
import unittest2 as unittest
import xlrd


class TestPopulateVotingResults(unittest.TestCase):
    """Test for the script that populates the votes based on the school
    submissions.
    """

    def setUp(self):
        init_testing_db()
        transaction.begin()

    def tearDown(self):
        transaction.abort()
        DBSession.remove()

    def _make_submission(self, data, school):
        from nuorisovaalitadmin.models import CSVSubmission

        session = DBSession()
        session.add(CSVSubmission(data, school, CSVSubmission.RESULT))
        session.flush()

    def test_no_submissions(self):
        """Test that populating votes with no submissions produces no votes."""
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import populate_voting_results

        session = DBSession()
        # Assert there are no votes or submissions before.
        self.assertEquals(0, session.query(Vote).count())
        self.assertEquals(0, session.query(CSVSubmission).count())

        # Assert the populating with no submissions produces no votes.
        populate_voting_results()
        self.assertEquals(0, session.query(Vote).count())

    def test_invalid_candidates(self):
        """Test that invalid submissions do not produce votes and fail the run.
        """
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import populate_voting_results

        session = DBSession()
        populate_testing_db()
        # Assert there are no votes or submissions before.
        self.assertEquals(0, session.query(Vote).count())
        self.assertEquals(0, session.query(CSVSubmission).count())
        # Generate a submission which contains an invalid candidate
        schools = session.query(School).all()
        self.failUnless(len(schools) >= 2)
        self._make_submission([
            {'number': 1, 'name': u'Matti Meikäläinen', 'votes': 100},
            {'number': 2, 'name': u'xxxx xxxx', 'votes': 200},
            {'number': 3, 'name': u'xxxx xxxx', 'votes': 16},
        ], schools[0])
        self._make_submission([
            {'number': 1, 'name': u'Matti Meikäläinen', 'votes': 100},
            {'number': 2, 'name': u'xxxx xxxx', 'votes': 200},
            {'number': 999, 'name': u'xxxx xxxx', 'votes': 16},
        ], schools[1])
        self.assertEquals(2, session.query(CSVSubmission).count())

        populate_voting_results()
        self.assertEquals(0, session.query(Vote).count())

    def test_valid_submissions(self):
        from nuorisovaalit.models import Candidate
        from nuorisovaalit.models import School
        from nuorisovaalit.models import Vote
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import populate_voting_results

        session = DBSession()
        populate_testing_db()
        # Assert there are no votes or submissions before.
        self.assertEquals(0, session.query(Vote).count())
        self.assertEquals(0, session.query(CSVSubmission).count())
        # Generate submissions containing valid data
        schools = session.query(School).order_by(School.id).all()
        self.failUnless(len(schools) >= 2)
        self._make_submission([
            {'number': 1, 'name': u'Matti Meikäläinen', 'votes': 10},
            {'number': 2, 'name': u'xxxx xxxx', 'votes': 20},
            {'number': 3, 'name': u'xxxx xxxx', 'votes': 30},
        ], schools[0])
        self._make_submission([
            {'number': 1, 'name': u'Matti Meikäläinen', 'votes': 100},
            {'number': 2, 'name': u'xxxx xxxx', 'votes': 200},
            {'number': 3, 'name': u'xxxx xxxx', 'votes': 300},
        ], schools[1])
        self.assertEquals(2, session.query(CSVSubmission).count())

        populate_voting_results()

        # Get a new session because populate_voting_results() commits the
        # transaction and invalidates the session.
        session = DBSession()
        schools = session.query(School).order_by(School.id).all()
        # Assert the correct number of vote records
        self.assertEquals(6, session.query(Vote).count())
        # Assert the votes were recorded correctly.
        query = session.query(Vote, Candidate, School)\
                    .filter(Vote.candidate_id == Candidate.id)\
                    .filter(Vote.school_id == School.id)
        votes = [(candidate.number, school.id, vote.count, vote.kind)
                 for vote, candidate, school
                 in query.all()]
        self.assertEquals(votes, [
            (1, schools[0].id, 10, Vote.PAPER),
            (2, schools[0].id, 20, Vote.PAPER),
            (3, schools[0].id, 30, Vote.PAPER),
            (1, schools[1].id, 100, Vote.PAPER),
            (2, schools[1].id, 200, Vote.PAPER),
            (3, schools[1].id, 300, Vote.PAPER),
        ])


class TestCreateVoters(unittest.TestCase):
    """Tests for the voter creation script."""

    def setUp(self):
        self.basedir = tempfile.mkdtemp()
        init_testing_db()
        # Make "random" values consistent
        random.seed(1234567890)
        transaction.begin()

    def tearDown(self):
        shutil.rmtree(self.basedir)
        DBSession.remove()

    def _create_school(self, name):
        """Creates a district and school object in the database."""
        from nuorisovaalit.models import District
        from nuorisovaalit.models import School

        session = DBSession()

        if session.query(District).count() == 0:
            district = District(u'District 9', 1, 10)
            session.add(district)
            session.flush()
        else:
            district = session.query(District).first()

        school = School(name, district)
        session.add(school)
        session.flush()

        return school

    def test_genpasswd(self):
        from nuorisovaalitadmin.scripts.populate import CreateVoters

        self.assertEquals(5, len(CreateVoters().genpasswd(5)))

    def test_run__no_existing_voters(self):
        """Tests a successful operation which creates the Voter instances and
        the associated filesystem artifacts. There are now existing Voters in
        the database.
        """
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()
        cs = CreateVoters(basedir=self.basedir)

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        data1 = (
            # A record with all fields filled, should end up in the SMS and email lists.
            {'firstname': u'Mätti',
             'dob': u'15.11.1990',
             'lastname': u'Meikäläinen',
             'address': u'Väinötie 5, 00200 Laukaa',
             'gsm': u'040 123 456',
             'email': u'matti@meikalainen.fi'},
            # A record with only email and address, should end up in the email list.
            {'firstname': u'Mäijä',
             'dob': u'1.3.1982',
             'lastname': u'Meikäläinen',
             'address': u'Jössäin kaukana',
             'gsm': u'',
             'email': u'maija@meikalainen.com'})
        data2 = (
            # A record with all fields filled, should end up in the SMS and email lists.
            {'firstname': u'Mätiäs',
             'dob': u'16.11.1990',
             'lastname': u'Müükäläinen',
             'address': u'Väinötie 5, 00200 Laukaa',
             'gsm': u'040654321',
             'email': u'matias@muukalainen.fi'},
            # A record with only an address, should end up in the itella list.
            {'firstname': u'Märtti',
             'dob': u'2.3.1981',
             'lastname': u'Teikäläinen',
             'address': u'Väinämöisenkatu 3 A, 00500 Helsinki',
             'gsm': u'',
             'email': u''})

        # Initialize the database with submissions.
        session.add(CSVSubmission(data1, self._create_school(u'S1'), CSVSubmission.VOTER))
        session.add(CSVSubmission(data2, self._create_school(u'S2'), CSVSubmission.VOTER))
        session.flush()
        self.assertEquals(2, session.query(CSVSubmission).filter_by(kind=CSVSubmission.VOTER).count())

        cs.SMS_TMPL = u'SMS üsername: {username}, pässwörd: {password}'
        cs.run()

        # Make sure all the files got created.
        self.assertEquals(sorted(os.listdir(self.basedir)), [
            os.path.basename(cs.filename('voters-email-{id}.txt')),
            os.path.basename(cs.filename('voters-itella-{id}.xls')),
            os.path.basename(cs.filename('voters-labyrintti-{id}.csv')),
            os.path.basename(cs.filename('voters-openid_accounts-{id}.txt'))])

        # Check the OpenID list. All voters must be present here.
        openid_list = open(cs.filename('voters-openid_accounts-{id}.txt')).read().splitlines()
        self.assertEquals(openid_list, [
            'matti.meikalainen|7xs464kc',
            'maija.meikalainen|dsbp8mm5',
            'matias.muukalainen|cn5xr7f4',
            'martti.teikalainen|84ah53m5'])

        # Check the emailing list. All voters with an email address but be present.
        email_list = open(cs.filename('voters-email-{id}.txt')).read().splitlines()
        self.assertEquals(email_list, [
            'matti.meikalainen|7xs464kc|matti@meikalainen.fi',
            'maija.meikalainen|dsbp8mm5|maija@meikalainen.com',
            'matias.muukalainen|cn5xr7f4|matias@muukalainen.fi'])

        # Check the labyrintti list. All voters with a GSM number must be present.
        sms_list = list(csv.reader(open(cs.filename('voters-labyrintti-{id}.csv')), delimiter=',', quotechar='"'))
        self.assertEquals(sms_list, [
            ['040123456', 'SMS üsername: matti.meikalainen, pässwörd: 7xs464kc'],
            ['040654321', 'SMS üsername: matias.muukalainen, pässwörd: cn5xr7f4']])

        # Check the Itella list. All voters without a GSM or email must be present.
        wb = xlrd.open_workbook(filename=cs.filename('voters-itella-{id}.xls'))
        ws = wb.sheet_by_index(0)
        self.assertEquals(2, ws.nrows)
        self.assertEquals(7, ws.ncols)
        self.assertEquals(ws.cell_value(1, 0), u'martti.teikalainen')
        self.assertEquals(ws.cell_value(1, 1), u'84ah53m5')
        self.assertEquals(ws.cell_value(1, 2), u'Märtti Teikäläinen')
        self.assertEquals(ws.cell_value(1, 3), u'Väinämöisenkatu 3 A')
        self.assertEquals(ws.cell_value(1, 4), u'00500')
        self.assertEquals(ws.cell_value(1, 5), u'Helsinki')
        self.assertEquals(ws.cell_value(1, 6), u'')

        # Check created Voter objects. All voters must be present.
        voters = session.query(Voter).order_by(Voter.openid).all()
        self.assertEquals(4, len(voters))

        self.assertEquals(voters[0].openid, u'http://maija.meikalainen.did.fi')
        self.assertEquals(voters[0].firstname, u'Mäijä')
        self.assertEquals(voters[0].lastname, u'Meikäläinen')
        self.assertEquals(voters[0].dob, date(1982, 3, 1))
        self.assertEquals(voters[0].gsm, u'')
        self.assertEquals(voters[0].email, u'maija@meikalainen.com')
        self.assertEquals(voters[0].address, u'Jössäin kaukana')
        self.assertEquals(voters[0].school.name, u'S1')

        self.assertEquals(voters[1].openid, u'http://martti.teikalainen.did.fi')
        self.assertEquals(voters[1].firstname, u'Märtti')
        self.assertEquals(voters[1].lastname, u'Teikäläinen')
        self.assertEquals(voters[1].dob, date(1981, 3, 2))
        self.assertEquals(voters[1].gsm, u'')
        self.assertEquals(voters[1].email, u'')
        self.assertEquals(voters[1].address, u'Väinämöisenkatu 3 A, 00500 Helsinki')
        self.assertEquals(voters[1].school.name, u'S2')

        self.assertEquals(voters[2].openid, u'http://matias.muukalainen.did.fi')
        self.assertEquals(voters[2].firstname, u'Mätiäs')
        self.assertEquals(voters[2].lastname, u'Müükäläinen')
        self.assertEquals(voters[2].dob, date(1990, 11, 16))
        self.assertEquals(voters[2].gsm, u'040654321')
        self.assertEquals(voters[2].email, u'matias@muukalainen.fi')
        self.assertEquals(voters[2].address, u'Väinötie 5, 00200 Laukaa')
        self.assertEquals(voters[2].school.name, u'S2')

        self.assertEquals(voters[3].openid, u'http://matti.meikalainen.did.fi')
        self.assertEquals(voters[3].firstname, u'Mätti')
        self.assertEquals(voters[3].lastname, u'Meikäläinen')
        self.assertEquals(voters[3].dob, date(1990, 11, 15))
        self.assertEquals(voters[3].gsm, u'040 123 456')
        self.assertEquals(voters[3].email, u'matti@meikalainen.fi')
        self.assertEquals(voters[3].address, u'Väinötie 5, 00200 Laukaa')
        self.assertEquals(voters[3].school.name, u'S1')

    def test_run__sms_message_too_long(self):
        """Tests a scenario where we end up with an SMS message that exceeds
        the limit of 160 characters.
        """
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()
        cs = CreateVoters(basedir=self.basedir)

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        data1 = (
            # A record with all fields filled, should end up in the SMS and email lists.
            {'firstname': u'Mätti',
             'dob': u'15.11.1990',
             'lastname': u'Meikäläinen',
             'address': u'Väinötie 5, 00200 Laukaa',
             'gsm': u'040 123 456',
             'email': u'matti@meikalainen.fi'},
             )

        # Initialize the database with submissions.
        session.add(CSVSubmission(data1, self._create_school(u'S1'), CSVSubmission.VOTER))
        session.flush()
        self.assertEquals(1, session.query(CSVSubmission).filter_by(kind=CSVSubmission.VOTER).count())

        cs.SMS_TMPL = u'X' * 160 + u'SMS üsername: {username}, pässwörd: {password}'
        self.assertRaises(ValueError, lambda: cs.run())

    def test_run__partial_address(self):
        """Tests a scenario where we fail to parse a snail mail address and
        have to use a partial address"""
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.models import CSVSubmission
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()
        cs = CreateVoters(basedir=self.basedir)

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        data1 = (
            # A record with only an address, should end up in the itella list.
            {'firstname': u'Märtti',
             'dob': u'2.3.1981',
             'lastname': u'Teikäläinen',
             'address': u'Honkatie 5',
             'gsm': u'',
             'email': u''},
             )

        # Initialize the database with submissions.
        session.add(CSVSubmission(data1, self._create_school(u'S1'), CSVSubmission.VOTER))
        session.flush()
        self.assertEquals(1, session.query(CSVSubmission).filter_by(kind=CSVSubmission.VOTER).count())

        cs.run()

        # Check the Itella list. All voters without a GSM or email must be present.
        wb = xlrd.open_workbook(filename=cs.filename('voters-itella-{id}.xls'))
        ws = wb.sheet_by_index(0)

        self.assertEquals(2, ws.nrows)
        self.assertEquals(7, ws.ncols)
        self.assertEquals(ws.cell_value(1, 0), u'martti.teikalainen')
        self.assertEquals(ws.cell_value(1, 1), u'7xs464kc')
        self.assertEquals(ws.cell_value(1, 2), u'Märtti Teikäläinen')
        self.assertEquals(ws.cell_value(1, 3), u'Honkatie 5')
        self.assertEquals(ws.cell_value(1, 4), u'')
        self.assertEquals(ws.cell_value(1, 5), u'')
        self.assertEquals(ws.cell_value(1, 6), u'S1')

    def test_genusername__no_duplicate(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()

        cs = CreateVoters()

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        self.assertEquals(u'xxxx.xxxx', cs.genusername(u'xxxx', u'xxxx'))
        self.assertEquals(u'xxxx.xxxx', cs.genusername(u'xxxx xxxx', u'xxxx'))
        self.assertEquals(u'fuu.bar.boo', cs.genusername(u'Füü', u'Bär bÖÖ'))

    def test_genusername__duplicates(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()

        cs = CreateVoters()

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        # First username without duplicate.
        self.assertEquals(u'foo.boo', cs.genusername(u'Föö Büü', u'Böö'))
        # First duplicate uses the middle initial.
        self.assertEquals(u'foo.b.boo', cs.genusername(u'Föö Büü', u'Böö'))
        # Second duplicate uses the full middle name.
        self.assertEquals(u'foo.buu.boo', cs.genusername(u'Föö Büü', u'Böö'))
        # Subsequent duplicates use an increasing suffix without the middle name.
        self.assertEquals(u'foo.boo2', cs.genusername(u'Föö Büü', u'Böö'))
        self.assertEquals(u'foo.boo3', cs.genusername(u'Föö Büü', u'Böö'))

    def test_genusername__duplicates_wo_middlename_fallback(self):
        from nuorisovaalit.models import Voter
        from nuorisovaalitadmin.scripts.populate import CreateVoters
        session = DBSession()

        cs = CreateVoters()

        # Make sure we don't have any existing voters.
        self.assertEquals(0, session.query(Voter).count())
        self.assertEquals(0, len(cs.usernames))

        # First username without duplicate.
        self.assertEquals(u'foo.boo', cs.genusername(u'Föö', u'Böö'))
        # Without middle name we start using suffixes right away.
        self.assertEquals(u'foo.boo2', cs.genusername(u'Föö', u'Böö'))
        self.assertEquals(u'foo.boo3', cs.genusername(u'Föö', u'Böö'))
