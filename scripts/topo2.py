from mininet.topo import Topo

class Test1Topo( Topo ):

    def __init__( self ):
        "Create custom topo."

        # Initialize topology
        Topo.__init__( self )


        # Add hosts and switches
	h0 = self.addHost('h0', mac='00:00:00:00:00:01', ip='10.0.0.1/24')
	h1 = self.addHost('h1', mac='00:00:00:00:00:02', ip='10.0.0.2/24')
    	h2 = self.addHost('h2', mac='00:00:00:00:00:03', ip='10.0.0.3/24')
    	h3 = self.addHost('h3', mac='00:00:00:00:00:04', ip='10.0.0.4/24')
    	h4 = self.addHost('h4', mac='00:00:00:00:00:05', ip='10.0.0.5/24')
    	h5 = self.addHost('h5', mac='00:00:00:00:00:06', ip='10.0.0.6/24')
    	h6 = self.addHost('h6', mac='00:00:00:00:00:07', ip='10.0.0.7/24')
    	h7 = self.addHost('h7', mac='00:00:00:00:00:08', ip='10.0.0.8/24')
    	h8 = self.addHost('h8', mac='00:00:00:00:00:09', ip='10.0.0.9/24')
    	h9 = self.addHost('h9', mac='00:00:00:00:00:10', ip='10.0.0.10/24')
	
    	s0 = self.addSwitch('s0')
    	s1 = self.addSwitch('s1')
    	s2 = self.addSwitch('s2')
    	s3 = self.addSwitch('s3')
	s4 = self.addSwitch('s4')
    	s5 = self.addSwitch('s5')
    	s6 = self.addSwitch('s6')
    	s7 = self.addSwitch('s7')

        # Add links
        self.addLink(s0, h0)
    	self.addLink(s1, h1)
    	self.addLink(s2, h2)
    	self.addLink(s3, h3)
    	self.addLink(s4, h4)
    	self.addLink(s5, h5)
    	self.addLink(s6, h6)
    	self.addLink(s6, h7)
    	self.addLink(s7, h8)
    	self.addLink(s7, h9)
	
    	self.addLink(s0, s1)
    	self.addLink(s1, s2)
    	self.addLink(s2, s3)
    	self.addLink(s3, s4)
	self.addLink(s4, s5)
	self.addLink(s5, s6)
	self.addLink(s6, s7)
	self.addLink(s7, s0)

topos = { 'mytopo': ( lambda: Test1Topo() ) }