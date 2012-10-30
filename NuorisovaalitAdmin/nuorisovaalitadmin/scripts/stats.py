# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from nuorisovaalit.models import School
from nuorisovaalitadmin.models import CSVSubmission
from nuorisovaalitadmin.models import DBSession
from nuorisovaalitadmin.models import initialize_sql
from nuorisovaalitadmin.scripts import get_config
from sqlalchemy import engine_from_config

from collections import defaultdict


def voter_submission_counts():
    """Lists the schools that have submitted voters and the number of voters
    for each school.
    """
    engine = engine_from_config(get_config(), 'sqlalchemy.')
    initialize_sql(engine)
    session = DBSession()

    query = session.query(School.name, CSVSubmission.csv)\
              .join(CSVSubmission)\
              .filter(CSVSubmission.kind == CSVSubmission.VOTER)\
              .order_by(School.name)

    stats = defaultdict(int)

    for school, submission in query.all():
        if school == u'Dummy school':
            continue

        print school, len(submission)
        stats['total'] += len(submission)

        for entry in submission:
            if entry['gsm'].strip():
                stats['gsm'] += 1
            elif entry['email'].strip():
                stats['email'] += 1
            else:
                stats['letter'] += 1

    print
    print 'Total voters: {total}'.format(**stats)
    print 'SMS: {gsm}, Email: {email}, Letter: {letter}'.format(**stats)
