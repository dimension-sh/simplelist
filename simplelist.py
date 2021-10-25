#!/usr/bin/env python

"""Simple List - a simple mailing list tool designed for Postfix."""

import argparse
import os
import pwd
import grp
import smtplib
import sys
import syslog
from email import utils
from email.parser import Parser
from email.policy import default

import yaml


def message(level: int, msg: str) -> None:
    """Write an error message to stderr.

    :param level: The syslog level for the message
    :param msg: The message
    """
    syslog.syslog(level, msg)
    sys.stderr.write('{0}\n'.format(msg))


def get_userlist(gid: int) -> list:
    """Return all usernames in a system GID.

    :param gid: The GID of the group to return users for
    :returns: A list of usernames
    """
    # Get users with a primary GID of the target group
    users = [user.pw_name for user in pwd.getpwall() if user.pw_gid == gid]

    # Add secondary group members
    users.extend(grp.getgrgid(gid).gr_mem)

    return set(users)


def main() -> int:  # noqa: WPS212 WPS210 WPS213
    """Run simplelist.

    :returns: A exit code as defined in sysexits.h
    """
    parser = argparse.ArgumentParser('simplelist')
    parser.add_argument('list', help='List name')
    parser.add_argument('-c', '--config', help='Location of the configuration file to use', default='/etc/postfix/simplelist.yaml')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s 1.1.0')  # noqa: WPS323
    args = parser.parse_args()

    syslog.openlog('simplelist', logoption=syslog.LOG_PID, facility=syslog.LOG_MAIL)

    # Load config
    config_file = os.path.expandvars(args.config)
    if os.path.exists(config_file):
        with open(config_file, 'r') as fobj:
            config = yaml.safe_load(fobj)
    else:
        message(syslog.LOG_CRIT, 'Config {0} does not exist, exiting...'.format(config_file))
        return os.EX_CONFIG

    # Check the list is defined
    if args.list not in config['lists']:
        message(syslog.LOG_CRIT, 'Configuration for list {0} does not exist, exiting...'.format(args.list))
        return os.EX_NOUSER
    list_config = config['lists'][args.list]

    # Get the list of users
    gid = list_config.get('gid')
    users = list_config.get('users')
    if gid:
        user_list = get_userlist(list_config['gid'])
    elif users:
        user_list = list_config['users']
    else:
        message(syslog.LOG_CRIT, 'No GID and no users for {0}, exiting...'.format(args.list))
        return os.EX_CONFIG

    # Capture the mail
    try:
        mail = Parser(policy=default).parsestr(sys.stdin.read())
    except Exception:
        message(syslog.LOG_CRIT, 'Invalid email passed, exiting...')
        return os.EX_NOINPUT

    # Check if the sender is allowed
    _, from_addr = utils.parseaddr(mail['from'])

    if list_config.get('allowed_senders') is None:
        message(syslog.LOG_WARNING, 'No allowed_senders defined for {0}, allowing all mail'.format(args.list))
    else:
        allowed_users = []
        for addr in list_config.get('allowed_senders'):
            if isinstance(addr, dict) and addr.get('gid'):
                addresses = ['{0}@{1}'.format(user, config['domain']) for user in get_userlist(addr.get('gid'))]
                allowed_users.extend(addresses)
            elif isinstance(addr, str):
                allowed_users.append(addr)

        if from_addr not in allowed_users:
            message(syslog.LOG_NOTICE, "{0} doesn't have permission to mail to {1}".format(from_addr, args.list))
            return os.EX_NOPERM

    # Construct the mail headers.
    mail.add_header('Sender', '<{0}@{1}>'.format(args.list, config['domain']))
    mail.add_header('List-ID', '{0}.{1}'.format(args.list, config['domain']))
    mail.add_header('Return-Path', '<>')

    # Attempt to connect to the SMTP server
    try:
        server = smtplib.SMTP(list_config.get('smtp', 'localhost'))
    except (ConnectionRefusedError, smtplib.SMTPException) as ex:
        message(syslog.LOG_ERR, 'Error connecting to the SMTP server: {0}'.format(ex))
        return os.EX_TEMPFAIL
    except Exception as ex:
        message(syslog.LOG_ERR, 'Error sending mail: {0}'.format(ex))
        return os.EX_CONFIG

    # Send the mail to each user in the list.
    message(syslog.LOG_INFO, 'Sending mail to {0} user(s)'.format(len(user_list)))
    for user in user_list:
        mail.replace_header('To', user)
        try:
            server.send_message(mail)
        except smtplib.SMTPException as ex:  # noqa: WPS440
            message(syslog.LOG_ERR, 'Error sending mail: {0}'.format(ex))
            return os.EX_TEMPFAIL
    server.quit()

    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main() or os.EX_OK)
