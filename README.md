Ansible module systemd-networkd
===============================

This repo contains a module for ansible, to handle networking with systemd-networkd. It currently supports simple, vlan and bridge interfaces.

License
=======

This repo is licensed under the GPLv3.

Examples
--------
```
# Setup a simple interface with IP address, default gateway, DNS and NTP servers
- networkd: name='eth0' mac=00:11:22:33:44:55 ip4=1.2.3.4 dns4=4.3.2.1 gw4=1.1.1.1

# Setup only an IP address on a interface
- networkd: name='eth1' mac=11:22:33:44:55:66 ip4=2.3.4.5 ntp=pool.ntp.org

# Create several VLANs on a host interface
- networkd: name='eth2' mac=22:33:44:55:66:77 vlan='internet internal' vlan_type='host'

# Setup the VLAN interfaces created on the host interface above
- networkd: name='internet' type=vlan ip4=2.3.4.6 dns4=8.8.8.8 8.8.4.4 gw4=2.3.4.1 vlan=10
- networkd: name='internal' type=vlan dhcp=yes state=present vlan=42

# Create several MACVLANs on a host interface
- networkd: name='eth3' mac=33:44:55:66:77:88' vlan='eth3.macvlan1 eth3.macvlan2' vlan_type='host'

# Setup the MACVLAN interfaces created on the host interface above
- networkd: name='eth3.macvlan1' type=macvlan mac=b1:c8:5b:dd:ed:47 ip4=2.3.4.6 gw4=2.3.4.1
- networkd: name='eth3.macvlan2' type=macvlan mac=e7:aa:fd:a3:5e:33 ip4=2.3.4.7 gw4=2.3.4.1

# Setup a bridge and connect a physical NIC to it
- networkd: name='br0' type=bridge ip4=1.1.1.5
- networkd: name='eth42' mac=00:11:22:44:55:66 bridge=br0

# Create a VLAN and attach it to a bridge interface
- networkd: name='eth4' mac=11:33:44:55:66:77 vlan='dmz' vlan_type='host'
- networkd: name='dmz' type=vlan vlan=1337 bridge='br-dmz'
- networkd: name='br-dmz' type=bridge dhcp=ipv4 bridge_type=vlan

# Create a standalone bridge
- networkd: name='lxcbr0' mac=44:55:66:77:88:99 ip4=192.168.0.1 dns4=192.168.0.3 bridge_type=none
```

Documentation of options
------------------------
```
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
  destructive:
    description:
      - If the module should try and remove all the files in /etc/systemd/network before running, thus
        making sure that the module setups the network files from scratch
    required: false
    default: false
```
