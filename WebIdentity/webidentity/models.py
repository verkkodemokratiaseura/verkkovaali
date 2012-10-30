# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from openidalchemy.models import bind_engine
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import PickleType
from sqlalchemy import String
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import synonym
from z3c.bcrypt import BcryptPasswordManager
from zope.sqlalchemy import ZopeTransactionExtension

import datetime
import time
import uuid

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()
password_manager = BcryptPasswordManager()


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
    #: Encrypted password.
    _password = Column('password', String(255))
    #: Email address.
    email = Column(String(255))

    #: List of :py:class:`Persona` objects associated with the user.
    personas = relationship('Persona', backref='user', cascade='all, delete-orphan')
    #: List of :py:class:`VisitedSite` objects associated with the user.
    visited_sites = relationship('VisitedSite', backref='user', cascade='all')
    #: List of :py:class:`Activity` objects associated with the user.
    activity = relationship('Activity', backref='user', cascade='all')

    def __init__(self, username, password, email):
        """
        :param username: The local id of the user.
        :type username: str

        :param password: Password in plain-text. The password will be stored
                         in ``bcrypt`` encrypted form and will not be
                         available in plain-text form through this object.
        :type password: unicode

        :param email: Email address.
        :type email: str
        """
        self.username = username
        self.password = password
        self.email = email

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


class Persona(Base):
    """A persona is a grouping of :py:class:`UserAttribute` objects under a
    single name.

    A :py:class:`User` may have multiple personas, e.g. "Home", "Work" which
    contain different sets of the :py:class:`UserAttribute` objects.
    """

    __tablename__ = 'personas'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: name of the persona.
    name = Column(Unicode(255))

    #: Foreign key reference to the associated :py:class:`User`.
    user_id = Column(Integer, ForeignKey('users.id'))

    #: List of :py:class:`UserAttribute` objects associated with this persona.
    attributes = relationship('UserAttribute', backref='persona', cascade='all')

    def __init__(self, name, attributes=None):
        """
        :param name: The name of the persona.
        :type name: unicode

        :param attributes: List of :py:class:`UserAttribute` objects to
                           associate with the persona.
        :type attributes: list
        """
        self.name = name
        if attributes is not None:
            self.attributes = attributes


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
    user_id = Column(Integer, ForeignKey('users.id'))

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


class UserAttribute(Base):
    """User attribute is a key-value piece of information about a
    :py:class:`User`.

    User attributes are always associated with a particular
    :py:class:`Persona`.

    A key must be a `Attribute Type Identifier
    <http://openid.net/specs/openid-attribute-exchange-1_0.html#attribute-name-definition>`_
    as defined by the OpenID `Attribute Exchange 1.0
    <http://openid.net/specs/openid-attribute-exchange-1_0.html>`_
    specification.
    """

    __tablename__ = 'user_attributes'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Attribute Type Identifier (URI).
    type_uri = Column(String(255))
    #: User attribute value.
    value = Column(Unicode(255))

    #: Foreign key reference to the associated :py:class:`Persona`.
    persona_id = Column(Integer, ForeignKey('personas.id'))

    def __init__(self, type_uri, value):
        """
        :param type_uri: Attribute Type Identifier (URI).
        :type type_uri: unicode

        :param value: User attribute value.
        :type value: unicode
        """
        self.type_uri = type_uri
        self.value = value


class VisitedSite(Base):
    """Information about visited sites.

    The purpose is to keep track of visited sites and the information about
    the authentication decisions. In case attribute exchange took place as
    part of the authentication process the choice of :py:class:`Persona` is
    persisted.

    The user may also choose to remember to connection for future use and
    forego the need to re-authenticate when accessing the same site again.
    """

    __tablename__ = 'visited_sites'
    __table_args__ = (
        UniqueConstraint('trust_root', 'user_id'),
        {'mysql_engine': 'InnoDB',
         'mysql_charset': 'utf8',
        },
    )

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: Address of the OpenID consumer site (trust root).
    trust_root = Column(String(255), nullable=False)
    #: Indicator whether subsequent authentication requests are handled automatically.
    remember = Column(Boolean, default=False, nullable=False)

    #: Foreign key reference to an associated :py:class:`User`.
    user_id = Column(Integer, ForeignKey('users.id'))
    #: Foreign key reference to an associated :py:class:`Persona`.
    persona_id = Column(Integer, ForeignKey('personas.id'), nullable=True)

    #: Associated :py:class:`Persona` or ``None``.
    persona = relationship('Persona', uselist=False)

    def __init__(self, trust_root, remember=False):
        """
        :param trust_root: Address of the OpenID consumer site.
        :type trust_root: str

        :param remember: ``True``, if subsequent authentication requests should
                         be handled automatically.
        :type remember: bool
        """
        self.trust_root = trust_root
        self.remember = remember

Index('ix_user_trust_root', VisitedSite.user_id, VisitedSite.trust_root)


class Activity(Base):
    """Activity log keeps entries of the actions performed by users and
    provides a simple audit trail.
    """

    __tablename__ = 'activity'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: User logged in successfully.
    LOGIN = u'Login'
    #: User login attempt failed.
    FAILED_LOGIN = u'Login failed'
    #: User authorized an authentication request for future use.
    AUTHORIZE = u'Authorize'
    #: User authorized an authentication request for one-time use.
    AUTHORIZE_ONCE = u'AuthorizeOnce'
    #: User denied an authentication request.
    DENY = u'Deny'

    #: Primary key.
    id = Column(Integer, primary_key=True)
    #: The URL associated with the entry (if available).
    url = Column(String(255), nullable=True)
    #: Timestamp of the entry.
    timestamp = Column(DateTime, nullable=False)
    #: The originating ip-address.
    ipaddr = Column(String(15), nullable=True)
    #: Login session identifier (if available).
    session = Column(String(255), nullable=False)
    #: Type of action (:py:attr:`Activity.LOGIN`, :py:attr:`Activity.FAILED_LOGIN`,
    #: :py:attr:`Activity.AUTHORIZE`, :py:attr:`Activity.AUTHORIZE_ONCE`,
    #: :py:attr:`Activity.DENY`)
    action = Column(Enum(LOGIN, FAILED_LOGIN, AUTHORIZE, AUTHORIZE_ONCE, DENY))

    #: Foreign key reference to an associated :py:class:`User`.
    user_id = Column(Integer, ForeignKey('users.id'))

    def __init__(self, ipaddr, session, action, url=None, timestamp=None):
        """
        :param ipaddr: Originating ip-address.
        :type ipaddr: str

        :param session: Login session identifier.
        :type session: str

        :param action: Action, one of :py:attr:`Activity.LOGIN`,
                       :py:attr:`Activity.FAILED_LOGIN`, :py:attr:`Activity.AUTHORIZE`,
                       :py:attr:`Activity.AUTHORIZE_ONCE` or :py:attr:`Activity.DENY`.
        :type action: enum

        :param url: OpenID consumer URL, if available.
        :type url: str

        :param timestamp: Timestamp of the entry, defaults to
                          ``datetime.datetime.now()``.
        :type timestamp: ``datetime.datetime``.
        """
        if timestamp is None:
            timestamp = datetime.datetime.now()
        self.timestamp = timestamp
        self.ipaddr = ipaddr[:15]
        self.session = session
        self.action = action
        self.url = url

Index('ix_user_id_session', Activity.user_id, Activity.session)


class CheckIdRequest(Base):
    """Stored OpenID Check ID requests during an authentication process.

    These requests are transient.
    """
    __tablename__ = 'active_requests'
    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        }

    #: Primary key.
    key = Column(String(64), primary_key=True)
    #: :py:class:`openid.server.CheckIDRequest` object.
    request = Column(PickleType, nullable=False)
    #: Timestamp of the Check ID request.
    issued = Column(Integer, nullable=False)

    def __init__(self, key, request, issued=None):
        """
        :param key: Check ID request identifier.
        :type key: str

        :param request: :py:class:`openid.server.CheckIDRequest` object.
        :type request: :py:class:`openid.server.CheckIDRequest`

        :param issued: Timestamp when the Check ID request was created,
                       defaults to ``time.time()``.
        :type issued: float
        """
        self.key = key
        self.request = request
        self.issued = issued if issued is not None else int(time.time())


def initialize_sql(engine, populate_db=True):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine, checkfirst=True)
    # Bind the OpenID tables into the engine
    bind_engine(engine)
