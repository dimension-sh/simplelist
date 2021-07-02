#!/usr/bin/env python

"""Simple List - a simple mailing list tool designed for Postfix."""

import argparse
import os
import pwd
import smtplib
import sys
from email import utils
from email.parser import Parser
from email.policy import default

import yaml

# sysexit.h codes - useful to tell Postfix what is going on
EX_OK = 0  # successful termination
EX_USAGE = 64  # command line usage error
EX_DATAERR = 65  # data format error
EX_NOINPUT = 66  # cannot open input
EX_NOUSER = 67  # addressee unknown
EX_NOHOST = 68  # host name unknown
EX_UNAVAILABLE = 69  # service unavailable
EX_SOFTWARE = 70  # internal software error
EX_OSERR = 71  # system error (e.g., can't fork)
EX_OSFILE = 72  # critical OS file missing
EX_CANTCREAT = 73  # can't create (user) output file
EX_IOERR = 74  # input/output error
EX_TEMPFAIL = 75  # temp failure; user is invited to retry
EX_PROTOCOL = 76  # remote error in protocol
EX_NOPERM = 77  # permission denied
EX_CONFIG = 78  # configuration error


def error(msg: str) -> None:
    """Write an error message to stderr.

    :param msg: The error message
    """
    sys.stderr.write('{0}\n'.format(msg))


def get_userlist(gid: int) -> list:
    """Return all usernames in a system GID.

    :param gid: The GID of the group to return users for
    :returns: A list of usernames
    """
    return [user.pw_name for user in pwd.getpwall() if user.pw_gid == gid]


def main() -> int:  # noqa: WPS212 WPS210 WPS213
    """Run simplelist.

    :returns: A exit code as defined in sysexits.h
    """
    parser = argparse.ArgumentParser('simplelist')
    parser.add_argument('list', help='List name')
    parser.add_argument('-c', '--config', help='Location of the configuration file to use', default='/etc/postfix/simplelist.yaml')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s 0.0.1')  # noqa: WPS323
    args = parser.parse_args()

    # Load config
    config_file = os.path.expandvars(args.config)
    if os.path.exists(config_file):
        with open(config_file, 'r') as fobj:
            config = yaml.safe_load(fobj)
    else:
        error('Config {0} does not exist, exiting...'.format(config_file))
        return EX_CONFIG

    # Check the list is defined
    if args.list not in config['lists']:
        error('Configuration for list {0} does not exist, exiting...'.format(args.list))
        return EX_NOUSER
    list_config = config['lists'][args.list]

    # Get the list of users
    gid = list_config.get('gid')
    users = list_config.get('users')
    if gid:
        user_list = get_userlist(list_config['gid'])
    elif users:
        user_list = list_config['users']
    else:
        error('No GID and no users for {0}, exiting...'.format(args.list))
        return EX_CONFIG

    # Capture the mail
    try:
        mail = Parser(policy=default).parsestr(sys.stdin.read())
    except Exception:
        error('Invalid email passed, exiting...')
        return EX_NOINPUT

    # Check if the sender is allowed
    allowed = list_config['allowed_senders']
    _, from_addr = utils.parseaddr(mail['from'])
    if from_addr not in allowed:
        error("{0} doesn't have permission to mail to {1}".format(from_addr, args.list))
        return EX_NOPERM

    # Construct the mail headers.
    mail.add_header('Sender', '<{0}@{1}>'.format(args.list, config['domain']))
    mail.add_header('List-ID', '{0}.{1}'.format(args.list, config['domain']))
    mail.add_header('Return-Path', '<>')

    # Attempt to connect to the SMTP server
    try:
        server = smtplib.SMTP(list_config.get('smtp', 'localhost'))
    except (ConnectionRefusedError, smtplib.SMTPException) as ex:
        error('Error connecting to the SMTP server: {0}'.format(ex))
        return EX_TEMPFAIL
    except Exception as ex:
        error('Error sending mail: {0}'.format(ex))
        return EX_CONFIG

    # Send the mail to each user in the list.
    for user in user_list:
        mail.replace_header('To', user)
        try:
            server.send_message(mail)
        except smtplib.SMTPException as ex:  # noqa: WPS440
            error('Error sending mail: {0}'.format(ex))
            return EX_TEMPFAIL
    server.quit()

    return EX_OK


if __name__ == '__main__':
    sys.exit(main() or EX_OK)
