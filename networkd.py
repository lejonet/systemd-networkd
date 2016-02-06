#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, Daniel Kuehn <daniel@kuehn.se>
#

import os
import tempfile
import filecmp
from ansible.module_utils.basic import *

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
				self.module.atomic_move(name, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (name, dest, e))
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
				self.module.atomic_move(name, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (name, dest, e))
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
				self.module.atomic_move(name, os.path.realpath(dest))
			except Exception as e:
				self.module.fail_json(msg='Could not move %s to %s: %s' % (name, dest, e))
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

	def configure_link(self):
		changed = False

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
        ),
    )

	networkd = SystemdNetworkd(module)
	networkd.configure_link()

if __name__ == '__main__':
	main()
