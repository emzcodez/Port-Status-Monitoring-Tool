"""
SDN Controller: L2 Learning Switch with Port-Based Access Control
=================================================================
Author  : Prema P Kotur
Course  : Computer Networks
Project : SDN with Mininet + Ryu (OpenFlow 1.3)

Description
-----------
This Ryu application implements a Layer-2 learning switch that:
  1. Learns source MAC addresses and the port they arrived on.
  2. Installs unicast flow rules so future frames bypass the controller.
  3. Floods frames whose destination MAC is not yet known.
  4. Demonstrates access control by blocking all traffic from port 3
     (configurable via BLOCKED_PORT constant).

Topology used (mininet_topo.py):
  h1 --- s1 --- h2
          |
          h3   (port 3 – blocked to show ACL scenario)

Test Scenarios
--------------
  Scenario A (normal): h1 <-> h2  → should succeed (ping + iperf)
  Scenario B (blocked): h3 -> h1  → should fail   (port 3 is blocked)
To execute :
# Terminal 1 – start controller
ryu-manager ryu_app.py --verbose

# Terminal 2 – start topology
sudo python3 mininet_topo.py

# In Mininet CLI:
mininet> h1 ping h2 -c 4      # Scenario A: should PASS
mininet> h3 ping h1 -c 4      # Scenario B: should FAIL (ACL)
mininet> iperf h1 h2           # throughput test
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types
import logging
from ryu.controller.handler import MAIN_DISPATCHER
from ryu.ofproto import ofproto_v1_3 as ofproto

# ── Configuration ─────────────────────────────────────────────────────────────
BLOCKED_PORT = 3          # Traffic arriving on this port is dropped (ACL demo)
FLOW_PRIORITY_DEFAULT = 0   # Table-miss / catch-all
FLOW_PRIORITY_UNICAST = 10  # Learned unicast rules
FLOW_IDLE_TIMEOUT = 30      # Seconds before an idle flow is removed
# ──────────────────────────────────────────────────────────────────────────────


class L2LearningSwitch(app_manager.RyuApp):
    """
    Ryu application: L2 learning switch with simple ACL (port blocking).

    MAC learning table layout
    ─────────────────────────
    self.mac_to_port  =  { dpid : { mac_address : port_number } }
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(L2LearningSwitch, self).__init__(*args, **kwargs)
        self.mac_to_port = {}          # MAC learning table
        self.logger.setLevel(logging.DEBUG)

    # ── Helper: install a flow rule ────────────────────────────────────────────
    def add_flow(self, datapath, priority, match, actions,
                 idle_timeout=0, hard_timeout=0):
        """
        Push an OFPFlowMod message to the switch.

        Parameters
        ----------
        datapath      : ryu datapath object (represents the switch)
        priority      : integer – higher wins on conflict
        match         : OFPMatch object
        actions       : list of OFPAction* objects
        idle_timeout  : remove rule after N seconds of inactivity (0 = never)
        hard_timeout  : remove rule after N seconds regardless (0 = never)
        """
        ofproto = datapath.ofproto
        parser  = datapath.ofproto_parser

        # Wrap actions in an ApplyActions instruction
        instructions = [
            parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout,
        )
        datapath.send_msg(flow_mod)

    # ── Event: switch connects (CONFIG_DISPATCHER) ─────────────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Called once when a switch first connects to the controller.
        Installs a table-miss flow rule:
          Match  : everything (empty match)
          Action : send to controller with full packet payload
        This ensures unknown packets always reach packet_in_handler.
        """
        datapath = ev.msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser

        self.logger.info("Switch connected: dpid=%016x", datapath.id)

        # Table-miss entry – lowest priority, sends packet to controller
        match   = parser.OFPMatch()
        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER   # deliver the full packet (no truncation)
            )
        ]
        self.add_flow(datapath, FLOW_PRIORITY_DEFAULT, match, actions)

    # ── Event: packet arrives at controller (MAIN_DISPATCHER) ─────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Core switching logic executed for every packet not matched by an
        existing flow rule.

        Steps
        -----
        1. Parse the incoming packet.
        2. Drop if from BLOCKED_PORT  (ACL scenario B).
        3. Learn the source MAC → in_port mapping.
        4. Look up the destination MAC:
             • Found  → unicast, install a flow rule.
             • Unknown → flood.
        5. Forward the current packet immediately (PacketOut).
        """
        msg      = ev.msg
        datapath = msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser
        in_port  = msg.match['in_port']
        dpid     = datapath.id

        # Parse packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return                         # Not an Ethernet frame – ignore

        src = eth.src
        dst = eth.dst

        # ── ACL: drop traffic from blocked port ────────────────────────────────
        #comment this if you want 0% packet drop else it blocks everything with port3
        if in_port == BLOCKED_PORT:
            self.logger.info(
                "[ACL-DROP] dpid=%016x  in_port=%s  src=%s  dst=%s",
                dpid, in_port, src, dst
            )
            # Install a drop rule so future packets don't hit the controller
            drop_match = parser.OFPMatch(in_port=BLOCKED_PORT)
            self.add_flow(datapath, FLOW_PRIORITY_UNICAST, drop_match,
                          actions=[],       # empty actions = drop
                          idle_timeout=FLOW_IDLE_TIMEOUT)
            return

        # ── Ignore IPv6 multicast (e.g. Neighbour Discovery) ──────────────────
        if dst.startswith("33:33"):
            return

        # ── MAC learning ───────────────────────────────────────────────────────
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port
        self.logger.debug(
            "[LEARN] dpid=%016x  src=%s → port %s", dpid, src, in_port
        )

        # ── Forward decision ───────────────────────────────────────────────────
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
            self.logger.info(
                "[UNICAST] dpid=%016x  %s → %s  via port %s",
                dpid, src, dst, out_port
            )
            # Install unicast flow rule so future frames skip the controller
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            actions = [parser.OFPActionOutput(out_port)]
            self.add_flow(datapath, FLOW_PRIORITY_UNICAST, match, actions,
                          idle_timeout=FLOW_IDLE_TIMEOUT)
        else:
            out_port = ofproto.OFPP_FLOOD
            self.logger.debug(
                "[FLOOD]   dpid=%016x  src=%s  dst=%s (unknown)",
                dpid, src, dst
            )

        # ── Send the current packet out immediately (PacketOut) ────────────────
        actions = [parser.OFPActionOutput(out_port)]
        data    = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            # Switch did not buffer the packet; we must include the raw data
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(out)
        
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, ev):
        msg = ev.msg
        dp  = msg.datapath
        reason = msg.reason
        port_no = msg.desc.port_no
        port_name = msg.desc.name.decode('utf-8')
        reasons = {
		dp.ofproto.OFPPR_ADD:    'PORT ADDED',
		dp.ofproto.OFPPR_DELETE: 'PORT DELETED',
		dp.ofproto.OFPPR_MODIFY: 'PORT MODIFIED',
	    }
        state = 'UP' if not (msg.desc.state & dp.ofproto.OFPPS_LINK_DOWN) else 'DOWN'
        reason_str = reasons.get(reason, 'UNKNOWN')
        self.logger.warning(
		"[PORT EVENT] dpid=%016x port=%s (%s) reason=%s state=%s",
		dp.id, port_no, port_name, reason_str, state
	    )
        self._generate_alert(dp.id, port_no, state)
	    
    def _generate_alert(self, dpid, port_no, state):
        if state == 'DOWN':
            self.logger.error(
                "ALERT: Port %s on switch %016x is DOWN! "
                "Removing stale MAC entries for this port.",
                port_no, dpid
            )

            if dpid in self.mac_to_port:
                stale = [
                    m for m, p in self.mac_to_port[dpid].items()
                    if p == port_no
                ]
                for mac in stale:
                    del self.mac_to_port[dpid][mac]

        elif state == 'UP':
            self.logger.info(
                "ALERT: Port %s on switch %016x is UP.",
                port_no, dpid
            )	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
	    
