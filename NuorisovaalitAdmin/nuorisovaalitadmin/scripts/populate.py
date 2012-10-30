# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from StringIO import StringIO
from datetime import date
from datetime import datetime
from isounidecode import unidecode
from itertools import count
from nuorisovaalit.models import District
from nuorisovaalit.models import School
from nuorisovaalit.models import Vote
from nuorisovaalit.models import Voter
from nuorisovaalitadmin.models import CSVSubmission
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.models import Group
from nuorisovaalitadmin.models import User
from nuorisovaalitadmin.models import initialize_sql
from nuorisovaalitadmin.scripts import get_config
from repoze.filesafe import FileSafeDataManager
from sqlalchemy import engine_from_config
from urlparse import urlparse

import csv
import os
import random
import re
import sys
import transaction
import xlrd
import xlwt

RE_ADDRESS = re.compile(ur'(.*)(\d{5})(.*)')


class CreateVoters(object):
    """Creates the voter accounts based on the submitted data.

    This is a two-part process and this function manages the first part, which
    creates the accounts in the nuorisovaalit database. The second part will
    create the associated OpenID accounts in the webidentity database.

    The steps taken are:

        1. Generate a unique username for all voters.

           The usernames are primarily generated as "firstname.lastname" and
           in the case of duplicates the middle name is used as the
           discriminator. Any collitions after using the middle name will be
           resolved with an monotonically increasing integer suffix starting
           from 2.

        2. Generate a password for all voters.

        3. Create the :py:class:`nuorisovaalit.models.Voter` instances.

        4. Write the (username, password) combinations to a text file which
           will be used to generate the OpenID accounts in the second part of
           the process.

        5. Write a list of (gsm, message) combinations to a CSV file file
           which will be sent to Labyrintti.

        6. Write a list of (username, password, email) combinations to a text
           file which will be used to send the email notifications.

        7. Write an Excel spreadsheet of (username, password, name, address,
           zipcode, city, [school]) combinations to a text file which will be
           sent to Itella.

    Because the address (street, zipcode, city) data is not perfect we use an
    additional column to record the school name in case we fail to parse the
    address information. The idea is that the school names can be manually
    translated to municipalities which in turn may help to resolve the partial
    address information.
    """

    def __init__(self, basedir=None):
        self.usernames = set()
        self.SMS_TMPL = u'Äänestä varjovaaleissa sähköisesti osoitteessa www.nuorisovaalit2011.fi! Käyttäjätunnus: {username}, salasana: {password}'
        self.runid = datetime.now().strftime('%Y-%m-%d-%H-%M')

        if basedir is None:
            # Generate the files in the current working directory by default.
            self.basedir = os.getcwd()
        else:
            self.basedir = os.path.join(os.getcwd(), basedir)

    def filename(self, template):
        """Returns a full path to a filename used for output."""
        return os.path.join(self.basedir, template.format(id=self.runid))

    def run(self, startdate=None):
        session = DBSession()

        if startdate is None:
            startdate = datetime(1900, 1, 1)

        # Join the repoze.filesafe manager in the transaction so that files will
        # be written only when a transaction commits successfully.
        filesafe = FileSafeDataManager()
        transaction.get().join(filesafe)

        # Query the currently existing usernames to avoid UNIQUE violations.
        # The usernames are stored as OpenID identifiers so we need to extract
        # the usernames from the URLs.
        self.usernames.update([
            urlparse(openid).netloc.rsplit('.', 2)[0]
            for result in session.query(Voter.openid).all()
            for openid in result])

        # Query the voter submission and associated schools.
        submissions = session.query(School, CSVSubmission)\
              .join(CSVSubmission)\
              .filter(CSVSubmission.kind == CSVSubmission.VOTER)\
              .filter(CSVSubmission.timestamp > startdate)\
              .order_by(School.name)

        fh_openid = filesafe.createFile(self.filename('voters-openid_accounts-{id}.txt'), 'w')
        fh_email = filesafe.createFile(self.filename('voters-email-{id}.txt'), 'w')
        fh_labyrintti = filesafe.createFile(self.filename('voters-labyrintti-{id}.csv'), 'w')
        fh_itella = filesafe.createFile(self.filename('voters-itella-{id}.xls'), 'w')

        # Excel worksheet for Itella
        wb_itella = xlwt.Workbook(encoding='utf-8')
        ws_itella = wb_itella.add_sheet('xxxx')
        text_formatting = xlwt.easyxf(num_format_str='@')
        for col, header in enumerate([u'Tunnus', u'Salasana', u'Nimi', u'Osoite', u'Postinumero', u'Postitoimipaikka', u'Todennäköinen kunta']):
            ws_itella.write(0, col, header, text_formatting)
        rows_itella = count(1)

        school_count = voter_count = address_parse_errors = 0

        self.header('Starting to process submissions')

        for school, submission in submissions.all():
            self.header('Processing school: {0}'.format(school.name.encode('utf-8')))
            for voter in submission.csv:
                username = self.genusername(voter['firstname'], voter['lastname'])
                password = self.genpasswd()

                # Create the voter instance.
                openid = u'http://{0}.did.fi'.format(username)
                dob = date(*reversed([int(v.strip()) for v in voter['dob'].split('.', 2)]))
                session.add(Voter(openid, voter['firstname'], voter['lastname'], dob, voter['gsm'], voter['email'], voter['address'], school))

                # Write the OpenID account information.
                fh_openid.write(u'{0}|{1}\n'.format(username, password).encode('utf-8'))

                has_gsm, has_email = bool(voter['gsm'].strip()), bool(voter['email'].strip())
                if has_gsm or has_email:
                    if has_gsm:
                        # Write the Labyrintti information only if a GSM number is available.
                        message = self.SMS_TMPL.format(username=username, password=password).encode('utf-8')
                        if len(message) > 160:
                            transaction.abort()
                            raise ValueError('SMS message too long: {0}'.format(message))

                        fh_labyrintti.write('"{0}","{1}"\n'.format(
                            u''.join(voter['gsm'].split()).encode('utf-8'),
                            message))

                    if has_email:
                        # Write the email information for everybody with an address.
                        fh_email.write(u'{0}|{1}|{2}\n'.format(username, password, voter['email']).encode('utf-8'))

                else:
                    # Write the Itella information for those that only have an
                    # address. We rely on the validation to ensure that it is
                    # available.
                    match = RE_ADDRESS.match(voter['address'])
                    if match is not None:
                        street = match.group(1).strip().strip(u',').strip()
                        zipcode = match.group(2).strip().strip(u',').strip()
                        city = match.group(3).strip().strip(u',').strip()

                        row = rows_itella.next()
                        for col, item in enumerate([username, password, u'{0} {1}'.format(voter['firstname'].split()[0], voter['lastname']), street, zipcode, city]):
                            ws_itella.write(row, col, item, text_formatting)
                    else:
                        print 'Failed to parse address for {0}: {1}.'.format(username, voter['address'].encode('utf-8'))
                        address_parse_errors += 1
                        row = rows_itella.next()
                        for col, item in enumerate([username, password, u'{0} {1}'.format(voter['firstname'].split()[0], voter['lastname']), voter['address'], u'', u'', school.name]):
                            ws_itella.write(row, col, item, text_formatting)

                print username
                voter_count += 1
            school_count += 1

        wb_itella.save(fh_itella)
        fh_openid.close()
        fh_email.close()
        fh_labyrintti.close()
        fh_itella.close()

        session.flush()
        transaction.commit()

        self.header('Finished processing')
        print 'Processed', school_count, 'schools and', voter_count, 'voters.'
        print 'Address parsing failed for', address_parse_errors, 'users.'

    def header(self, message):
        print '-' * len(message)
        print message
        print '-' * len(message)

    def genpasswd(self, length=8, chars='abcdefhkmnprstuvwxyz23456789'):
        """Generate a random password of given length."""
        return u''.join(random.choice(chars) for i in xrange(length))

    def genusername(self, firstnames, lastname):
        """Generates a username based on the given names."""
        # Generate a list of normalized first names.
        names = [unicode(unidecode(n)) for n in firstnames.strip().lower().split()]
        # In case the lastname consists of multiple parts we join them with
        # a period.
        lastname = unicode(unidecode(u'.'.join(lastname.strip().lower().split())))

        # Try the "firstname.lastname" option first.
        candidate = u'{0}.{1}'.format(names[0], lastname)
        if candidate not in self.usernames:
            self.usernames.add(candidate)
            return candidate

        # If a second name exists, try using the first letter.
        if len(names) > 1 and len(names[1]) > 0:
            candidate = u'{0}.{1}.{2}'.format(names[0], names[1][0], lastname)
            if candidate not in self.usernames:
                self.usernames.add(candidate)
                print >> sys.stderr, "-!- Using middle initial for {0}.".format(candidate)
                return candidate
            else:
                # Try with the whole second name.
                candidate = u'{0}.{1}.{2}'.format(names[0], names[1], lastname)
                if candidate not in self.usernames:
                    self.usernames.add(candidate)
                    print >> sys.stderr, "-!- Using middle name for {0}.".format(candidate)
                    return candidate

        # We've exhausted our options of readable usernames, start using a suffix.
        suffix = count(2)
        candidate = base = u'{0}.{1}'.format(names[0], lastname)
        while candidate in self.usernames:
            candidate = u'{0}{1}'.format(base, suffix.next())

        self.usernames.add(candidate)
        print >> sys.stderr, "-!- Using suffix for {0}.".format(candidate)
        return candidate


def populate_voters():
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    engine.echo = False
    startdate = None
    if len(sys.argv) >= 2:
        try:
            startdate = datetime.strptime(sys.argv[2].strip(), '%Y-%m-%dT%H:%M')
            print "Reading submissions received after", startdate.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            print "Invalid timestamp:", sys.argv[2], ". Excepted format is %Y-%m-%dT%H:%M"
            sys.exit(1)

    CreateVoters().run(startdate)


def verify_voters():
    """Verifies the generated Voter instances against the OpenID account
    list.
    """
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    session = DBSession()

    if len(sys.argv) < 6:
        print "Usage: {0} <config> <openidlist> <itellalist> <labyrinttilist> <emaillist>".format(sys.argv[0])
        sys.exit(1)

    openids = set([oid for result in session.query(Voter.openid).all() for oid in result])
    failed = 0

    passwords = dict(line.strip().split('|', 1) for line in open(sys.argv[2]).read().splitlines())

    print "Checking Voter instances for OpenID consistency.."
    for username, password in passwords.iteritems():
        openid = 'http://{0}.did.fi'.format(username)
        if openid not in openids:
            print "Unknown OpenID account:", openid
            failed += 1

    print "Checked", len(passwords), "OpenID accounts against", len(openids), "voters."
    if failed == 0:
        print "Voter instances OK"
    else:
        print "Failures", failed
        print "Data inconsistency in Voter instances, please investigate!"

    print
    print "Checking Itella listing for password consistency.."
    failed = 0
    wb = xlrd.open_workbook(filename=os.path.join(os.getcwd(), sys.argv[3]))
    ws = wb.sheet_by_index(0)
    for row in xrange(1, ws.nrows):
        username = ws.cell_value(row, 0)
        password = ws.cell_value(row, 1)
        if username not in passwords:
            print "Unknown username:", username
            failed += 1
        elif passwords[username] != password:
            print "Password mismatch for username:", username
            failed += 1

    print "Checked", ws.nrows, "Excel rows."
    if failed == 0:
        print "Itella records OK"
    else:
        print "Failures", failed
        print "Data inconsistency in Itella records, please investigate!"

    print
    print "Checking Labyrintti listing for password consistency.."
    failed = 0
    RE_CREDS = re.compile(u'.*tunnus: ([a-z0-9.-]+), salasana: ([a-z0-9]+)')
    for row in csv.reader(open(sys.argv[4]), delimiter=',', quotechar='"'):
        m = RE_CREDS.match(row[1])
        if m is not None:
            username = m.group(1)
            password = m.group(2)
            if username not in passwords:
                print "Unknown username:", username
                failed += 1
            elif passwords[username] != password:
                print "Password mismatch for username:", username
                failed += 1
        else:
            failed += 1
            print "Invalid message:", row[1]

    print "Checked", len(open(sys.argv[4]).readlines()), "CSV rows."
    if failed == 0:
        print "Labyrintti records OK"
    else:
        print "Failures", failed
        print "Data inconsistency in Labyrintti records, please investigate!"

    print
    print "Checking email listing for password consistency.."
    failed = 0
    lines = open(sys.argv[5]).read().splitlines()
    for line in lines:
        username, password, email = line.split('|', 2)
        if username not in passwords:
            print "Unknown username:", username
            failed += 1
        elif passwords[username] != password:
            print "Password mismatch for username:", username
            failed += 1

    print "Checked", len(lines), "email records."
    if failed == 0:
        print "Email records OK"
    else:
        print "Failures", failed
        print "Data inconsistency in email records, please investigate!"


def populate_school_accounts():
    """Creates the school representative accounts.

    This scripts assumes that the database is already populated with the
    voting district information.

    Based on the information received we create the following type of objects:

        * nuorisovaalit.models.School
        * nuorisovaalitadmin.models.User

    .. warning:: Running this function multiple times on the same data will
                 result in redundant accounts to be created. You should only
                 run it once per dataset.
    """
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    session = DBSession()
    print('Generating school representative accounts.')

    # Generate user groups if necessary
    groups = [
        ('admin', u'Administrators'),
        ('xxxx', u'xxxx'),
        ('school', u'Schools'),
        ('school_limited', u'Schools (results only)')]
    for gname, gtitle in groups:
        if session.query(Group).filter(Group.name == gname).count() == 0:
            print(' > Created group: {0}'.format(gname))
            session.add(Group(gname, gtitle))
    session.flush()

    # Create a dummy school to satisfy constraints.
    district = session.query(District).first()
    if session.query(School).filter_by(name=u'Dummy school').count() == 0:
        dummy_school = School(u'Dummy school', district)
        session.add(dummy_school)
        session.flush()

    # Create an admin account if necessary
    if session.query(User).filter_by(username='admin').count() == 0:
        print(' > Creating an admin user.')

        admin_grp = session.query(Group).filter_by(name='admin').one()
        admin = User('admin', 'xxxx', u'Administrator', u'xxxx@xxxx.xx', False, dummy_school, admin_grp)
        session.add(admin)

    # Create the xxxx account if necessary
    if session.query(User).filter_by(username='allianssi').count() == 0:
        print(' > Creating the xxxx user.')
        allianssi_grp = session.query(Group).filter_by(name='xxxx').one()
        dummy_school = session.query(School).filter_by(name=u'Dummy school').first()

        allianssi = User('xxxx', 'yyyy', u'xxxx', u'xxxx.xxxx@xxxx.xx', False, dummy_school, allianssi_grp)
        session.add(allianssi)

    school_grp = session.query(Group).filter_by(name='school').one()
    school_limited_grp = session.query(Group).filter_by(name='school_limited').one()

    # Create a test account that has normal school user access.
    if session.query(User).filter_by(username='schooltest').count() == 0:
        print(' > Creating a dummy school user.')
        dummy_school = session.query(School).filter_by(name=u'Dummy school').first()
        schooltest = User('schooltest', 'xxxx', u'School test account', u'xxxx.xxxx@xxxx.xx', False, dummy_school, school_grp)
        session.add(schooltest)

    def genpasswd(length=8, chars='abcdefhkmnprstuvwxyz23456789'):
        return u''.join(random.choice(chars) for i in xrange(length))

    users = set([username
                 for result in session.query(User.username).all()
                 for username in result])

    def genusername(name):
        base = candidate = unicode(unidecode(u'.'.join(name.strip().lower().split())))

        suffix = count(2)
        while candidate in users:
            candidate = base + unicode(suffix.next())

        users.add(candidate)
        return candidate

    if len(sys.argv) > 2:
        filename = os.path.join(os.getcwd(), sys.argv[2].strip())
        reader = csv.reader(open(filename, 'rb'))
        # Skip the first row.
        reader.next()
    else:
        print('No CSV file was provided, omitting school account creation!')
        reader = tuple()

    # Generate the users
    for row in reader:
        school_name, fullname, email, district_name, participation = \
            [f.decode('utf-8').strip() for f in row[:5]]

        # Find the corresponding district
        distcode = int(district_name.strip().split()[0])
        district = session.query(District).filter_by(code=distcode).one()
        # Create the school object.
        school = School(school_name, district)
        session.add(school)
        session.flush()

        password = genpasswd()
        username = genusername(fullname)
        participates = participation.strip() == '1'

        # Choose the user group based on the participation to the electronic election.
        group = school_grp if participates else school_limited_grp

        session.add(User(username, password, fullname, email, participates, school, group))
        print(u'{0}|{1}|{2}|{3}'.format(username, password, email, school_name))

    session.flush()
    transaction.commit()


def populate_demo():
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    session = DBSession()
    engine.echo = False

    school1 = session.query(School).get(1)
    school2 = session.query(School).get(2)
    school3 = session.query(School).get(3)

    grp_admin = Group('admin', u'Administrators')
    grp_allianssi = Group('xxxx', u'xxxx')
    grp_school = Group('school', u'Schools')
    grp_school_limited = Group('school_limited', u'Schools (results only)')

    session.add(grp_admin)
    session.add(grp_allianssi)
    session.add(grp_school)
    session.add(grp_school_limited)

    admin = User('admin', 'testi', u'Admin user', 'xxxx@xxxx.xx', True, school1)
    allianssi = User('xxxx', 'testi', u'xxxx', 'xxxx@xxxx.xx', True, school1)

    school_user1 = User('school1', 'testi', u'School user', 'xxxx@xxxx.xx', True, school1)
    school_user2 = User('school2', 'testi', u'School user', 'xxxx@xxxx.xx', True, school2)
    school_user3 = User('school3', 'testi', u'School user', 'xxxx@xxxx.xx', True, school3)

    admin.groups.append(grp_admin)
    allianssi.groups.append(grp_allianssi)
    school_user1.groups.append(grp_school)
    school_user2.groups.append(grp_school)
    school_user3.groups.append(grp_school_limited)

    session.add(admin)
    session.add(allianssi)
    session.add(school_user1)
    session.add(school_user2)
    session.add(school_user3)

    session.flush()
    transaction.commit()
    print("Generated demo accounts.")


def generate_third_labyrintti_batch():
    """Generates the third SMS batch for Labyrintti based on the data for the
    second batch.

    The third batch will be sent to the same recipients with a different
    message.
    """
    if len(sys.argv) < 2:
        print >> sys.stderr, 'Usage: {0} <second_batch.csv>'.format(sys.argv[0])
        sys.exit(1)

    output = StringIO()
    reader = csv.reader(open(os.path.join(os.getcwd(), sys.argv[1])))
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

    MSG_TMPL = 'Olethan jo käyttänyt äänesi ennakkoon sähköisesti osoitteessa www.nuorisovaalit2011.fi Käyttätunnus: {username}, salasana: {password}'
    RE_MSG = re.compile(r'^Äänestä varjovaaleissa sähköisesti osoitteessa www.nuorisovaalit2011.fi! Käyttäjätunnus: (?P<username>[a-z0-9-.]+), salasana: (?P<password>[a-z0-9]+)$')

    failures = 0
    for row in reader:
        match = RE_MSG.match(row[1])
        if match is not None:
            message = MSG_TMPL.format(**match.groupdict())
            if len(message) > 160:
                failures += 1
                print >> sys.stderr, 'Message too long: {0}'.format(message)
            else:
                writer.writerow([row[0], message])
        else:
            failures += 1
            print >> sys.stderr, 'Failed to parse row: {0}.'.format(row)

    if failures == 0:
        print output.getvalue()


def generate_labyrintti_batch_for_remaining_voters():
    """Generates a CSV batch file for Labyrintti based on data from the third
    batch by filtering out the voters who have already cast their vote.

    The list of voters who have already cast their vote is read from another
    file. See https://xxxx.xxxx.xx/xxxx/ for
    details on how to generate this file.
    """
    if len(sys.argv) < 3:
        print >> sys.stderr, 'Usage: {0} <third_batch.csv> <already_voted.txt>'.format(sys.argv[0])
        sys.exit(1)

    # Read in the already voted users.
    already_voted = set(open(os.path.join(os.getcwd(), sys.argv[2])).read().split())
    print >> sys.stderr, 'Loaded {0} already voted users.'.format(len(already_voted))

    # Note, there is an unfortunate typo in the third batch.
    RE_MSG = re.compile(r'Käyttätunnus: (?P<username>[a-z0-9-.]+), salasana: (?P<password>[a-z0-9]+)')
    MSG_TMPL = 'Olethan jo käyttänyt äänesi ennakkoon sähköisesti osoitteessa www.nuorisovaalit2011.fi Käyttäjätunnus: {username}, salasana: {password}'

    failures = skipped = 0
    output = StringIO()
    reader = csv.reader(open(os.path.join(os.getcwd(), sys.argv[1])))
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)

    for row in reader:
        match = RE_MSG.search(row[1].strip())
        if match is not None:
            username = match.groupdict()['username']
            if username in already_voted:
                print >> sys.stderr, 'Skipping {0}.'.format(username)
                skipped += 1
            else:
                message = MSG_TMPL.format(**match.groupdict())
                if len(message) > 160:
                    print >> sys.stderr, 'Message loo long: {0}'.format(message)
                    failures += 1
                else:
                    writer.writerow([row[0], message])
        else:
            print >> sys.stderr, 'Invalid input line: {0},{1}'.format(*row)
            failures += 1

    if failures == 0 and len(already_voted) != skipped:
        print output.getvalue()
    else:
        print >> sys.stderr, 'Failures: {0}, already voted: {1}, skipped: {2}'.format(failures, len(already_voted), skipped)


def generate_email_batch_for_remaining_voters():
    """Generates an email batch file based on data from the third batch by
    filtering out the voters who have already cast their vote.

    The list of voters who have already cast their vote is read from another
    file. See https://xxxx.xxxx.xx/xxxx/ for
    details on how to generate this file.
    """
    if len(sys.argv) < 3:
        print >> sys.stderr, 'Usage: {0} <third_batch.txt> <already_voted.txt>'.format(sys.argv[0])
        sys.exit(1)

    # Read in the already voted users.
    already_voted = set(open(os.path.join(os.getcwd(), sys.argv[2])).read().split())
    print >> sys.stderr, 'Loaded {0} already voted users.'.format(len(already_voted))

    skipped = 0
    output = StringIO()

    for line in open(os.path.join(os.getcwd(), sys.argv[1])).xreadlines():
        if len(line.strip()) == 0:
            continue

        username, _ = line.split('|', 1)
        if username in already_voted:
            print >> sys.stderr, 'Skipping {0}.'.format(username)
            skipped += 1
        else:
            output.write(line)

    if len(already_voted) != skipped:
        print output.getvalue()
    else:
        print >> sys.stderr, 'Already voted: {0}, skipped: {1}'.format(len(already_voted), skipped)


def populate_voting_results():
    """Reads the paper ballot submissions and populates the database with new
    :py:class:`nuorisovaalit.models.Vote` records based on them.
    """
    session = DBSession()

    records = failures = 0
    for submission in session.query(CSVSubmission).filter_by(kind=CSVSubmission.RESULT).all():
        print 'Processing', submission.school.name.encode('utf-8')
        # Find all the candidates that belong to the district associated with the school.
        candidates = dict((c.number, c) for c in submission.school.district.candidates)
        for record in submission.csv:
            number = int(record['number'])
            votes = int(record['votes'])
            if number in candidates:
                session.add(Vote(candidates[number], submission.school, Vote.PAPER, votes))
                records += 1
            else:
                failures += 1
                print >> sys.stderr, 'Unknown candidate number {0} in district {1}'.format(number, submission.school.district.name.encode('utf-8'))

    if failures == 0:
        session.flush()
        transaction.commit()
        print 'Populated {0} voting records.'.format(records)
    else:
        print >> sys.stderr, 'Aborting due to {0} failure(s).'.format(failures)
        transaction.abort()


def populate_voting_results_cli():
    """Command line interface for populate_voting_results()."""
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    populate_voting_results()
