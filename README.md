# Port-Status-Monitoring-Tool
# SDN Learning Switch with Access Control
### Computer Networks Project — Mininet + Ryu (OpenFlow 1.3)

---

## Problem Statement

Traditional networks rely on distributed per-device intelligence. Software-Defined Networking (SDN) separates the **control plane** (decisions) from the **data plane** (forwarding), centralising logic in a **controller**.

This project implements a **Layer-2 learning switch** using:
- **Mininet** to emulate the network topology
- **Ryu** as the OpenFlow 1.3 SDN controller
- **Explicit flow rules** (match + action) installed dynamically

It demonstrates two scenarios:
| Scenario | Description | Expected Result |
|----------|-------------|----------------|
| **A – Normal** | h1 ↔ h2 ping + iperf | ✅ Succeeds |
| **B – Blocked** | h3 → h1 (port 3 ACL) | ❌ Fails (dropped) |

---

## Repository Structure

```
.
├── ryu_app.py         # Ryu controller application (L2 switch + ACL)
├── mininet_topo.py    # Mininet topology script (1 switch, 3 hosts)
└── README.md          # This file
```

---

## Prerequisites

```bash
# Ubuntu 20.04 / 22.04 recommended
sudo apt update
sudo apt install -y mininet openvswitch-switch python3-pip

pip3 install ryu eventlet==0.30.2
```

> **Note:** Ryu requires `eventlet==0.30.2`. Newer versions break the WSGI layer.

---

## Setup & Execution

### Step 1 — Start the Ryu Controller

Open **Terminal 1**:

```bash
ryu-manager ryu_app.py --verbose
```

You should see:
```
loading app ryu_app.py
instantiating app ryu_app.py of L2LearningSwitch
```

### Step 2 — Launch the Mininet Topology

Open **Terminal 2**:

```bash
sudo python3 mininet_topo.py
```

The topology:
```
h1 (10.0.0.1) ──┐
h2 (10.0.0.2) ──┤── s1 ──── Ryu Controller
h3 (10.0.0.3) ──┘
                  └── port 3 is ACL-blocked
```

---

## Test Scenarios

### Scenario A — Normal Connectivity (h1 ↔ h2)

In the Mininet CLI:

```
mininet> h1 ping h2 -c 4
```

**Expected output:**
```
PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.
64 bytes from 10.0.0.2: icmp_seq=1 ttl=64 time=X ms
...
4 packets transmitted, 4 received, 0% packet loss
```

**iperf throughput test:**
```
mininet> iperf h1 h2
```

**Full pingall (h1 ↔ h2 works, h3 fails as expected):**
```
mininet> pingall
```

---

### Scenario B — Blocked Port (h3 → h1)

```
mininet> h3 ping h1 -c 4
```

**Expected output:**
```
PING 10.0.0.1 (10.0.0.1) 56(84) bytes of data.

--- 10.0.0.1 ping statistics ---
4 packets transmitted, 0 received, 100% packet loss
```

The controller logs will show:
```
[ACL-DROP] dpid=0000000000000001  in_port=3  src=00:00:00:00:00:03  dst=00:00:00:00:00:01
```

---

## Inspecting Flow Tables

In a third terminal (while network is running):

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

After `h1 ping h2` you will see unicast rules installed:
```
cookie=0x0, ...priority=10,in_port=1,dl_src=00:00:00:00:00:01,dl_dst=00:00:00:00:00:02 actions=output:2
cookie=0x0, ...priority=10,in_port=2,dl_src=00:00:00:00:00:02,dl_dst=00:00:00:00:00:01 actions=output:1
```

After `h3 ping h1` you will see the ACL drop rule:
```
cookie=0x0, ...priority=10,in_port=3 actions=drop
```

---

## How It Works

### Controller–Switch Interaction

```
Switch connects
      │
      ▼
switch_features_handler()
      │  installs table-miss rule (priority 0)
      │  → send all unknown packets to controller
      ▼
packet_in_handler() called for each unmatched frame
      │
      ├─ in_port == 3? → DROP + install drop rule
      │
      ├─ Learn: mac_to_port[dpid][src_mac] = in_port
      │
      ├─ dst known? → unicast + install flow rule (priority 10)
      │
      └─ dst unknown? → FLOOD
```

### Flow Rule Design (Match–Action)

| Rule | Match | Action | Priority |
|------|-------|--------|----------|
| Table-miss | `*` (all) | Send to controller | 0 |
| ACL drop | `in_port=3` | Drop (no actions) | 10 |
| Unicast | `in_port, eth_src, eth_dst` | `output:<port>` | 10 |

---

## Expected Output / Proof of Execution

### pingall result
```
mininet> pingall
*** Ping: testing ping reachability
h1 -> h2 X
h2 -> h1 X
h3 -> X X
*** Results: 66% dropped (2/6 received)
```
*(h1↔h2 pass; anything involving h3 fails due to ACL)*

### Flow table after tests
```
 priority=0  actions=CONTROLLER:65535
 priority=10,in_port=3  actions=drop
 priority=10,in_port=1,...  actions=output:2
 priority=10,in_port=2,...  actions=output:1
```

> Screenshots of Wireshark captures, iperf results, and flow tables should be placed in a `/screenshots` folder in this repo.

---

## Wireshark Capture Instructions

```bash
# Capture on h1's interface
sudo wireshark &
# Select interface: s1-eth1
# Filter: icmp
# Then run: h1 ping h2 -c 4 in Mininet CLI
```

---
