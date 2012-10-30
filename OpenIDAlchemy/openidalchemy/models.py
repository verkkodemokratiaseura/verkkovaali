# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -*- coding: utf-8 -*-
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import LargeBinary
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Nonce(Base):
    __tablename__ = 'nonces'
    __table_args__ = (
        PrimaryKeyConstraint('server_url', 'timestamp', 'salt'),
        {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        })

    server_url = Column(String(255), nullable=False)
    timestamp = Column(Integer, nullable=False)
    salt = Column(String(40), nullable=False)

    def __init__(self, server_url, timestamp, salt):
        self.server_url = server_url
        self.timestamp = timestamp
        self.salt = salt


class Association(Base):
    __tablename__ = 'associations'
    __table_args__ = (
        PrimaryKeyConstraint('server_url', 'handle'),
        {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
        })

    server_url = Column(String(255), nullable=False)
    handle = Column(String(255), nullable=False)
    secret = Column(LargeBinary, nullable=False)
    issued = Column(Integer, nullable=False)
    lifetime = Column(Integer, nullable=False)
    assoc_type = Column(String(64), nullable=False)

    def __init__(self, server_url, handle, secret, issued, lifetime, assoc_type):
        self.server_url = server_url
        self.handle = handle
        self.secret = secret
        self.issued = issued
        self.lifetime = lifetime
        self.assoc_type = assoc_type

    @classmethod
    def fromOpenIdAssociation(cls, server_url, association):
        """Returns an Association model object initialized with values from
        the given server URL and an openid.association.Association object.
        """
        return Association(
            server_url,
            association.handle,
            association.secret,
            association.issued,
            association.lifetime,
            association.assoc_type)

    def update(self, association):
        """Updates the values for this Association from the given
        openid.association.Association object.

        Raises a ValueError if the ``handle`` attribute of the given
        association differs from the current value.
        """
        if association.handle != self.handle:
            raise ValueError('Handle mismatch: {0} != {1}'.format(self.handle, association.handle))

        self.secret = association.secret
        self.issued = association.issued
        self.lifetime = association.lifetime
        self.assoc_type = association.assoc_type


def bind_engine(engine):
    Base.metadata.bind = engine
    Base.metadata.create_all(checkfirst=True)
