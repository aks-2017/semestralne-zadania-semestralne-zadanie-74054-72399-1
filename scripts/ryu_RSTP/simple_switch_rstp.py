import struct
import datetime

from ryu.base import app_manager
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import dpid as dpid_lib
from ryu.lib import rstplib
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types

from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.lib.mac import haddr_to_str


class SimpleSwitchRstp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'rstplib': rstplib.Rstp}

    ### Tempo di rimozione di un elemento dalla flow table 0
    _DEFAULT_TIME_EXP = 500

    def __init__(self, *args, **kwargs):
        super(SimpleSwitchRstp, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.rstp = kwargs['rstplib']

        config = {
                    dpid_lib.str_to_dpid('0000000000000001'):{'bridge': {'priority': 0xB000,'hello_time': 1}},
                    dpid_lib.str_to_dpid('0000000000000002'):{'bridge': {'priority': 0xC000,'hello_time': 1}},
                    dpid_lib.str_to_dpid('0000000000000003'):{'bridge': {'priority': 0xA000,'hello_time': 1}},
                    dpid_lib.str_to_dpid('0000000000000004'):{'bridge': {'priority': 0xE000,'hello_time': 1}},
                    dpid_lib.str_to_dpid('0000000000000005'):{'bridge': {'priority': 0xD000,'hello_time': 1}}
                }
        self.rstp.set_config(config)

        self.start_time = datetime.datetime.now()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser


        match = parser.OFPMatch()

        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, match=match, table_id=1,
            command=ofproto.OFPFC_DELETE,out_port=ofproto.OFPP_ANY,out_group=ofproto.OFPG_ANY)
        datapath.send_msg(mod)

        
        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, match=match, table_id=0,
            command=ofproto.OFPFC_DELETE,out_port=ofproto.OFPP_ANY,out_group=ofproto.OFPG_ANY)
        datapath.send_msg(mod)


        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.add_flow(datapath, 0, match, actions, table_id=1)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, table_id=0, inst=None,idle_timeout=0):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        if not inst:
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, table_id=table_id, idle_timeout=idle_timeout)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst, table_id=table_id,idle_timeout=idle_timeout)

        datapath.send_msg(mod)

    def flush_mac(self, datapath):
        ofproto = datapath.ofproto
        match = datapath.ofproto_parser.OFPMatch()
        mod = datapath.ofproto_parser.OFPFlowMod(
            datapath=datapath, match=match, table_id=1,
            command=ofproto.OFPFC_DELETE,out_port=ofproto.OFPP_ANY,out_group=ofproto.OFPG_ANY)
        datapath.send_msg(mod)

        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions, table_id=1)

    @set_ev_cls(rstplib.EventPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        if ev.msg.msg_len < ev.msg.total_len:
            self.logger.debug("packet truncated: only %s of %s bytes",
                              ev.msg.msg_len, ev.msg.total_len)
        msg = ev.msg
        bridge = ev.bridge
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]


        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            # ignore lldp packet
            return

        dst = eth.dst
        src = eth.src

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)

        # learn a mac address to avoid FLOOD next time.
        self.mac_to_port[dpid][src] = in_port

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

            match = datapath.ofproto_parser.OFPMatch(eth_dst=dst, eth_src = src)
            actions = []
            inst = [parser.OFPInstructionGotoTable(table_id=1)]
            self.add_flow(datapath, ofproto.OFP_DEFAULT_PRIORITY, match, actions, inst=inst,idle_timeout=self._DEFAULT_TIME_EXP)

            match = datapath.ofproto_parser.OFPMatch(eth_dst=dst,eth_src = src)
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, ofproto.OFP_DEFAULT_PRIORITY, match, actions, table_id=1)

            actions = [parser.OFPActionOutput(out_port)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id, in_port=in_port, actions=actions, data=data)
            datapath.send_msg(out)
        else:
            for port in bridge.ports:
                if (bridge.ports[port].state != rstplib.PORT_STATE_DISCARDING) and (bridge.ports[port].ofport.port_no != in_port):
                    out_port = bridge.ports[port].ofport.port_no
                    actions = [parser.OFPActionOutput(out_port)]
                    out = parser.OFPPacketOut(datapath=datapath, in_port=in_port, actions=actions, buffer_id=msg.buffer_id, data=data)

                    bridge.dp.send_msg(out)

    @set_ev_cls(rstplib.EventTopologyChange, MAIN_DISPATCHER)
    def _topology_change_handler(self, ev):
        dp = ev.dp
        dpid_str = dpid_lib.dpid_to_str(dp.id)
        msg = 'Receive topology change event. Flush MAC table.'
        #self.logger.info("[time="+str((datetime.datetime.now()-self.start_time).seconds)+" secs]"
        #    +"[dpid="+str(dpid_str)+"] "+msg)

        if dp.id in self.mac_to_port:
            del self.mac_to_port[dp.id]
        self.flush_mac(dp)

    @set_ev_cls(rstplib.EventPortStateChange, MAIN_DISPATCHER)
    def _port_state_change_handler(self, ev):
        dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
        of_state = {rstplib.PORT_STATE_DISCARDING: 'DISCARDING',
                    rstplib.PORT_STATE_LEARNING: 'LEARNING',
                    rstplib.PORT_STATE_FORWARDING: 'FORWARDING'}
        self.logger.info("[time="+str((datetime.datetime.now()-self.start_time).seconds)+" secs]"
            +"[dpid="+str(dpid_str)+"][port="+str(ev.port_no)+"] state="+of_state[ev.port_state])

    @set_ev_cls(rstplib.EventPortRoleChange, MAIN_DISPATCHER)
    def _port_role_change_handler(self, ev):
        dpid_str = dpid_lib.dpid_to_str(ev.dp.id)
        of_role = {rstplib.PORT_ROLE_ALTERNATE: 'ALTERNATE',
                    rstplib.PORT_ROLE_ROOT: 'ROOT',
                    rstplib.PORT_ROLE_DESIGNATED: 'DESIGNATED',
                    rstplib.PORT_ROLE_BACKUP: 'BACKUP'}
        self.logger.info("[time="+str((datetime.datetime.now()-self.start_time).seconds)+" secs]"+
            "[dpid="+str(dpid_str)+"][port="+str(ev.port_no)+"] state="+of_role[ev.port_role])