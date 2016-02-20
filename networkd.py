#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, Daniel Kuehn <daniel@kuehn.se>
#

DOCUMENTATION = '''
---
module: networkd
short_description: Configure simple and complex networking setups for systemd-networkd
description:
    - Configure simple and complex networking setups for systemd-networkd

notes:
    - To configure the more complex scenarios of networking, i.e. vlans on simple interfaces or
      bridges on vlans on simple interfaces, it requires to either manually setup the required
      steps, and thus only setup the top-level with this module, or map the steps needed with
      this module
options:
  interface:
    description:
      - Name of the interface, will also be the name of the link/network/netdev file
        (i.e interface=eth0 will become eth0.link/netdev/network). For simple interfaces
        they will retain the name that udev or similar system gave them i.e. eth0, enp2s0
        or wlp3s0f1 in ifconfig/ip addr output, for the others, they will have this name.
    required: true
    default: null
  state:
    description:
      - Desired state of the interface configuration files, i.e. if the config files should be
        written or removed.
    required: true
    default: null
    choices: ['present', 'absent']
  bridge_type:
    description:
      - What type of interface the bridge is connected to, if any, initially
    required: false
    default: 'simple'
    choices: ['vlan', 'bond', 'simple', 'none']
  type:
    description:
      - What type of interface to create
    required: false
    default: 'simple'
    choices: ['bridge', 'vlan', 'bond', 'simple']
  vlan_type:
    description:
      - If the interface being configured for the VLAN is the host which the VLANs are created
        from or if its the actual interface for the VLAN
    required: false
    default: 'interface'
    choices: ['interface', 'host']
  mac:
    description:
      - MAC address of the interface
    required: false
    default: null
  ip4:
    description:
      - IPv4 address of the interface
    required: false
    default: null
  gw4:
    description:
      - IPv4 gateway for the interface
    required: false
    default: null
  dns4:
    description:
      - IPv4 DNS servers to setup for the interface
    required: false
    default: null
  ntp:
    description:
      - NTP server to configure for the interface
    required: false
    default: null
  bridge:
    description:
      - Name of the bridge to attach the interface to
    required: false
    default: null
  vlan:
    description:
      - Numeric ID of the VLAN, if vlan_type is interface, or string of one or more VLANs to create
        on the interface, if vlan_type is host
    required: false
    default: null
  destructive:
    description:
      - If the module should try and remove all the files in /etc/systemd/network before running, thus
        making sure that the module setups the network files from scratch
    required: false
    default: false
'''

import os
import tempfile
import filecmp
import glob

class SystemdNetworkd:
	def __init__(self, module):
		self.module = module
		self.interface = module.params['interface']
		self.state = module.params['state']
		self.mac = module.params['mac']
		self.ip4 = module.params['ip4']
		self.gw4 = module.params['gw4']
		self.dns4 = module.params['dns4']
		self.ntp = module.params['ntp']
		self.type = module.params['type']
		self.bridge = module.params['bridge']
		self.bridge_type = module.params['bridge_type']
		self.vlan = module.params['vlan']
		self.vlan_type = module.params['vlan_type']
		self.destructive = module.params['destructive']

		if not self.mac and (self.type in ['simple', 'bond'] or (self.type == 'bridge' and self.bridge_type != 'vlan')):
			module.fail_json(msg='Have to supply a MAC address to match to when type is simple, bridge or bond')

		if not self.vlan and self.type == 'vlan':
			module.fail_json(msg='Have to supply a vlan id, or list of vlan names in case of vlan_type="host", if type="vlan"')

		if self.type == 'bridge' and self.bridge:
			module.fail_json(msg='Can not specify a bridge to attach interface to when creating a bridge: (bridge: {})'.format(self.bridge))

	def _create_link_file(self):
		fd, tmpname = tempfile.mkstemp()
		f = os.fdopen(fd, 'wb')
		str = "[Match]\nMACAddress={mac}\n\n[Link]\nName={interface}\n".format(mac=self.mac, interface=self.interface)
		f.writelines(str)
		f.close()

		dest = "/etc/systemd/network/{}.link".format(self.interface)

		if self._content_changed(str, 'link', tmpname):
			try:
				self.module.atomic_move(tmpname, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (tmpname, dest, e))
				return False

			return True
		else:
			os.remove(tmpname)
			return False

	def _create_network_file(self):
		fd, tmpname = tempfile.mkstemp()
		f = os.fdopen(fd, 'wb')

		if self.type == 'vlan' or self.bridge_type == 'vlan':
			str = "[Match]\nName={}\n\n[Network]\n".format(self.interface)
		elif self.type != 'vlan':
			str = "[Match]\nMACAddress={}\n\n[Network]\n".format(self.mac)

		if self.ip4:
			str += "Address={}\n".format(self.ip4)

		if self.gw4:
			str += "Gateway={}\n".format(self.gw4)

		if self.dns4:
			str += "DNS={}\n".format(self.dns4)

		if self.ntp:
			str += "NTP={}\n".format(self.ntp)

		if self.bridge:
			str += "Bridge={}\n".format(self.bridge)

		if self.vlan_type == 'host' and self.vlan:
			vlans = self.vlan.split(" ")
			for vlan in vlans:
				str += "VLAN={}\n".format(vlan)

		f.writelines(str)
		f.close()
		dest = "/etc/systemd/network/{}.network".format(self.interface)

		if self._content_changed(str, 'network', tmpname):
			try:
				self.module.atomic_move(tmpname, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (tmpname, dest, e))
				return False

			return True
		else:
			os.remove(tmpname)
			return False

	def _create_netdev_file(self):
		fd, tmpname = tempfile.mkstemp()
		f = os.fdopen(fd, 'wb')

		if self.type == 'bridge':
			str = "[NetDev]\nName={}\nKind=bridge\n".format(self.interface)
		elif self.type == 'vlan':
			str = "[NetDev]\nName={name}\nKind=vlan\n\n[VLAN]\nId={id}".format(name=self.interface, id=self.vlan)

		f.writelines(str)
		f.close()

		dest = "/etc/systemd/network/{}.netdev".format(self.interface)

		if self._content_changed(str, 'netdev', tmpname):
			try:
				self.module.atomic_move(tmpname, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (tmpname, dest, e))
				return False

			return True
		else:
			os.remove(tmpname)
			return False

	def _content_changed(self, str, file_type, tmpfile):
		file_path = "/etc/systemd/network/{interface}.{file_type}".format(interface=self.interface, file_type=file_type)

		if os.path.isfile(file_path):
			return not filecmp.cmp(file_path, tmpfile)
		else:
			return True

	def _remove_files(self):
		changed = False
		if self.destructive:
			files = glob("/etc/systemd/network/*")

			# Only remove files that are related systemd-networkd
			for file in files:
				# This makes sure that the module doesn't remove anything
				# but link, netdev and network files
				if file.split(".")[-1] in ['link', 'netdev', 'network']:
					os.remove(file)
		else:
			for type in ['link', 'netdev', 'network']:
				file_path = "/etc/systemd/network/{interface}.{file_type}".format(interface=self.interface, file_type=type)

				if os.path.isfile(file_path):
					os.remove(file_path)
					changed = True

		if not self.destructive and self.state == 'absent':
			self.module.exit_json(changed=changed)
		else:
			return changed

	def configure_link(self):
		changed = False

		if self.state == 'absent' or self.destructive:
			changed = self._remove_files()

		if self.type == 'simple':
			changed = self._create_link_file()

		if self.type in ['bridge', 'vlan']:
			changed = self._create_netdev_file()

		changed = self._create_network_file()

		self.module.exit_json(changed=changed)

def main():
	module = AnsibleModule(
    	argument_spec=dict(
    		interface = dict(required=True, type='str', aliases=['name']),
    		state = dict(required=True, choices=['present', 'absent']),
    		mac = dict(type='str'),
    		ip4 = dict(type='str'),
    		gw4 = dict(type='str'),
    		dns4 = dict(type='str'),
    		ntp = dict(type='str'),
    		type = dict(default='simple', choices=['simple', 'bridge', 'vlan', 'bond']),
    		bridge = dict(type='str'),
    		vlan_type = dict(default='interface', choices=['interface', 'host']),
    		vlan = dict(type='str'),
    		bridge_type = dict(default='simple', choices=['vlan', 'bond', 'simple']),
    		destructive = dict(default=False, type='bool'),
        ),
    )

	networkd = SystemdNetworkd(module)
	networkd.configure_link()

from ansible.module_utils.basic import *
if __name__ == '__main__':
	main()
