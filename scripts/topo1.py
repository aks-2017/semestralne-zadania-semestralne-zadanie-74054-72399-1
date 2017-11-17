#!/usr/bin/python

#run me like one of your french girl:  sudo -E python topo1.py

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
      
	net.addLink(s0,h0)
	net.addLink(s0,h1)
	net.addLink(s0,h2)
	
	net.addLink(s1,h3)
	net.addLink(s1,h4)
	
	net.addLink(s2,h5)
	net.addLink(s2,h6)
	net.addLink(s2,h7)
	
	net.addLink(s3,h8)
	net.addLink(s3,h9)
	
	net.addLink(s0,s1)
	net.addLink(s1,s2)
	net.addLink(s2,s3)
	net.addLink(s3,s0)
	
	c0 = net.addController("c0")
	net.start()  
	
	for x in range(0,4):
		cmd = "ovs-vsctl set bridge s%d rstp_enable=true" % (x)
		c0.cmd(cmd)
	
	CLI(net)
	net.stop
    
    
