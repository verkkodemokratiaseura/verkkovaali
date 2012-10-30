# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from openid.association import Association
from openid.store import nonce
from openid.store.interface import OpenIDStore
from openidalchemy.models import Association as AssociationModel
from openidalchemy.models import Nonce
from sqlalchemy import desc

import time


class AlchemyStore(OpenIDStore):
    """Custom store implementation using SQLAlchemy."""

    def __init__(self, session):
        """Creates a new store bound to a SQLAlchemy session."""
        self.session = session

    def makeOpenIdAssociation(self, assoc):
        """Returns an openid.association.Association object initialized with
        data from assoc.
        """
        return Association(
            assoc.handle,
            assoc.secret,
            assoc.issued,
            assoc.lifetime,
            assoc.assoc_type)

    def storeAssociation(self, server_url, association):
        """Set the association for the server URL."""
        assoc = self.session.query(
            AssociationModel).get((server_url, association.handle))

        if assoc is None:
            assoc = AssociationModel.fromOpenIdAssociation(server_url, association)
        else:
            assoc.update(association)

        self.session.add(assoc)

    def getAssociation(self, server_url, handle=None):
        """Get the most recent association that has been set for this server
        URL and handle.

        Returns an openid.association.Association object or None if one could
        not be found.
        """
        query = self.session.query(AssociationModel).filter_by(server_url=server_url)
        if handle is not None:
            query = query.filter_by(handle=handle)

        association_results = query.order_by(desc(AssociationModel.issued)).all()
        if len(association_results) == 0:
            return None

        associations = []
        for assoc_item in association_results:
            association = self.makeOpenIdAssociation(assoc_item)
            if association.getExpiresIn() == 0:
                self.removeAssociation(server_url, association.handle)
            else:
                associations.append(association)

        if len(associations) > 0:
            return associations[0]

        return None

    def removeAssociation(self, server_url, handle):
        """Removes the association for the given server URL and handle.

        Returns True, if the association existed, False otherwise.
        """
        return self.session.query(AssociationModel)\
                    .filter_by(server_url=server_url, handle=handle)\
                    .delete() > 0

    def useNonce(self, server_url, timestamp, salt):
        """Returns whether this nonce is present, and if it is, then removes
        it from the set.
        """
        if abs(timestamp - time.time()) > nonce.SKEW:
            return False

        existing = self.session.query(Nonce).get((server_url, timestamp, salt))
        if existing is None:
            self.session.add(Nonce(server_url, timestamp, salt))
            return True
        else:
            return False

    def cleanupNonces(self):
        """Cleans up expired nonces."""
        threshold = int(time.time()) - nonce.SKEW
        return self.session.query(Nonce)\
                    .filter(Nonce.timestamp < threshold)\
                    .delete()

    def cleanupAssociations(self):
        """Cleans up expired associations."""
        threshold = int(time.time())
        return self.session.query(AssociationModel)\
                    .filter(AssociationModel.issued + AssociationModel.lifetime < threshold)\
                    .delete(synchronize_session='fetch')
