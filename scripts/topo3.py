#!/usr/bin/python

#run me like one of your french girl:  sudo -E python topo2.py

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
      
	s0 = net.addSwitch("s0",dpid="0000000000000001")    
	s1 = net.addSwitch("s1",dpid="0000000000000002")    
	s2 = net.addSwitch("s2",dpid="0000000000000003") 
	s3 = net.addSwitch("s3",dpid="0000000000000004") 
	s4 = net.addSwitch("s4",dpid="0000000000000005") 
	s5 = net.addSwitch("s5",dpid="0000000000000006") 
	s6 = net.addSwitch("s6",dpid="0000000000000007") 
	s7 = net.addSwitch("s7",dpid="0000000000000008") 
	s8 = net.addSwitch("s8",dpid="0000000000000009") 
	s9 = net.addSwitch("s9",dpid="0000000000000010") 
	s10 = net.addSwitch("s10",dpid="0000000000000011") 
	s11 = net.addSwitch("s11",dpid="0000000000000012") 
      
	net.addLink(s1,h0)
	net.addLink(s3,h1)
	net.addLink(s3,h2)
	net.addLink(s4,h3)
	net.addLink(s6,h4)
	net.addLink(s7,h5)
	net.addLink(s8,h6)
	net.addLink(s9,h7)
	net.addLink(s10,h8)
	net.addLink(s10,h9)
	
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
	
	CLI(net)
	net.stop
