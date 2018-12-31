import charms.apt
from charms.reactive import when, when_not, set_flag
from charmhelpers.core import hookenv
from charmhelpers import fetch
from charmhelpers.core.templating import render
from charmhelpers.core import host

from os import chmod, mkdir

import xml.etree.ElementTree

CROWD_URL="https://product-downloads.atlassian.com/software/crowd/downloads/atlassian-crowd-{}.tar.gz"
CROWD_INSTALL="/opt/atlassian/crowd"


@when_not('apt.installed.openjdk-8-jdk')
def install_jdk():
    charms.apt.queue_install(['openjdk-8-jdk'])


@when_not('crowd.installed')
@when('apt.installed.openjdk-8-jdk')
def install_crowd():
    host.adduser('crowd')
    fetch.install_remote(
        source=CROWD_URL.format(hookenv.config('crowd-version')), # version
        dest=CROWD_INSTALL,
        # checksum=None,
        # hash_type='sha1'
    )
    host.lchownr(CROWD_INSTALL,
        owner='crowd',
        group='crowd',
    )
    for dir in [
      '{}/atlassian-crowd-{}'.format(CROWD_INSTALL, hookenv.config('crowd-version')),
      '/var/crowd-home',
      '/var/crowd-home/shared/',
    ]:
      try:
          mkdir(dir)
      except:
          pass
      host.chownr(dir,
          owner='crowd',
          group='crowd',
          chowntopdir=True,
      )
    set_flag('crowd.installed')


@when('crowd.installed',
      'config.changed',
)
def configure_crowd():
    opts = {}
    opts['crowd_home'] = '/var/crowd-home'
    render(
        'crowd-init.properties',
        "{}/atlassian-crowd-{}/crowd-webapp/WEB-INF/classes/crowd-init.properties".format(CROWD_INSTALL, hookenv.config('crowd-version')),
        opts,
        owner="crowd", group="crowd",
    )
    service_opts = {
        'crowd_install_dir': CROWD_INSTALL,
        'crowd_version': hookenv.config('crowd-version'),
    }
    render(
        'crowd.service',
        '/etc/systemd/system/crowd.service',
        service_opts,
    )
    chmod("{}/atlassian-crowd-{}/start_crowd.sh".format(CROWD_INSTALL, hookenv.config('crowd-version')), 0o755)
    chmod("{}/atlassian-crowd-{}/stop_crowd.sh".format(CROWD_INSTALL, hookenv.config('crowd-version')), 0o755)

    if hookenv.config('license-key'):
        install_license(hookenv.config('license-key'))

    host.service_start('crowd')
    host.service_resume('crowd')
    hookenv.open_port(8095)


def install_license(key):
    opts = {
        'license_key': key,
    }
    if hookenv.config('server-id'):
        opts['server_id'] = hookenv.config('server-id')
    else:
        existing_id = crowd_config('crowd.server.id')
        if existing_id:
            opts['server_id'] = existing_id

    render(
        'crowd.config.xml',
        '/var/crowd-home/shared/crowd.cfg.xml',
        opts,
        owner="crowd", group="crowd",
    )


def crowd_config(key, file='/var/crowd-home/shared/crowd.cfg.xml'):
    try:
        e = xml.etree.ElementTree.parse(file).getroot()
        return e.find(".//property[@name='{}']".format(key)).text
    except:
        return None