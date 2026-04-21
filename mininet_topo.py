"""
mininet_topo.py  –  Custom Mininet topology for SDN project
============================================================
Topology
--------
    h1 ──┐
    h2 ──┤── s1 ──── Remote Ryu Controller (127.0.0.1:6653)
    h3 ──┘

  h1  10.0.0.1  (port 1 on s1)
  h2  10.0.0.2  (port 2 on s1)
  h3  10.0.0.3  (port 3 on s1)  ← BLOCKED by ACL in ryu_app.py

Usage
-----
  sudo python3 mininet_topo.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info


def build_topology():
    """Create and return a Mininet network with one switch and three hosts."""

    net = Mininet(
        controller=RemoteController,
        switch=OVSKernelSwitch,
        autoSetMacs=True,     # assigns deterministic MACs: 00:00:00:00:00:01 etc.
    )

    info("*** Adding controller\n")
    controller = net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    info("*** Adding switch\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")

    info("*** Adding hosts\n")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")   # will be blocked at port 3

    info("*** Creating links\n")
    # Link order determines port numbers on s1: h1→port1, h2→port2, h3→port3
    net.addLink(h1, s1)   # s1-eth1
    net.addLink(h2, s1)   # s1-eth2
    net.addLink(h3, s1)   # s1-eth3  (ACL blocks this port)

    return net, controller


def run():
    setLogLevel("info")
    net, controller = build_topology()

    info("*** Starting network\n")
    net.start()

    # Force OVS to use OpenFlow 1.3
    net.get("s1").cmd("ovs-vsctl set bridge s1 protocols=OpenFlow13")

    info("\n" + "="*60)
    info("\nTopology ready!")
    info("\n  h1 (10.0.0.1) ── s1 ── h2 (10.0.0.2)")
    info("\n                    └─── h3 (10.0.0.3)  [port 3 – BLOCKED]")
    info("\n\nTest Scenario A  (allowed):  h1 ping h2")
    info("\nTest Scenario B  (blocked):  h3 ping h1  → should fail")
    info("\n" + "="*60 + "\n")

    info("*** Opening Mininet CLI (type 'exit' to stop)\n")
    CLI(net)

    info("*** Stopping network\n")
    net.stop()


if __name__ == "__main__":
    run()
