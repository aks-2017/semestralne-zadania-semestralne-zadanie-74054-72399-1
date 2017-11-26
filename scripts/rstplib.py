import time
import logging
import threading
import copy

from ryu.base import app_manager
from ryu.controller import event
from ryu.controller import handler
from ryu.controller import ofp_event
from ryu.controller.handler import set_ev_cls
from ryu.exception import RyuException
from ryu.exception import OFPUnknownVersion
from ryu.lib import hub
from ryu.lib.dpid import dpid_to_str
from ryu.lib.packet import bpdu
from ryu.lib.packet import ethernet
from ryu.lib.packet import llc
from ryu.lib.packet import packet
from ryu.ofproto import ofproto_v1_0
from ryu.ofproto import ofproto_v1_2
from ryu.ofproto import ofproto_v1_3

# Risultati possibili di comparazione
SUPERIOR = -1
REPEATED = 0
INFERIOR = 1

MAX_PORT_NO = 0xfff

### Tipi di BPDU disponibili
STP_BPDU_TCN = -1
RSTP_BPDU = 0
STP_BPDU = 1


### Ruoli delle porte
PORT_ROLE_DESIGNATED = 0
PORT_ROLE_ROOT = 1
PORT_ROLE_BACKUP = 2
PORT_ROLE_ALTERNATE = 3
PORT_ROLE_DISABLED = 4

### Stati delle porte ###
PORT_STATE_DISCARDING = 0
PORT_STATE_LEARNING = 1
PORT_STATE_FORWARDING = 2


### Parametri massimi e minimi di HELLO:
HELLO_MAX = 2.0
HELLO_MIN = 1.0

### Priorita' per i packetin
BPDU_PKT_IN_PRIORITY = 0xffff
NO_PKT_IN_PRIORITY = 0xfffe

### Multiplo di hello time per la scadenza del timer di topology change
MAX_TC_TMR_MLT = 3 


# Configurazione per OpenFlow 1.2
PORT_CONFIG_V1_2 = {PORT_STATE_DISCARDING: ofproto_v1_2.OFPPC_NO_PACKET_IN,
                    PORT_STATE_LEARNING: ofproto_v1_2.OFPPC_NO_PACKET_IN,
                    PORT_STATE_FORWARDING: 0}

# Configurazione per OpenFlow 1.3
PORT_CONFIG_V1_3 = {PORT_STATE_DISCARDING: ofproto_v1_3.OFPPC_NO_PACKET_IN,
                    PORT_STATE_LEARNING: ofproto_v1_3.OFPPC_NO_PACKET_IN,
                    PORT_STATE_FORWARDING: 0}
                    

FLAG_BIT_TC = 0b00000001
FLAG_BIT_PROP = 0b00000010
FLAG_BIT_TCA = 0b10000000
FLAG_BIT_CLR = 0b00000000
FLAG_BIT_ALT_BCK = 0b00000100
FLAG_BIT_ROOT = 0b00001000
FLAG_BIT_DSG = 0b00001100
FLAG_BIT_AGRMNT = 0b01000000
FLAG_BIT_FRWD = 0b00100000
FLAG_BIT_LRNG = 0b00010000


class Rstp(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_0.OFP_VERSION,
                    ofproto_v1_2.OFP_VERSION,
                    ofproto_v1_3.OFP_VERSION]

    def __init__(self):
        super(Rstp, self).__init__()
        self.name = 'rstplib'
        self._set_logger()
        self.config = {}
        self.bridge_list = {}

    def _set_logger(self):
        self.logger.propagate = False
        hdlr = logging.StreamHandler()
        fmt_str = '[RSTP][%(levelname)s] dpid=%(dpid)s: %(message)s'
        hdlr.setFormatter(logging.Formatter(fmt_str))
        self.logger.addHandler(hdlr)
    
    def set_config(self, config):
        assert isinstance(config, dict)
        self.config = config

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [handler.MAIN_DISPATCHER, handler.DEAD_DISPATCHER])
    def dispacher_change(self, ev):
        assert ev.datapath is not None
        if ev.state == handler.MAIN_DISPATCHER:
            self._register_bridge(ev.datapath)
        elif ev.state == handler.DEAD_DISPATCHER:
            self._unregister_bridge(ev.datapath.id)

    def _register_bridge(self, dp):
        self._unregister_bridge(dp.id)
        dpid_str = {'dpid': dpid_to_str(dp.id)}
        self.logger.info('Join as rstp bridge.', extra=dpid_str)
        try:
            bridge = Bridge(dp, self.config.get(dp.id, {}),self.logger, self.send_event_to_observers)
        except OFPUnknownVersion as message:
            self.logger.error(str(message), extra=dpid_str)
            return

        self.bridge_list[dp.id] = bridge

    def _unregister_bridge(self, dp_id):
        if dp_id in self.bridge_list:
            del self.bridge_list[dp_id]
            self.logger.info('Leave rstp bridge.',
                             extra={'dpid': dpid_to_str(dp_id)})

    @set_ev_cls(ofp_event.EventOFPPacketIn, handler.MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        if ev.msg.datapath.id in self.bridge_list:
            bridge = self.bridge_list[ev.msg.datapath.id]
            bridge.packet_in_handler(ev.msg)

    @set_ev_cls(ofp_event.EventOFPPortStatus, handler.MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        dp = ev.msg.datapath
        dpid_str = {'dpid': dpid_to_str(dp.id)}
        port = ev.msg.desc
        reason = ev.msg.reason
        link_down_flg = port.state & 0b1

        if dp.id in self.bridge_list:
            bridge = self.bridge_list[dp.id]

            if reason is dp.ofproto.OFPPR_ADD:
                self.logger.info('[port=%d] Port add.',
                                 port.port_no, extra=dpid_str)
                bridge.port_add(port)
            elif reason is dp.ofproto.OFPPR_DELETE:
                self.logger.info('[port=%d] Port delete.',
                                 port.port_no, extra=dpid_str)
                bridge.port_delete(port.port_no)

    @staticmethod
    def compare_root_path(path_cost1, path_cost2, bridge_id1, bridge_id2,
                          port_id1, port_id2):
        result = Rstp._cmp_value(path_cost1, path_cost2)
        if not result:
            result = Rstp._cmp_value(bridge_id1, bridge_id2)
            if not result:
                result = Rstp._cmp_value(port_id1, port_id2)
        return result

    @staticmethod
    def compare_bpdu_info(my_priority, rcv_priority):
        if my_priority is None:
            result = SUPERIOR
        elif rcv_priority is None:
            result = INFERIOR
        else:
            result = Rstp._cmp_value(rcv_priority.root_id.value,
                                    my_priority.root_id.value)
            if not result:
                result = Rstp.compare_root_path(
                    rcv_priority.root_path_cost,
                    my_priority.root_path_cost,
                    rcv_priority.designated_bridge_id.value,
                    my_priority.designated_bridge_id.value,
                    rcv_priority.designated_port_id.value,
                    my_priority.designated_port_id.value)
                if not result:
                    result1 = Rstp._cmp_value(
                        rcv_priority.designated_bridge_id.value,
                        my_priority.designated_bridge_id.mac_addr)
                    result2 = Rstp._cmp_value(
                        rcv_priority.designated_port_id.value,
                        my_priority.designated_port_id.port_no)
                    if not result1 and not result2:
                        result = SUPERIOR
                    else:
                        result = REPEATED
        return result

    @staticmethod
    def _cmp_value(value1, value2):
        result = cmp(value1, value2)
        if result < 0: #value2>value1
            return SUPERIOR
        elif result == 0: #value2=value1
            return REPEATED
        else: #value1>value2
            return INFERIOR

    @staticmethod
    def _cmp_obj(obj1, obj2):
        for key in obj1.__dict__.keys():
            if (not hasattr(obj2, key)
                    or getattr(obj1, key) != getattr(obj2, key)):
                return SUPERIOR
        return REPEATED

    
class Bridge(object):

    _DEFAULT_VALUE = {'priority': bpdu.DEFAULT_BRIDGE_PRIORITY,
                      'sys_ext_id': 0,
                      'max_age': bpdu.DEFAULT_MAX_AGE,
                      'hello_time': bpdu.DEFAULT_HELLO_TIME,
                      'fwd_delay': bpdu.DEFAULT_FORWARD_DELAY,
                      }

    def __init__(self, dp, config, logger, send_eve_func):

        ### OpenFlow and supporting data ###

        super(Bridge, self).__init__()
        self.logger = logger
        self.dp = dp
        self.dpid_str = {'dpid': dpid_to_str(dp.id)}
        self.send_event = send_eve_func

        # Bridge data
        bridge_conf = config.get('bridge', {})
        values = self._DEFAULT_VALUE
        for key, value in bridge_conf.items():
            values[key] = value
        system_id = list(dp.ports.values())[0].hw_addr

        self.bridge_id = BridgeId(values['priority'],
                                  values['sys_ext_id'],
                                  system_id)
        self.bridge_times = Times(0,  # message_age
                                  values['max_age'],
                                  values['hello_time'],
                                  values['fwd_delay'])
        
        self.bridge_priority = Priority(self.bridge_id,0,self.bridge_id,PortId(0,0))
        self.root_id = self.bridge_id
        self.priority = copy.copy(self.bridge_priority)
        self.reset = False

        # Ports
        self.ports = {}
        self.ports_conf = config.get('ports', {})
        for ofport in dp.ports.values():
            self.port_add(ofport)

        # Install BPDU PacketIn flow. (OpenFlow 1.2/1.3)
        if dp.ofproto == ofproto_v1_2 or dp.ofproto == ofproto_v1_3:
            ofctl = OfCtl_v1_2later(self.dp)
            ofctl.add_bpdu_pkt_in_flow()

        # Thread di trasmissione di BPDU da tutte le porte (che possono farlo) ogni hello time
        self.timers = Timers(self.bridge_times.hello_time,self.bridge_times.hello_time*MAX_TC_TMR_MLT)
        transmission_thread = threading.Thread(target=self.gen_send_bpdu,args=())
        transmission_thread.start()   

        self.alternate_priority = {}




    def detect_edge(self, port):
        try:
            while True and not self.reset and self.ports[port.ofport.port_no]:
                starttime = time.time()
                if port.edge_delay_tmr !=0 and not self.reset:
                    port.edge_delay_tmr = port.edge_delay_tmr-1
                elif not self.reset:
                    if port.role != PORT_ROLE_ROOT:
                        if port.state != PORT_STATE_FORWARDING:
                            port.edge = True
                            self.set_port_state_role(port,PORT_STATE_FORWARDING,PORT_ROLE_DESIGNATED)
                    else:                    
                        reset = True
                        for port_i in self.ports:
                            if self.ports[port_i].role is PORT_ROLE_ALTERNATE:
                                self.set_port_state_role(self.ports[port_i],PORT_STATE_FORWARDING,PORT_ROLE_ROOT)
                                self.priority = copy.copy(self.alternate_priority[port_i])
                                new_prio = copy.copy(self.alternate_priority[port_i])
                                new_prio.designated_bridge_id = self.bridge_id
                                for port_i_two in self.ports:
                                    if (self.ports[port_i_two].role is PORT_ROLE_ROOT) and (self.ports[port_i_two].ofport.port_no != self.ports[port_i].ofport.port_no):
                                        self.set_port_state_role(self.ports[port_i_two],PORT_STATE_DISCARDING,PORT_ROLE_DESIGNATED)
                                    new_prio.designated_port_id = self.ports[port_i_two].port_id 
                                    self.ports[port_i_two].priority = copy.copy(new_prio)
                                reset=False
                                break
                        if reset:
                            self.resetting_bridge()
                            break
                else:
                    break
                if not self.reset:
                    t_end = time.time() + 1#
                    while (time.time() < t_end) and not (self.reset):#
                        time.sleep(0.01)#
                    #time.sleep(1 - (time.time() - starttime))
                else:
                    break
        except:
            pass


    def resetting_bridge(self):

        self.reset = True
        self.root_id = self.bridge_id
        self.priority = copy.copy(self.bridge_priority)



        time.sleep(0.1)#
        #time.sleep(1)

        self.reset = False

        self.alternate_priority = {}

        for port in self.ports:
            self.ports[port].reset()

        for port in self.ports:
            self.start_edge_threads(self.ports[port])

        transmission_thread = threading.Thread(target=self.gen_send_bpdu,args=())
        transmission_thread.start()   


    def gen_send_bpdu(self):
        while True and not self.reset:
            starttime = time.time()
            if self.timers.hello_tmr !=0:
                self.timers.hello_tmr = self.timers.hello_tmr-1
            else:
                for port in self.ports:
                    if (self.ports[port].role is PORT_ROLE_DESIGNATED) or (self.ports[port].topo_change):
                        pkt = self.ports[port].generate_bpdu()
                        self.ports[port].tx_bpdu(pkt)
                self.timers.hello_tmr = self.bridge_times.hello_time           
            time.sleep(1 - (time.time() - starttime))
        
    def port_add(self, ofport):
        if ofport.port_no <= MAX_PORT_NO:
            port_conf = self.ports_conf.get(ofport.port_no, {})
            port = Port(self.dp, port_conf, self.bridge_id, self.bridge_times, ofport, self.logger, self.send_event)
            self.ports[ofport.port_no] = port
            self.start_edge_threads(port)           

    def start_edge_threads(self, port):        
        edge_thread = threading.Thread(target=self.detect_edge,args=(port,))
        edge_thread.start()

    def port_delete(self, port_no):

        if self.ports[port_no].role is PORT_ROLE_ROOT:
            reset = True
            for port_i in self.ports:
                if self.ports[port_i].role is PORT_ROLE_ALTERNATE:
                    self.set_port_state_role(self.ports[port_i],PORT_STATE_FORWARDING,PORT_ROLE_ROOT)
                    self.priority = copy.copy(self.alternate_priority[port_i])
                    new_prio = copy.copy(self.alternate_priority[port_i])
                    new_prio.designated_bridge_id = self.bridge_id
                    reset=False
                        
            if reset:
                del self.ports[port_no]
                self.resetting_bridge()
            else:
                del self.ports[port_no]
        else:
            del self.ports[port_no]

    def packet_in_handler(self, msg):
        if not self.reset:
            dp = msg.datapath
            if dp.ofproto == ofproto_v1_0:
                in_port_no = msg.in_port
            else:
                assert dp.ofproto == ofproto_v1_2 or dp.ofproto == ofproto_v1_3
                in_port_no = None
                for match_field in msg.match.fields:
                    if match_field.header == dp.ofproto.OXM_OF_IN_PORT:
                        in_port_no = match_field.value
                        break
            if in_port_no not in self.ports:
                return

            in_port = self.ports[in_port_no]

            pkt = packet.Packet(msg.data)
            if bpdu.ConfigurationBPDUs in pkt:
                self.logger.info('STP BPDU - '+str(self.dpid_str))
                #### TODO ######################################################################################################################################

            elif bpdu.TopologyChangeNotificationBPDUs in pkt:
                self.logger.info('Topology Change Notification BPDU STP' ,)
                #### TODO ######################################################################################################################################
        
            elif bpdu.RstBPDUs in pkt:          
                (bpdu_pkt, ) = pkt.get_protocols(bpdu.RstBPDUs)
                self.handle_rstp_bpdu(bpdu_pkt,in_port)            
        
            else:
                self.send_event(EventPacketIn(msg,copy.copy(self)))
    
    def handle_rstp_bpdu(self,bpdu,in_port):

        is_prop = FLAG_BIT_PROP & bpdu.flags
        is_agrmnt = FLAG_BIT_AGRMNT & bpdu.flags
        is_tc = FLAG_BIT_TC & bpdu.flags
        is_alt_bck = FLAG_BIT_ALT_BCK & bpdu.flags

        # Se arriva una bpdu ed e' una porta edge -> non lo e' piu' e parte il timer
        # alla cui scadenza torna una porta edge 
        if in_port.edge:
            in_port.edge = False
        

        # Ricevo i dati dalla BPDU
        msg_priority, msg_times = self.rcv_info_bpdu(bpdu)
        msg_prio_no_lc = copy.copy(msg_priority)
        msg_priority.root_path_cost = msg_priority.root_path_cost+in_port.path_cost

        my_priority = copy.copy(self.priority)
        #my_priority.designated_port_id = in_port.port_id

        rcv_info = Rstp.compare_bpdu_info(my_priority, msg_priority)
        rcv_info_two = Rstp.compare_bpdu_info(in_port.priority, msg_prio_no_lc)

        if not(rcv_info_two is INFERIOR and rcv_info is INFERIOR and is_alt_bck):
            in_port.reset_edge_delay_tmr()

        if is_tc:
            self.set_topology_change()

        ### Se e' un agreement: ###
        if is_agrmnt:
            self.handle_agreement(msg_priority,in_port)
        else:
            if in_port.role != PORT_ROLE_ROOT:
                if rcv_info is INFERIOR:

                    if msg_priority.designated_bridge_id.value == self.bridge_id.value:
                        if rcv_info_two is SUPERIOR:
                            self.set_port_state_role(in_port,PORT_STATE_DISCARDING,PORT_ROLE_BACKUP)
                        else:
                            if (not in_port.already_transitioning) and (in_port.state != PORT_STATE_FORWARDING and in_port.state != PORT_STATE_LEARNING):
                                self.start_learning_forwarding_thread(in_port)
                    else:    
                        if rcv_info_two is SUPERIOR and in_port.role != PORT_ROLE_BACKUP:  
                            self.set_port_state_role(in_port,PORT_STATE_DISCARDING,PORT_ROLE_ALTERNATE)
                            self.alternate_priority[in_port.ofport.port_no] = copy.copy(msg_priority)
                            self.handle_proposal(in_port=in_port, rcv_info=rcv_info)
                        elif rcv_info_two is INFERIOR and in_port.role != PORT_ROLE_BACKUP:
                            if (not in_port.already_transitioning) and (in_port.state != PORT_STATE_FORWARDING and in_port.state != PORT_STATE_LEARNING):
                                self.start_learning_forwarding_thread(in_port)
                elif rcv_info is SUPERIOR:
                    self.priority = copy.copy(msg_priority)
                    if is_prop:
                        self.handle_proposal(in_port=in_port,rcv_info=rcv_info,bpdu=bpdu)
                    msg_priority.designated_bridge_id = self.bridge_id
                    for port in self.ports:
                        msg_priority.designated_port_id = self.ports[port].port_id 
                        self.ports[port].priority = copy.copy(msg_priority)
                        self.ports[port].set_prio_times(msg_times)     
                    self.root_id = msg_priority.root_id
                    if not is_prop:
                        for port in self.ports:
                            if (self.ports[port] != in_port) and not (self.ports[port].edge) and not (self.ports[port].state is PORT_STATE_DISCARDING):  
                                self.set_port_state_role(self.ports[port],PORT_STATE_DISCARDING,PORT_ROLE_DESIGNATED)
                        self.set_port_state_role(in_port,PORT_STATE_FORWARDING,PORT_ROLE_ROOT)
            else:
                rcv_info_three = Rstp.compare_bpdu_info(self.bridge_priority, msg_priority)
                if rcv_info_three is INFERIOR:
                    self.resetting_bridge()
                else:
                    self.priority = copy.copy(msg_priority)
                    if is_prop:
                        self.handle_proposal(in_port=in_port,rcv_info=rcv_info,bpdu=bpdu)
                    msg_priority.designated_bridge_id = self.bridge_id
                    for port in self.ports:
                        msg_priority.designated_port_id = self.ports[port].port_id 
                        self.ports[port].priority = copy.copy(msg_priority)                    
                        self.ports[port].set_prio_times(msg_times)       
                    self.root_id = msg_priority.root_id
                    if not is_prop and not (rcv_info is REPEATED):
                        for port in self.ports:
                            if (self.ports[port] != in_port) and not (self.ports[port].edge) and not (self.ports[port].state is PORT_STATE_DISCARDING):
                                self.set_port_state_role(self.ports[port],PORT_STATE_DISCARDING,PORT_ROLE_DESIGNATED)
                
    def set_port_state_role(self,port,state,role):
        if (port.state != PORT_STATE_FORWARDING and (not port.edge) and (state is PORT_STATE_FORWARDING)):
            self.set_topology_change()
        port.change_status(state)
        port.change_role(role)  

    def start_learning_forwarding_thread(self,in_port):
        transition_thread = threading.Thread(target=in_port.learning_forwarding_transition,args=())
        transition_thread.start()        

    # Gestisce il caso in cui si riceva una proposal
    def handle_proposal(self, in_port, rcv_info, bpdu = None):
        if rcv_info is INFERIOR:
            #if ((in_port.state is PORT_STATE_LEARNING) or (in_port.state is PORT_STATE_DISCARDING)) and (in_port.role is PORT_ROLE_DESIGNATED):
            new_bpdu = in_port.generate_bpdu()
            in_port.tx_bpdu(new_bpdu)
        elif rcv_info is SUPERIOR:
            self.synch_process(in_port,bpdu)

    # Gestisce il caso in cui si riceva un agreement 
    def handle_agreement(self, msg_priority, in_port):
        if (self.bridge_id == msg_priority.designated_bridge_id 
            and self.root_id == msg_priority.root_id
            and in_port.ofport.port_no == msg_priority.designated_port_id.port_no):
            port_prop = self.ports[msg_priority.designated_port_id.port_no]
            self.set_port_state_role(port_prop,PORT_STATE_FORWARDING,PORT_ROLE_DESIGNATED)
            self.set_topology_change()
    
    # Metodo che ritorna i dati salvati nella BPDU
    def rcv_info_bpdu(self,bpdu):
        root_id = BridgeId(bpdu.root_priority,
                           bpdu.root_system_id_extension,
                           bpdu.root_mac_address)
        root_path_cost = bpdu.root_path_cost
        designated_bridge_id = BridgeId(bpdu.bridge_priority,
                                        bpdu.bridge_system_id_extension,
                                        bpdu.bridge_mac_address)
        designated_port_id = PortId(bpdu.port_priority,
                                    bpdu.port_number)

        msg_priority = Priority(root_id, root_path_cost,
                                designated_bridge_id,
                                designated_port_id)
        msg_times = Times(bpdu.message_age,
                          bpdu.max_age,
                          bpdu.hello_time,
                          bpdu.forward_delay)
        return msg_priority, msg_times


    def synch_process(self,port_ex,bpdu):
        port_ex.last_prop_bpdu = bpdu
        for port in self.ports:
            if (self.ports[port] != port_ex) and not (self.ports[port].edge) and not (self.ports[port].state is PORT_STATE_DISCARDING):
                self.set_port_state_role(self.ports[port],PORT_STATE_DISCARDING,PORT_ROLE_DESIGNATED)
        self.send_agreement(port_ex)
        self.set_port_state_role(port_ex,PORT_STATE_FORWARDING,PORT_ROLE_ROOT)
        self.set_topology_change()

    def send_agreement(self,port):
        bpdu = port.generate_bpdu(agreement=True)
        port.tx_bpdu(bpdu)

    def set_topology_change(self):
        for port in self.ports:
            self.ports[port].topo_change = True        
        self.send_event(EventTopologyChange(self.dp))
        tc_thread = threading.Thread(target=self.tc_countdown,args=())
        tc_thread.start()

    def tc_countdown(self):
        while self.timers.topo_change_tmr !=0:
            starttime = time.time()
            self.timers.topo_change_tmr = self.timers.topo_change_tmr-1
            time.sleep(1 - (time.time() - starttime))
        self.timers.topo_change_tmr = self.bridge_times.hello_time*MAX_TC_TMR_MLT
        for port in self.ports:
            self.ports[port].topo_change = False


class Port(object):

    _DEFAULT_VALUE = {'priority': bpdu.DEFAULT_PORT_PRIORITY,
                      'path_cost': bpdu.PORT_PATH_COST_10MB,
                      'admin_edge': False}

    def __init__(self, dp, config, 
                 bridge_id, bridge_times, ofport,
                 logger,send_eve_func):
        super(Port, self).__init__()
        self.logger = logger
        ### OpenFlow and supporting data ###
        self.dp = dp
        self.dpid_str = {'dpid': dpid_to_str(dp.id)}
        self.ofctl = (OfCtl_v1_0(dp) if dp.ofproto == ofproto_v1_0
                      else OfCtl_v1_2later(dp))

        self.ofport = ofport

        self.send_event = send_eve_func

        ### RSTP data ###

        values = self._DEFAULT_VALUE
        path_costs = {dp.ofproto.OFPPF_10MB_HD: bpdu.PORT_PATH_COST_10MB,
                      dp.ofproto.OFPPF_10MB_FD: bpdu.PORT_PATH_COST_10MB,
                      dp.ofproto.OFPPF_100MB_HD: bpdu.PORT_PATH_COST_100MB,
                      dp.ofproto.OFPPF_100MB_FD: bpdu.PORT_PATH_COST_100MB,
                      dp.ofproto.OFPPF_1GB_HD: bpdu.PORT_PATH_COST_1GB,
                      dp.ofproto.OFPPF_1GB_FD: bpdu.PORT_PATH_COST_1GB,
                      dp.ofproto.OFPPF_10GB_FD: bpdu.PORT_PATH_COST_10GB}
        for rate in sorted(path_costs.keys(), reverse=True):
            if ofport.curr & rate:
                values['path_cost'] = path_costs[rate]
                break
        for key, value in values.items():
            values[key] = value

        self.path_cost = values['path_cost']
        self.port_id = PortId(values['priority'], ofport.port_no)
        
        self.role = None
        self.state = None

        self.change_role(PORT_ROLE_DESIGNATED)
        self.change_status(PORT_STATE_DISCARDING)

        self.proposing = True

        self.bridge_id = bridge_id
        self.bridge_times = copy.copy(bridge_times)

        self.admin_edge = config.get('admin_edge', self._DEFAULT_VALUE['admin_edge'])
        self.edge = self.admin_edge

        self.priority = Priority(bridge_id, 0, bridge_id, self.port_id)

        if self.edge:
            self.state = self.change_status(PORT_STATE_FORWARDING)

        self.migrate_time = bridge_times.hello_time*3
        self.prio_times = copy.copy(bridge_times)

        self.topo_change = False 
        self.fwd_delay_tmr = self.bridge_times.forward_delay        
        self.edge_delay_tmr = self.migrate_time
        self.last_prop_bpdu = None ## Ultimo bpdu di proposal ricevuto
        
        self.already_transitioning = False
        self.stop_transition = False

    def reset(self):

        dp = self.dp
        values = self._DEFAULT_VALUE
        path_costs = {dp.ofproto.OFPPF_10MB_HD: bpdu.PORT_PATH_COST_10MB,
                      dp.ofproto.OFPPF_10MB_FD: bpdu.PORT_PATH_COST_10MB,
                      dp.ofproto.OFPPF_100MB_HD: bpdu.PORT_PATH_COST_100MB,
                      dp.ofproto.OFPPF_100MB_FD: bpdu.PORT_PATH_COST_100MB,
                      dp.ofproto.OFPPF_1GB_HD: bpdu.PORT_PATH_COST_1GB,
                      dp.ofproto.OFPPF_1GB_FD: bpdu.PORT_PATH_COST_1GB,
                      dp.ofproto.OFPPF_10GB_FD: bpdu.PORT_PATH_COST_10GB}

        for rate in sorted(path_costs.keys(), reverse=True):
            if self.ofport.curr & rate:
                values['path_cost'] = path_costs[rate]
                break
        for key, value in values.items():
            values[key] = value

        self.path_cost = values['path_cost']
        self.port_id = PortId(values['priority'], self.ofport.port_no)
        
        self.role = None
        self.state = None

        self.change_role(PORT_ROLE_DESIGNATED)
        self.change_status(PORT_STATE_DISCARDING)

        self.proposing = True

        self.edge = False

        self.priority = Priority(self.bridge_id, 0, self.bridge_id, self.port_id)

        self.migrate_time = self.bridge_times.hello_time*3
        self.prio_times = copy.copy(self.bridge_times)

        self.topo_change = False 
        self.fwd_delay_tmr = self.bridge_times.forward_delay        
        self.edge_delay_tmr = self.migrate_time
        self.last_prop_bpdu = None ## Ultimo bpdu di proposal ricevuto
        
        self.already_transitioning = False
        self.stop_transition = False

    def set_prio_times(self,times):
        self.prio_times = copy.copy(times)
        self.migrate_time = self.prio_times.hello_time*3


    def learning_forwarding_transition(self):
        self.already_transitioning = True
        self.stop_transition = False
        while self.fwd_delay_tmr != 0 and not self.stop_transition:
            
            starttime = time.time()
            self.fwd_delay_tmr = self.fwd_delay_tmr-1      
            time.sleep(1 - (time.time() - starttime))
        
        if self.fwd_delay_tmr == 0 and not self.stop_transition:
            
            self.state = PORT_STATE_LEARNING
            self.proposing = True
            self.ofctl.set_port_status(self.ofport, self.state)
            self.send_event(EventPortStateChange(self.dp, self))
            self.fwd_delay_tmr = self.bridge_times.forward_delay
            
            while self.fwd_delay_tmr != 0 and not self.stop_transition:
                starttime = time.time()
                self.fwd_delay_tmr = self.fwd_delay_tmr-1      
                time.sleep(1 - (time.time() - starttime))
            if self.fwd_delay_tmr == 0 and not self.stop_transition:
                self.state = PORT_STATE_FORWARDING
                self.proposing = False
                self.ofctl.set_port_status(self.ofport, self.state)
                self.send_event(EventPortStateChange(self.dp, self))
        
        self.fwd_delay_tmr = self.bridge_times.forward_delay
        self.already_transitioning = False

    def reset_edge_delay_tmr(self):
        self.edge_delay_tmr = self.migrate_time

    


    ### prop indica se la prossima bpdu sara' di proposing o meno
    ### agreement indica se la prossima bpdu sara' una risposta a un vecchio proposing
    def generate_bpdu(self, agreement = False):
        if agreement:
            b = self.last_prop_bpdu
            new_flags = b.flags | FLAG_BIT_AGRMNT
            b.flags = new_flags
        else:
            flags = FLAG_BIT_CLR

            ## role ##
            if (self.role is PORT_ROLE_ALTERNATE) or (self.role is PORT_ROLE_BACKUP):
                flags = flags | FLAG_BIT_ALT_BCK
            elif self.role is PORT_ROLE_ROOT:
                flags = flags | FLAG_BIT_ROOT
            elif self.role is PORT_ROLE_DESIGNATED:
                flags = flags | FLAG_BIT_DSG

            ## tc ##
            if self.topo_change:
                self.send_event(EventTopologyChange(self.dp))
                flags = flags | FLAG_BIT_TC

            ## Proposal ##
            if self.proposing:
                flags = flags | FLAG_BIT_PROP

            ## Forwarding - Learning ##
            if self.state is PORT_STATE_LEARNING:
                flags = flags | FLAG_BIT_LRNG
            if self.state is PORT_STATE_FORWARDING:
                flags = flags | FLAG_BIT_FRWD

            b = bpdu.RstBPDUs(
                flags = flags, 
                root_priority = self.priority.root_id.priority,
                root_mac_address = self.priority.root_id.mac_addr,
                root_system_id_extension = self.priority.root_id.system_id_extension,
                root_path_cost = self.priority.root_path_cost,           
                bridge_priority = self.bridge_id.priority,
                bridge_mac_address = self.bridge_id.mac_addr,
                bridge_system_id_extension = self.bridge_id.system_id_extension,
                port_priority = self.port_id.priority,
                port_number = self.ofport.port_no,
                message_age = self.bridge_times.message_age,
                max_age = self.bridge_times.max_age,
                hello_time = self.bridge_times.hello_time,
                forward_delay = self.bridge_times.forward_delay)

        src_mac = self.ofport.hw_addr
        dst_mac = bpdu.BRIDGE_GROUP_ADDRESS
        length = (bpdu.bpdu._PACK_LEN + bpdu.ConfigurationBPDUs.PACK_LEN + bpdu.RstBPDUs.PACK_LEN
                  + llc.llc._PACK_LEN + llc.ControlFormatU._PACK_LEN)

        e = ethernet.ethernet(dst_mac, src_mac, length)
        l = llc.llc(llc.SAP_BPDU, llc.SAP_BPDU, llc.ControlFormatU())
        pkt = packet.Packet()
        pkt.add_protocol(e)
        pkt.add_protocol(l)
        pkt.add_protocol(b)
        pkt.serialize()

        return pkt.data

    def tx_bpdu(self, bpdu):
        self.ofctl.send_packet_out(self.ofport.port_no, bpdu)

    def change_status(self,new_state):
        self.stop_transition = True
        if (new_state is PORT_STATE_LEARNING) or (new_state is PORT_STATE_DISCARDING):
            new_prop = True
        else:
            new_prop = False
        if new_state != self.state:
            self.state = new_state
            self.proposing = new_prop
            self.ofctl.set_port_status(self.ofport, self.state)
            self.send_event(EventPortStateChange(self.dp, self))

    def change_role(self,new_role): ################################################# DA FINIRE?
        if new_role != self.role:
            self.role = new_role
            self.send_event(EventPortRoleChange(self.dp, self))

### hello_tmr = timer che scade con l'hello time del bridge
### topo_change_tmr = timer che scade con il topology_change
class Timers(object):
    def __init__(self, hello_tmr, topo_change_tmr):
        self.hello_tmr = hello_tmr
        self.topo_change_tmr = topo_change_tmr
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

class Times(object):
    def __init__(self, message_age, forward_delay, hello_time, max_age):
        super(Times, self).__init__()
        self.message_age = message_age
        self.forward_delay = forward_delay
        self.hello_time = hello_time
        self.max_age = max_age
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

class BridgeId(object):
    def __init__(self, priority, system_id_extension, mac_addr):
        super(BridgeId, self).__init__()
        self.priority = priority
        self.system_id_extension = system_id_extension
        self.mac_addr = mac_addr
        self.value = bpdu.ConfigurationBPDUs.encode_bridge_id(
            priority, system_id_extension, mac_addr)
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

class PortId(object):
    def __init__(self, priority, port_no):
        super(PortId, self).__init__()
        self.priority = priority
        self.port_no = port_no
        self.value = bpdu.ConfigurationBPDUs.encode_port_id(priority, port_no)
    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

class Priority(object):
    def __init__(self, root_id, root_path_cost,
                 designated_bridge_id, designated_port_id):
        super(Priority, self).__init__()
        self.root_id = root_id
        self.root_path_cost = root_path_cost
        self.designated_bridge_id = designated_bridge_id
        self.designated_port_id = designated_port_id

    def __eq__(self, other): 
        return self.__dict__ == other.__dict__

class OfCtl_v1_0(object):
    def __init__(self, dp):
        super(OfCtl_v1_0, self).__init__()
        self.dp = dp

    def send_packet_out(self, out_port, data):
        actions = [self.dp.ofproto_parser.OFPActionOutput(out_port, 0)]
        self.dp.send_packet_out(buffer_id=self.dp.ofproto.OFP_NO_BUFFER,
                                in_port=self.dp.ofproto.OFPP_CONTROLLER,
                                actions=actions, data=data)

    def set_port_status(self, port, state):
        ofproto_parser = self.dp.ofproto_parser
        mask = 0b1111111
        msg = ofproto_parser.OFPPortMod(self.dp, port.port_no, port.hw_addr,
                                        PORT_CONFIG_V1_0[state], mask,
                                        port.advertised)
        self.dp.send_msg(msg)

class EventTopologyChange(event.EventBase):
    def __init__(self, dp):
        super(EventTopologyChange, self).__init__()
        self.dp = dp

# Event for receive packet in message except BPDU packet.
class EventPacketIn(event.EventBase):
    def __init__(self, msg, bridge):
        super(EventPacketIn, self).__init__()
        self.msg = msg
        self.bridge = bridge

class EventPortStateChange(event.EventBase):
    def __init__(self, dp, port):
        super(EventPortStateChange, self).__init__()
        self.dp = dp
        self.port_no = port.ofport.port_no
        self.port_state = port.state

class EventPortRoleChange(event.EventBase):
    def __init__(self, dp, port):
        super(EventPortRoleChange, self).__init__()
        self.dp = dp
        self.port_no = port.ofport.port_no
        self.port_role = port.role


class OfCtl_v1_2later(OfCtl_v1_0):
    def __init__(self, dp):
        super(OfCtl_v1_2later, self).__init__(dp)

    def set_port_status(self, port, state):
        ofp = self.dp.ofproto
        parser = self.dp.ofproto_parser
        config = {ofproto_v1_2: PORT_CONFIG_V1_2,
                  ofproto_v1_3: PORT_CONFIG_V1_3}

        mask = 0b1100101
        msg = parser.OFPPortMod(self.dp, port.port_no, port.hw_addr,
                                config[ofp][state], mask, port.advertised)
        self.dp.send_msg(msg)

        if config[ofp][state] & ofp.OFPPC_NO_PACKET_IN:
            self.add_no_pkt_in_flow(port.port_no)
        else:
            self.del_no_pkt_in_flow(port.port_no)

    def add_bpdu_pkt_in_flow(self):
        ofp = self.dp.ofproto
        parser = self.dp.ofproto_parser

        match = parser.OFPMatch(eth_dst=bpdu.BRIDGE_GROUP_ADDRESS)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS,
                                             actions)]
        mod = parser.OFPFlowMod(self.dp, priority=BPDU_PKT_IN_PRIORITY,
                                match=match, instructions=inst)
        self.dp.send_msg(mod)

    def add_no_pkt_in_flow(self, in_port):
        parser = self.dp.ofproto_parser

        match = parser.OFPMatch(in_port=in_port)
        mod = parser.OFPFlowMod(self.dp, priority=NO_PKT_IN_PRIORITY,
                                match=match)
        self.dp.send_msg(mod)

    def del_no_pkt_in_flow(self, in_port):
        ofp = self.dp.ofproto
        parser = self.dp.ofproto_parser

        match = parser.OFPMatch(in_port=in_port)
        mod = parser.OFPFlowMod(self.dp, command=ofp.OFPFC_DELETE_STRICT,
                                out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
                                priority=NO_PKT_IN_PRIORITY, match=match)
        self.dp.send_msg(mod)