# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from datetime import datetime
from openidalchemy.models import bind_engine as openidalchemy_bind_engine
from pyramid.security import Allow
from pyramid.security import Authenticated
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Table
from sqlalchemy import Unicode
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import dynamic_loader
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import time


DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class RootFactory(object):
    """Custom root factory.

    An instance of this class will function as the context for all views. The
    instance implements the access control policy which has the following
    rules:

     * Authenticated users are allowed to vote during the e-election period
       (Mon 21.3.2011 - Sun 27.3.2011).
    """

    def __init__(self, request):
        if getattr(request, 'matchdict', None) is not None:
            self.__dict__.update(request.matchdict)

        self.__acl__ = []
        schedule = School(request)

        if schedule.during_elections():
            self.__acl__.append((Allow, Authenticated, 'vote'))


class Candidate(Base):
    """Election candidate.

    A candidate is associated with a candidate number, a voting
    :py:class:`District` and a political :py:class:`Party`.
    """

    __tablename__ = 'candidates'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Candidate number for a special "empty" candidate. The empty candidate has a
    #: valid candidate number which can be voted but does not count in the
    #: results for any of the real candidates.
    EMPTY_CANDIDATE = 0

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Candidate number.
    number = Column(Integer, nullable=False)
    #: First name of the candidate.
    firstname = Column(Unicode(255), nullable=False)
    #: Family name of the candidate.
    lastname = Column(Unicode(255), nullable=False)
    #: Date of birth.
    dob = Column(Date, nullable=False)
    #: Municipality.
    municipality = Column(Unicode(50), nullable=False)
    #: Occupation.
    occupation = Column(Unicode(255), nullable=False)

    #: Foreign key reference to an associated voting :py:class:`District`.
    district_id = Column(Integer, ForeignKey('districts.id'), nullable=False)
    #: Foreign key reference to an associated political :py:class:`Party`.
    party_id = Column(Integer, ForeignKey('parties.id'), nullable=False)

    #: List of associated :py:class:`Vote` records.
    votes = relationship('Vote', backref='candidate', cascade='all')

    def __init__(self, number, firstname, lastname, dob, municipality, occupation, party_or_id=None, district_or_id=None):
        """
        :param number: The candidate number.
        :type number: int

        :param firstname: The first name of the candidate.
        :type firstname: unicode

        :param lastname: The family name of the candidate.
        :type lastname: unicode

        :param dob: The date of birth of the candidate.
        :type dob: :py:class:`datetime.date`

        :param municipality: The name of the municipality where the candidate lives.
        :type municipality: unicode

        :param occupation: The occupation of the candidate.
        :type occupation: unicode

        :param party_or_id: :py:class:`Party` which this :py:class:`Candidate` will be associated with.
        :type party_or_id: :py:class:`Party` instance or a primary key value

        :param district_or_id: :py:class:`District` which this :py:class:`Candidate` will be associated with.
        :type district_or_id: :py:class:`District` instance or a primary key value
        """
        self.number = number
        self.firstname = firstname.strip()
        self.lastname = lastname.strip()
        self.dob = dob
        self.municipality = municipality.strip()
        self.occupation = occupation.strip()

        if party_or_id is not None:
            self.party_id = getattr(party_or_id, 'id', party_or_id)
        if district_or_id is not None:
            self.district_id = getattr(district_or_id, 'id', district_or_id)

    def is_empty(self):
        """Returns ``True`` if this candidate represents the special "empty"
        candidate, ``False`` otherwise.

        :rtype: bool
        """
        return self.number == Candidate.EMPTY_CANDIDATE

    def vote_count(self):
        """Returns the number of votes this candidate received during the
        election.

        This includes votes voth from the electronic voting period and results
        from the paper ballot.

        :rtype: int
        """
        return sum(vote.count for vote in self.votes)

    def __repr__(self):
        """Detailed object representation."""
        return '<nuorisovaalit.models.Candidate[name={0},number={1}] at {2}>'.format(
            self.fullname().encode('utf-8'), self.number, id(self))

    def fullname(self):
        """Returns the full name of the candidate.

        :rtype: unicode
        """
        if self.lastname.strip() and self.firstname.strip():
            return u'{0}, {1}'.format(self.lastname, self.firstname)

        return self.lastname.strip() or self.firstname.strip()


#: Join table for Party/Coalition associations
CoalitionAssociation = Table(
    'coalition_associations', Base.metadata,
    Column('coalition_id', Integer, ForeignKey('coalitions.id')),
    Column('party_id', Integer, ForeignKey('parties.id')),
    mysql_engine='InnoDB',
    mysql_charset='utf8')


class Party(Base):
    """A political party which groups together :py:class:`Candidate` instances
    which is the primary grouping mechanism when displaying the candidates to
    the voter.

    .. note:: Also non-party groupings (valitsijalista) are modeled as Party
              objects as the technical semantics are the same.
    """

    __tablename__ = 'parties'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key
    id = Column(Integer, primary_key=True)
    #: Name of the party
    name = Column(Unicode(255), nullable=False)

    #: Dynamic relationship to coalitions this party is associated with.
    coalitions = dynamic_loader('Coalition', secondary=CoalitionAssociation)
    #: List of :py:class:`Candidate` objects associated with this party. The
    #: candidates are in ascending order sorted by their candidate numbers.
    candidates = relationship('Candidate', backref='party', order_by='Candidate.number', cascade='all')

    def __init__(self, name):
        """
        :param name: The name of the party
        :type name: unicode
        """
        self.name = name

    def coalition(self, district):
        """Returns the coalition that this party is associated within the
        given voting district or ``None`` if not associated.

        :param district: The district which is checked.
        :type district: :py:class:`District`

        :rtype: :py:class:`Coalition` or ``None``
        """
        return self.coalitions\
                     .join(District)\
                     .filter(District.id == district.id)\
                     .first()


class Coalition(Base):
    """A coalition of political parties.

    A coalition groups together political parties or other groups
    (valitsijalista) and is relevant during the results counting. For those
    parties and groups that are part of a coalition the results will be
    calculated as they were a single party or a group.

    In Finnish, a coalition is called "vaaliliitto" when it refers to
    political parties and "yhteislista" when it refers non-party groupings
    (valitsijalista).

    A coalition is specific to a particular voting district. Parties in
    different voting district may choose to form different coalitions.
    """

    __tablename__ = 'coalitions'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key
    id = Column(Integer, primary_key=True)
    #: Name of the coalition
    name = Column(Unicode(255), nullable=False)

    #: Foreign key reference to an associated voting :py:class:`District`.
    district_id = Column(Integer, ForeignKey('districts.id'), nullable=False)
    #: Reference to parties that are associated with this coalition.
    parties = relationship('Party', secondary=CoalitionAssociation)

    def __init__(self, name, district_or_id=None):
        """
        :param name: The name of the coalition
        :type name: unicode

        :param district_or_id: The :py:class:`District` instance this school will be associated with
        :type district_or_id: :py:class:`District` instance or primary key
        """
        self.name = name
        if district_or_id is not None:
            self.district_id = getattr(district_or_id, 'id', district_or_id)


class School(Base):
    """School is a grouping mechanism for voters which is associated with a
    particular :py:class:`District`."""

    __tablename__ = 'schools'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key
    id = Column(Integer, primary_key=True)
    #: Name of the school
    name = Column(Unicode(255), nullable=False)

    #: Foreign key reference to the associated :py:class:`District`
    district_id = Column(Integer, ForeignKey('districts.id'), nullable=False)

    #: List of associated :py:class:`Vote` records
    votes = relationship('Vote', backref='school', cascade='all')
    #: List of associated :py:class:`Voter` instances
    voters = relationship('Voter', backref='school', cascade='all')

    def __init__(self, name, district_or_id=None):
        """
        :param name: The name of the school
        :type name: unicode

        :param district_or_id: The :py:class:`District` instance this school will be associated with
        :type district_or_id: :py:class:`District` instance or primary key
        """
        self.name = name
        if district_or_id is not None:
            self.district_id = getattr(district_or_id, 'id', district_or_id)


class District(Base):
    """An election district which contains a set of schools and voters.

    A voter may only vote candidates associated with her designated voting
    district.
    """

    __tablename__ = 'districts'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Name of the voting district.
    name = Column(Unicode(255), unique=True, nullable=False)
    #: District code.
    code = Column(Integer, unique=True, nullable=False)
    #: Number of eligible candidates from this district.
    quota = Column(Integer, nullable=False, default=0)

    #: List of :py:class:`School` instances associated with this district.
    schools = relationship('School', backref='district', cascade='all')
    #: List of :py:class:`Candidate` instances associated with this district.
    candidates = relationship('Candidate', backref='district', cascade='all')

    def __init__(self, name, code, quota=0):
        """
        :param name: The name of the district.
        :type name: unicode

        :param code: The district code.
        :type code: int

        :param quota: The number of elibigle candidates from the district.
        :type quota: int
        """
        self.name = name
        self.code = code
        self.quota = quota


class Voter(Base):
    """Voter in an authenticated principal who is authorized to cast a vote.

    The voter authenticates using an external OpenID service and the
    identifier resulting from that process will be matched against a known
    value.

    An authenticated voter may cast a vote once for any candidate in the
    associated voting district.
    """

    __tablename__ = 'voters'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: OpenID identifier.
    openid = Column(Unicode(255), unique=True, nullable=False)
    #: First name(s).
    firstname = Column(Unicode(255), nullable=False)
    #: Last name.
    lastname = Column(Unicode(255), nullable=False)
    #: Date of birth.
    dob = Column(Date, nullable=False)
    #: Mobile phone number.
    gsm = Column(Unicode(50))
    #: Email address
    email = Column(Unicode(255))
    # XXX: Split the address into street, zip, city?
    #: Postal address.
    address = Column(Unicode(255))
    #: Indicator whether the voter wishes to continue using the OpenID account.
    accept_openid = Column(Boolean, nullable=True)

    #: Foreign key reference to the associated :py:class:`School` instance.
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)

    def __init__(self, openid, firstname, lastname, dob, gsm, email, address, school_or_id):
        """
        :param openid: An OpenID identifier
        :type openid: unicode

        :param firstname: First name(s)
        :type firstname: unicode

        :param lastname: Last name
        :type lastname: unicode

        :param dob: Date of birth
        :type dob: ``datetime.date``

        :param gsm: Mobile phone number
        :type gsm: unicode

        :param email: Email address
        :type email: unicode

        :param address: Postal address
        :type address: unicode

        :param school_or_id: School which this voter belongs to
        :type school_or_id: :py:class:`School` or primary key
        """
        self.openid = openid
        self.firstname = firstname
        self.lastname = lastname
        self.dob = dob
        self.gsm = gsm
        self.email = email
        self.address = address
        self.school_id = getattr(school_or_id, 'id', school_or_id)

    def fullname(self):
        """Returns the full name of the voter.

        :rtype: unicode
        """
        return u'{0} {1}'.format(self.firstname, self.lastname)

    def has_voted(self):
        """Returns ``True`` if the voter has already voted in the election,
        ``False`` otherwise.

        :rtype: bool
        """
        session = DBSession()
        return session.query(VotingLog).filter(
            VotingLog.voter_id == self.id).count() > 0

    def has_preference(self):
        """Returns ``True`` if the voter has selected his/her
        preference for accepting to keep using the OpenID account,
        otherwise ``False``.

        :rtype: bool
        """
        return self.accept_openid is not None


class Vote(Base):
    """Election vote.

    A record for a given number of votes for a :py:class:`Candidate`. A record
    is created either when

     * a :py:class:`Voter` casts a vote in the election.

     * a :py:class:`School` representative submits the results of the paper
       ballot.

    A :py:class:`Vote` record is not directly associated with the
    :py:class:`Voter` who cast a vote. For each :py:class:`Vote` of type
    :py:attr:`Vote.ELECTRONIC` there exists a :py:class:`VotingLog` record
    created within the same transaction.
    """

    __tablename__ = 'votes'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Type definition for a vote recorded during the online election.
    ELECTRONIC = u'electronic'
    #: Type definition for a vote recorded during the offline paper election.
    PAPER = u'paper'

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Number of votes.
    count = Column(Integer, default=0, nullable=False)
    #: The type of vote. Either :py:attr:`Vote.ELECTRONIC` or :py:attr:`Vote.PAPER`.
    kind = Column(Enum(ELECTRONIC, PAPER), index=True)

    #: Foreign key reference to an associated :py:class:`Candidate` object.
    candidate_id = Column(Integer, ForeignKey('candidates.id'), nullable=False)
    #: Foreign key reference to an associated :py:class:`School` object.
    school_id = Column(Integer, ForeignKey('schools.id'), nullable=False)

    def __init__(self, candidate_or_id, school_or_id, kind, num_votes=1):
        """
        :param candidate_or_id: The :py:class:`Candidate` receiving the vote
        :type candidate_or_id: :py:class:`Candidate` or primary key

        :param school_or_id: The :py:class:`School` associated with the :py:class:`Voter` casting the vote.
        :type school_or_id: :py:class:`School` or primary key

        :param kind: The type of vote. Must be either :py:attr:`Vote.ELECTRONIC` or :py:attr:`Vote.PAPER`.
        :type kind: unicode

        :param num_votes: The number of votes to record. When a :py:class:`Voter` is casting a vote this must be exactly one.
        :type num_votes: int
        """
        self.count = num_votes
        self.candidate_id = getattr(candidate_or_id, 'id', candidate_or_id)
        self.school_id = getattr(school_or_id, 'id', school_or_id)
        if kind in (Vote.ELECTRONIC, Vote.PAPER):
            self.kind = kind
        else:
            raise ValueError


class VotingLog(Base):
    """Record of a voter who has voted in the election.

    The primary use case is to keep track of voters who have already voted to
    prevent them from casting additional votes. The :py:attr:`voter_id`
    foreign key has a *UNIQUE* constraint which enforces the single vote per
    voter restriction on the database level.

    A secondary use case is to enable school representatives to generate
    listings of voters for blacklisting during the paper ballot.

    .. note:: The voting log specifically does not reference the actual
              :py:class:`Vote` which was cast.
    """

    __tablename__ = 'votinglog'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Timestamp when the vote was cast.
    timestamp = Column(Float, nullable=False)

    #: Foreign key to the :py:class:`Voter` instance who cast the vote.
    voter_id = Column(Integer, ForeignKey('voters.id'), nullable=False, unique=True)

    def __init__(self, voter_or_id, timestamp=None):
        """
        :param voter_or_id: The :py:class:`Voter` who cast the vote
        :type voter_or_id: :py:class:`Voter` instance or primary key

        :param timestamp: The timestamp. If ``None``, defaults to ``time.time()``.
        :type timestamp: float
        """
        self.voter_id = getattr(voter_or_id, 'id', voter_or_id)
        self.timestamp = timestamp if timestamp is not None else time.time()


def initialize_sql(engine):
    """Initializes the SQL connection and populates the database.

    :param engine: Database engine.
                   This should be an object returned by the
                   :py:func:`sqlalchemy.create_engine` function.
    :type engine: :py:class:`sqlalchemy.engine.base.Engine`

    :param populate_db: If ``True``, the database will be populated with data.
    :type populate_db: bool
    """
    DBSession.configure(bind=engine)
    bind_engine(engine)
    # Bind the OpenID tables into the engine
    openidalchemy_bind_engine(engine)


def bind_engine(engine):
    Base.metadata.bind = engine
    Base.metadata.create_all(engine, checkfirst=True)
