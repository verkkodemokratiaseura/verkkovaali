# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from datetime import datetime
from nuorisovaalit.models import School
from nuorisovaalit.models import bind_engine
from pyramid.security import ALL_PERMISSIONS
from pyramid.security import Allow
from pyramid.security import DENY_ALL
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import PickleType
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import synonym
from z3c.bcrypt import BcryptPasswordManager
from zope.sqlalchemy import ZopeTransactionExtension

import logging
import uuid

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()
password_manager = BcryptPasswordManager()


class RootFactory(object):
    """Custom root factory.

    An instance of this class will function as the context for all views. The
    instance implements the access control policy which has the following
    rules:

     * Members of the ``group:admin`` group have access to everything all the
       time.

     * Members of the ``group:allianssi`` group have access to resources
       granted to them all the time.

     * Members of the ``group:school`` group have time dependent access to
       specific resources according to the following schedule:

        * The ``submit-voters`` permission is granted for a semi-open time
          period before ending at 16.3.2011 12:00. This is the deadline for
          submitting the list of eligible voters per school.

        * The ``download-voters`` permission is granted for a semi-open time
          period starting at 28.3.2011 00:00. This is when the electronic
          voting has finished and schools may download the list of voters who
          took part in it.

        * The ``submit-results`` permission is granted for a semi-open time
          period starting at 28.3.2011 00:00 and ending at 8.3.2011 23:59:59.

    It is possible to override the date based checks by setting a

      nuorisovaalitadmin.skip_deadline_check = true

    configuration option.
    """

    def __init__(self, request):
        if getattr(request, 'matchdict', None) is not None:
            self.__dict__.update(request.matchdict)

        self.__acl__ = [
            (Allow, 'group:admin', ALL_PERMISSIONS),
            (Allow, 'group:allianssi', 'view-stats'),
        ]

        now = datetime.now()
        skip_check = request.registry.settings.get(
            'nuorisovaalitadmin.skip_deadline_check', '').strip() == 'true'

        if skip_check:
            log = logging.getLogger('nuorisovaalitadmin')
            log.warn('Deadline checks are disabled.')

        if skip_check or now < datetime(2011, 3, 16, 12, 0, 0):
            self.__acl__.append(
                (Allow, 'group:school', 'submit-voters'),
            )
        if skip_check or now >= datetime(2011, 3, 28):
            self.__acl__.append(
                (Allow, 'group:school', 'download-voters'),
            )
        if skip_check or (datetime(2011, 3, 28) <= now < datetime(2011, 4, 9)):
            self.__acl__.extend([
                (Allow, 'group:school', 'submit-results'),
                (Allow, 'group:school_limited', 'submit-results')
            ])
        if skip_check or now >= datetime(2011, 4, 12, 12, 0, 0):
            self.__acl__.extend([
                (Allow, 'group:school', 'download-results'),
                (Allow, 'group:school_limited', 'download-results'),
            ])

        self.__acl__.append(DENY_ALL)


#: Join table for user/group membership
GroupMembership = Table(
    'group_membership', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('group_id', Integer, ForeignKey('groups.id')),
    mysql_engine='InnoDB',
    mysql_charset='utf8')


class User(Base):
    """User is a principal which is associated with a single OpenID identity."""

    __tablename__ = 'users'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Username (also called the provider local id).
    username = Column(String(255), unique=True)
    #: Full name.
    fullname = Column(Unicode(255))
    #: Encrypted password.
    _password = Column('password', String(255))
    #: Email address.
    email = Column(String(255))
    #: Choice of electronic election participation.
    eparticipation = Column(Boolean, default=False, nullable=False)

    #: Foreign key reference to an associated :py:class:`nuorisovaalit.models.School` object.
    school_id = Column(Integer, ForeignKey(School.id), nullable=False)
    #: Reference to the associated :py:class:`nuorisovaalit.models.School` object.
    school = relationship(School)
    #: Reference to groups this user is a member of.
    groups = relationship("Group", secondary=GroupMembership)

    def __init__(self, username, password, fullname, email, eparticipation=False, school_or_id=None, group=None):
        """
        :param username: The local id of the user.
        :type username: str

        :param password: Password in plain-text. The password will be stored
                         in ``bcrypt`` encrypted form and will not be
                         available in plain-text form through this object.
        :type password: unicode

        :param email: Email address.
        :type email: str

        :param eparticipation: `True`, if the user takes part the in electronic
                         election, `False` otherwise.
        :type eparticipation: bool

        :param school_or_id: Reference to an associated school.
        :type school_or_id': :py:class:`nuorisovaalit.models.School` or int
        """
        self.username = username
        self.password = password
        self.fullname = fullname
        self.email = email
        self.eparticipation = eparticipation

        if school_or_id is not None:
            self.school_id = getattr(school_or_id, 'id', school_or_id)
        if group is not None:
            self.groups.append(group)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, password):
        """Stores the password in encrypted form."""
        self._password = password_manager.encodePassword(password)

    #: Encrypted password
    password = synonym('_password', descriptor=password)

    def check_password(self, password):
        """Returns ``True`` if the given ``password`` matches to stored one,
        ``False`` otherwise.

        :param password: The plain-text password to check.
        :type password: str

        :rtype: bool
        """
        return password_manager.checkPassword(self.password, password)


class Group(Base):
    """User group.

    A grouping of users which can be associated with access control
    permissions.
    """

    __tablename__ = 'groups'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Group permission identifier. Members of the group will get a group id
    #: of the form "group:${name}" which can be used in setting the the ACL
    #: declarations. See :py:func:`nuorisovaalitadmin.views.login.groupfinder`
    #: for details.
    name = Column(String(100), nullable=False, unique=True)
    #: Human readable title of the group.
    title = Column(Unicode(255), nullable=False)

    #: List of :py:class:`User` instances which are members of this group.
    members = relationship("User", secondary=GroupMembership)

    def __init__(self, name, title):
        self.name = name.strip()
        self.title = title.strip()


class PasswordReset(Base):
    """Password reset request.

    A password reset allows a user to reset her current password by performing
    an email verification and upon successful response granting access using
    a unique token.

    A password reset request is valid only for a limited time.
    """

    __tablename__ = 'passwordreset'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Password reset expiration date.
    expires = Column(DateTime, nullable=False)
    #: Unique token for the password reset request.
    token = Column(String(36), nullable=False)

    #: Foreign key reference to the associated :py:class:`User` object.
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    def __init__(self, user_id, expires, token=None):
        """
        :param user_id: Primary key of the associated :py:class:`User`.
        :type user_id: int

        :param expires: Password reset request expiration date.
        :type expires: ``datetime.datetime``

        :param token: Unique token for the password reset request. If ``None``,
                      a random value will be generated using the
                      ``uuid.uuid4()`` function.
        :type token: unicode
        """
        self.user_id = user_id
        self.expires = expires
        if token is None:
            # Use a random UUID by default
            token = unicode(uuid.uuid4())
        self.token = token


class CSVSubmission(Base):
    """CSV information provided by school representatives.
    """

    __tablename__ = 'csvsubmission'
    __table_args__ = (
        UniqueConstraint('school_id', 'kind'),
        {'mysql_engine': 'InnoDB',
         'mysql_charset': 'utf8',
        },
    )

    VOTER = u'voter'
    RESULT = u'result'

    #: Primary key
    id = Column(Integer, primary_key=True)
    #: Contents of the CSV submission parsed into Python objects.
    csv = Column(PickleType(mutable=False), nullable=False)
    #: Timestamp when the submission was received.
    timestamp = Column(DateTime, nullable=False)

    #: The type of the CSV submission. Either :py:attr:`CSVSubmission.VOTER`
    # or :py:attr:`CSVSubmission.RESULT`
    kind = Column(Enum(VOTER, RESULT), nullable=False, index=True)

    #: Foreign key reference to the associated
    #: :py:class:`nuorisovaalit.models.School` object.
    school_id = Column(Integer, ForeignKey(School.id), nullable=False)
    #: Reference to the associated :py:class:`nuorisovaalit.models.School` object.
    school = relationship(School, backref='csvsubmission')

    def __init__(self, csv, school_or_id, kind):
        self.csv = csv
        self.school_id = getattr(school_or_id, 'id', school_or_id)
        self.timestamp = datetime.now()
        if kind not in (CSVSubmission.VOTER, CSVSubmission.RESULT):
            raise ValueError
        self.kind = kind


def initialize_sql(engine):
    DBSession.configure(bind=engine)
    bind_engine(engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
