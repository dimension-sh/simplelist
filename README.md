# SimpleList

A simple mailing list tool designed for Postfix. Re-inventing the wheel for a mailing list, but MailMan seemed like overkill for a simple announcement mailing list.

## Installation


* Copy over `simplelist.py` to a location of your choice, `/etc/postfix` will be used for further examples.
* Copy `simplelist.yaml` to `/etc/postfix`.
* If you have SELinux configured, run `chcon -v -t postfix_local_exec_t /etc/postfix/simplelist.py`

## Setup A Mailing List

* Add a line to your `/etc/aliases` for the mailing list:

```
sysop: "|/etc/postfix/simplelist.py sysop"
```

* Run `newalias`
* Edit `simplelist.yaml` to your needs.
  * `gid` sends the mail to all members of that Group ID
  * `users` is a list of email addresses
  * `allowed_users` is the mail address of users allowed to send to the list.