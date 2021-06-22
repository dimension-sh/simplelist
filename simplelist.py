"""
Simple List - a simple mailing list tool designed for Postfix
"""
import os
import sys
import pwd
import smtplib
import argparse
from email.parser import Parser
from email.policy import default
import yaml

__author__ = 'Andrew Williams <nikdoof@dimension.sh>'
__version__ = '0.0.1'


def get_userlist(gid: int) -> list:
    """ Returns all usernames in a group gid """
    return [x.pw_name for x in pwd.getpwall() if x.pw_gid == gid]


def main():
    parser = argparse.ArgumentParser('simplelist')
    parser.add_argument('list', help='List name')
    parser.add_argument('-c', '--config', help='Location of the configuration file to use',
                        default='/etc/postfix/simplelist.yaml')
    parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + __version__)
    args = parser.parse_args()

    # Load config
    config_file = os.path.expandvars(args.config)
    if os.path.exists(config_file):
        with open(config_file, 'r') as fobj:
            config = yaml.load(fobj)
    else:
        sys.stderr.write('Config %s does not exist, exiting...' % config_file)
        return 70

    # Check the list is defined
    if not args.list in config['lists']:
        sys.stderr.write('Configuration for list %s does not exist, exiting...' % config_file)
        return 67
    list_config = config['lists'][args.list]

    # Get the list of users
    if 'gid' in list_config:
        user_list = get_userlist(list_config['gid'])
    elif 'users' in list_config:
        user_list = list_config['users']

    # Capture the mail
    try:
        mail = Parser(policy=default).parsestr(sys.stdin.read())
    except:
        sys.stderr.write('Invalid email passed, exiting...')
        return 66

    allowed = list_config['allowed_senders']
    if not mail['from'].strip() in allowed:
        return 77

    mail.add_header('Sender', '<%s@%s>' % (args.list, config['domain']))
    mail.add_header('List-ID', '%s.%s' % (args.list, config['domain']))
    mail.add_header('Return-Path', '<>')

    s = smtplib.SMTP(list_config.get('smtp', 'localhost'))
    for user in get_userlist():
        mail.replace_header('To', user)
        s.send_message(mail)
    s.quit()


if __name__ == '__main__':
    sys.exit(main() or 0)
