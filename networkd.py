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
    default: 'present'
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
  macvlan:
    description:
      - string of one or more MACVLANs to create on the interface, if vlan_type is host
    required: false
    default: null
  destructive:
    description:
      - If the module should try and remove all the files in /etc/systemd/network before running, thus
        making sure that the module setups the network files from scratch
    required: false
    default: null
  dhcp:
    description:
      - Enable DHCP on the interface, either both IPv4 and IPv6, just either or not at all
      required: false
      default: null
      choices: ['yes', 'no', 'ipv4', 'ipv6']
'''

EXAMPLES = '''
# Setup a simple interface with IP address, default gateway, DNS and NTP servers
- networkd: name='eth0' mac=00:11:22:33:44:55 ip4=1.2.3.4 dns4=4.3.2.1 gw4=1.1.1.1 ntp=pool.0.ntp.org state=present

# Setup only an IP address on a interface
- networkd: name='eth1' mac=11:22:33:44:55:66 ip4=2.3.4.5 state=present

# Create several VLANs on a host interface
- networkd: name='eth2' mac=22:33:44:55:66:77 vlan='internet internal' vlan_type='host'

# Setup the VLAN interfaces created on the host interface above
- networkd: name='internet' type=vlan ip4=2.3.4.6 dns4=8.8.8.8 8.8.4.4 gw4=2.3.4.1 state=present vlan=10
- networkd: name='internal' type=vlan dhcp=yes state=present vlan=42

# Setup a bridge and connect a physical NIC to it
- networkd: name='br0' type=bridge ip4=1.1.1.5 state=present
- networkd: name='eth42' mac=00:11:22:44:55:66 bridge=br0 state=present

# Create a VLAN and attach it to a bridge interface
- networkd: name='eth3' mac=11:33:44:55:66:77 vlan='dmz' vlan_type='host' state=present
- networkd: name='dmz' type=vlan state=present vlan=1337 bridge='br-dmz'
- networkd: name='br-dmz' type=bridge dhcp=ipv4 state=present bridge_type=vlan

# Create a standalone bridge
- networkd: name='lxcbr0' mac=33:44:55:77:88:99 ip4=192.168.0.1 dns4=192.168.0.3 state=present bridge_type=none
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
		self.macvlan = module.params['macvlan']
		self.vlan_type = module.params['vlan_type']
		self.destructive = module.params['destructive']
		self.dhcp = module.params['dhcp']

		if self.dhcp and self.ip4:
			module.fail_json(msg='Cannot specify static address and DHCP at the same time')

		if not self.mac and (self.type in ['simple', 'macvlan', 'bond'] or (self.type == 'bridge' and self.bridge_type != 'vlan')):
			module.fail_json(msg='Have to supply a MAC address to match to when type is macvlan, simple, bridge or bond')

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

		if not self.dhcp:
			if self.ip4:
				str += "Address={}\n".format(self.ip4)

			if self.gw4:
				str += "Gateway={}\n".format(self.gw4)
		else:
			str += "DHCP={}\n".format(self.dhcp)

		if self.dns4:
			str += "DNS={}\n".format(self.dns4)

		if self.ntp:
			str += "NTP={}\n".format(self.ntp)

		if self.bridge:
			str += "Bridge={}\n".format(self.bridge)

		if self.vlan_type == 'host':
			if self.vlan:
				vlans = self.vlan.split(" ")
				for vlan in vlans:
					str += "VLAN={}\n".format(vlan)
			if self.macvlan:
				macvlans = self.macvlan.split(" ")
				for macvlan in macvlans:
					str += "MACVLAN={}\n".format(macvlan)

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
		elif self.type in ['macvlan','vlan']:
			str = "[NetDev]\nName={name}\nKind={kind}".format(name=self.interface, kind=self.type)

		if(self.mac):
			str += "\nMACAddress={}".format(self.mac)

		if self.type == 'vlan':
			str += "\n\n[VLAN]\nId={id}".format(id=self.vlan)
		elif self.type == 'macvlan':
			str += "\n\n[MACVLAN]\nMode=bridge"

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

		if self.type in ['bridge', 'vlan', 'macvlan']:
			changed = self._create_netdev_file()

		changed = self._create_network_file()

		self.module.exit_json(changed=changed)

def main():
	module = AnsibleModule(
    	argument_spec=dict(
    		interface = dict(required=True, type='str', aliases=['name']),
    		state = dict(default='present', choices=['present', 'absent']),
    		mac = dict(type='str'),
    		ip4 = dict(type='str'),
    		gw4 = dict(type='str'),
    		dns4 = dict(type='str'),
    		ntp = dict(type='str'),
    		type = dict(default='simple', choices=['simple', 'bridge', 'vlan', 'macvlan', 'bond']),
    		bridge = dict(type='str'),
    		vlan_type = dict(default='interface', choices=['interface', 'host']),
    		vlan = dict(type='str'),
    		macvlan = dict(type='str'),
    		bridge_type = dict(default='simple', choices=['vlan', 'bond', 'simple']),
    		destructive = dict(default=False, type='bool'),
    		dhcp = dict(type='str', choices=['yes', 'no', 'ipv4', 'ip6']),
        ),
    )

	networkd = SystemdNetworkd(module)
	networkd.configure_link()

from ansible.module_utils.basic import *
if __name__ == '__main__':
	main()
