# <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
from datetime import datetime
from datetime import timedelta
from email.header import Header
from email.message import Message
from pyramid.exceptions import Forbidden
from pyramid.exceptions import NotFound
from pyramid.i18n import get_localizer
from pyramid.security import forget
from pyramid.security import remember
from pyramid.url import route_url
from webidentity.i18n import WebIdentityMessageFactory as _
from webidentity.models import DBSession
from webidentity.models import PasswordReset
from webidentity.models import User
from webidentity.sendmail import send_mail
from webidentity.views.oid import extract_local_id
from webidentity.views.oid import identity_url
from webob.exc import HTTPFound

import textwrap


def login(request):
    """Renders a login form and logs in a user if given the correct
    credentials.
    """
    session = DBSession()
    login_url = route_url('login', request)

    login = u''

    if 'form.submitted' in request.POST:
        login = request.POST['login']

        if request.session.get_csrf_token() != request.POST.get('csrf_token'):
            raise Forbidden(u'CSRF attempt detected.')
        else:
            # Allow the use of the full identity URL.
            username = extract_local_id(request, login, relaxed=True)
            if len(username) == 0:
                # Fallback to the the local id.
                username = login

            user = session.query(User).filter_by(username=username).first()
            password = request.POST['password']

            if user is not None and user.check_password(password):
                headers = remember(request, user.username)
                request.session.flash(_(u'You have successfully logged in.'))
                return HTTPFound(location=request.application_url, headers=headers)

            request.session.flash(_(u'Login failed'))

    return {
        'title': _(u'Login'),
        'action_url': login_url,
        'login': login,
        'reset_url': route_url('reset_password', request),
        'csrf_token': request.session.get_csrf_token(),
    }


def logout(request):
    """Logs out the currently authenticated user."""
    headers = forget(request)
    request.session.flash(_(u'You have been logged out'))
    return HTTPFound(location=request.application_url, headers=headers)


class PasswordResetView(object):
    """Password reset logic."""

    def __init__(self, request):
        self.request = request
        self.session = DBSession()
        self.prune_expired()

    def prune_expired(self):
        """Prunes password reset requests that have expired."""
        self.session.query(PasswordReset)\
                .filter(PasswordReset.expires < datetime.now())\
                .delete()

    def render_form(self):
        """Renders the password reset form."""
        return {
            'action_url': route_url('reset_password_initiate', self.request),
            'title': _(u'Reset password'),
        }

    def password_change_form(self):
        """Renders the form for changing a password for a valid token."""
        reset = self.session.query(PasswordReset)\
            .filter(PasswordReset.token == self.request.matchdict['token'])\
            .filter(PasswordReset.expires >= datetime.now())\
            .first()
        if reset is None:
            # No matching password reset found
            raise NotFound()

        user = self.session.query(User).get(reset.user_id)
        if user is None:
            raise NotFound()

        return {
            'action_url': route_url('reset_password_process', self.request),
            'title': _(u'Change password'),
            'token': reset.token,
            }

    def send_confirmation_message(self):
        """Sends an email confirmation message to the user."""
        username = self.request.POST.get('username', '').strip()
        redirect_url = route_url('reset_password', self.request)
        if not username:
            self.request.session.flash(_(u'Please supply a username.'))
        else:
            user = self.session.query(User).filter(User.username == username).first()
            if user is None:
                self.request.session.flash(_(u'The given username does not match any account.'))
            else:
                # Create a password reset request that is valid for 24 hours
                reset = PasswordReset(user.id, datetime.now() + timedelta(hours=24))
                self.session.add(reset)
                message = self.create_message(user, reset)
                from_address = self.request.registry.settings['webidentity_from_address'].strip()
                send_mail(from_address, [user.email], message)
                self.request.session.flash(_(u'Password retrieval instructions have been emailed to you.'))
                redirect_url = self.request.application_url

        return HTTPFound(location=redirect_url)

    def create_message(self, user, reset):
        """Returns an email.message.Message object representing the password
        reset message.
        """
        from_address = self.request.registry.settings['webidentity_from_address'].strip()
        date_format = self.request.registry.settings['webidentity_date_format'].strip()
        locale = get_localizer(self.request)
        subject = locale.translate(
            _(u'Password reset for ${identity}',
            mapping={'identity': identity_url(self.request, user.username)}))

        message = Message()
        message['From'] = Header(from_address, 'utf-8')
        message['To'] = Header(u'{0} <{1}>'.format(user.username, user.email), 'utf-8')
        message['Subject'] = Header(subject, 'utf-8')

        message.set_payload(locale.translate(_(
            u'password-reset-email',
            default=textwrap.dedent(u'''
            Hi ${username}

            A password retrieval process has been initiated for your OpenID
            identity

              ${identity}

            If the process was initiated by you you can continue the process
            of resetting your password by opening the following link in your
            browser

              ${reset_url}

            The link will will expire at ${expiration}.

            If you did not initiate this request you can just ignore this
            email. Your password has not been changed.
            ''').lstrip(),
            mapping=dict(
                username=user.username,
                identity=identity_url(self.request, user.username),
                expiration=reset.expires.strftime(date_format),
                reset_url=route_url('reset_password_token', self.request, token=reset.token)))))

        return message

    def change_password(self):
        """Changes the password for a user."""
        token = self.request.POST.get('token', '').strip()

        if token:
            password = self.request.POST.get('password', '')
            confirm_password = self.request.POST.get('confirm_password', '')
            if len(password.strip()) < 5:
                self.request.session.flash(_(u'Password must be at least five characters long'))
                return HTTPFound(
                    location=route_url('reset_password_token', self.request, token=token))
            elif password != confirm_password:
                self.request.session.flash(_(u'Given passwords do not match'))
                return HTTPFound(
                    location=route_url('reset_password_token', self.request, token=token))
            else:
                reset = self.session.query(PasswordReset)\
                    .filter(PasswordReset.token == token)\
                    .filter(PasswordReset.expires >= datetime.now())\
                    .first()
                if reset is None:
                    raise NotFound()

                user = self.session.query(User).get(reset.user_id)
                if user is None:
                    raise NotFound()

                # Update the user password
                user.password = password
                self.session.add(user)
                self.session.delete(reset)

                self.request.session.flash(_(u'Password changed.'))
                headers = remember(self.request, user.username)
                return HTTPFound(location=self.request.application_url, headers=headers)

        raise NotFound()
