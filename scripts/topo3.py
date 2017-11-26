#!/usr/bin/python

#run me like one of your french girl:  sudo -E python topo2.py
#ryu-manager simple_switch_igmp_13.py
#vypnutie int ip link set dev sxx-ethx down

from mininet.cli import CLI
from mininet.net import Mininet
from mininet.node import RemoteController

if "__main__" == __name__:
     
	net = Mininet(controller=RemoteController)     
 
	h0 = net.addHost("h0", mac="00:00:00:00:00:01", ip="10.0.0.1/24")
	h1 = net.addHost("h1", mac="00:00:00:00:00:02", ip="10.0.0.2/24")
	h2 = net.addHost("h2", mac="00:00:00:00:00:03", ip="10.0.0.3/24")
	h3 = net.addHost("h3", mac="00:00:00:00:00:04", ip="10.0.0.4/24")
	h4 = net.addHost("h4", mac="00:00:00:00:00:05", ip="10.0.0.5/24")
	h5 = net.addHost("h5", mac="00:00:00:00:00:06", ip="10.0.0.6/24")
	h6 = net.addHost("h6", mac="00:00:00:00:00:07", ip="10.0.0.7/24")
	h7 = net.addHost("h7", mac="00:00:00:00:00:08", ip="10.0.0.8/24")
	h8 = net.addHost("h8", mac="00:00:00:00:00:09", ip="10.0.0.9/24")
	h9 = net.addHost("h9", mac="00:00:00:00:00:10", ip="10.0.0.10/24")
      
	s0 = net.addSwitch("s0",dpid="0000000000000002",protocols="OpenFlow13")    
	s1 = net.addSwitch("s1",dpid="0000000000000001",protocols="OpenFlow13")    
	s2 = net.addSwitch("s2",dpid="0000000000000003",protocols="OpenFlow13") 
	s3 = net.addSwitch("s3",dpid="0000000000000004",protocols="OpenFlow13") 
	s4 = net.addSwitch("s4",dpid="0000000000000005",protocols="OpenFlow13") 
	s5 = net.addSwitch("s5",dpid="0000000000000006",protocols="OpenFlow13") 
	s6 = net.addSwitch("s6",dpid="0000000000000007",protocols="OpenFlow13") 
	s7 = net.addSwitch("s7",dpid="0000000000000008",protocols="OpenFlow13") 
	s8 = net.addSwitch("s8",dpid="0000000000000009",protocols="OpenFlow13") 
	s9 = net.addSwitch("s9",dpid="0000000000000010",protocols="OpenFlow13") 
	s10 = net.addSwitch("s10",dpid="0000000000000011",protocols="OpenFlow13") 
	s11 = net.addSwitch("s11",dpid="0000000000000012",protocols="OpenFlow13") 
      
	net.addLink(s1,h0,2)
	net.addLink(s2,h1)
	net.addLink(s3,h2)
	net.addLink(s4,h3)
	net.addLink(s6,h4)
	net.addLink(s7,h5)
	net.addLink(s8,h6)
	net.addLink(s9,h7)
	net.addLink(s10,h8)
	net.addLink(s11,h9)
	
	net.addLink(s0,s1)
	net.addLink(s1,s2)
	net.addLink(s2,s3)
	net.addLink(s3,s4)
	net.addLink(s4,s5)
	net.addLink(s5,s6)
	net.addLink(s6,s7)
	net.addLink(s7,s8)
	net.addLink(s8,s9)
	net.addLink(s9,s10)
	net.addLink(s10,s11)
	net.addLink(s11,s0)
	
	c0 = net.addController("c0")
	net.start()  
	
	for x in range(0,12):
		cmd = "ovs-vsctl set bridge s%d rstp_enable=true" % (x)
		c0.cmd(cmd)
	
	#1. multicast group h0+h1 - 225.0.0.1
	h0 = net.get('h0')
	cmd="ip route add 225.0.0.1 dev h0-eth0"
	h0.cmd(cmd)
	h1 = net.get('h1')
	cmd="ip route add 225.0.0.1 dev h1-eth0"
	h1.cmd(cmd)
	#2. multicast group h2+h3 - 225.0.0.2
	h2 = net.get('h2')
	cmd="ip route add 225.0.0.2 dev h2-eth0"
	h2.cmd(cmd)
	h3 = net.get('h3')
	cmd="ip route add 225.0.0.2 dev h3-eth0"
	h3.cmd(cmd)
	#3. multicast group h4+h5 - 225.0.0.3
	h4 = net.get('h4')
	cmd="ip route add 225.0.0.3 dev h4-eth0"
	h4.cmd(cmd)
	h5 = net.get('h5')
	cmd="ip route add 225.0.0.3 dev h5-eth0"
	h5.cmd(cmd)
	#4. multicast group h6+h7 - 225.0.0.4
	h6 = net.get('h6')
	cmd="ip route add 225.0.0.4 dev h6-eth0"
	h6.cmd(cmd)
	h7 = net.get('h7')
	cmd="ip route add 225.0.0.4 dev h7-eth0"
	h7.cmd(cmd)
	#5. multicast group h8+h9 - 225.0.0.5
	h8 = net.get('h8')
	cmd="ip route add 225.0.0.5 dev h8-eth0"
	h8.cmd(cmd)
	h9 = net.get('h9')
	cmd="ip route add 225.0.0.5 dev h9-eth0"
	h9.cmd(cmd)
	
	CLI(net)
	net.stop
