# Port-Status-Monitoring-Tool — Prema P Kotur PES1UG24CS343
# SDN Learning Switch with Access Control
### Computer Networks Project — Mininet + Ryu (OpenFlow 1.3)

---

## Problem Statement

Traditional networks rely on distributed per-device intelligence. Software-Defined Networking (SDN) separates the **control plane** (decisions) from the **data plane** (forwarding), centralising logic in a **controller**.

This project implements a **Layer-2 learning switch** using:
- **Mininet** to emulate the network topology
- **Ryu** as the OpenFlow 1.3 SDN controller
- **Explicit flow rules** (match + action) installed dynamically
- **Port status monitoring** with real-time alerts and a live web dashboard

It demonstrates two scenarios:

| Scenario | Description | Expected Result |
|----------|-------------|----------------|
| **A – Normal** | h1 ↔ h2 ping + iperf | ✅ Succeeds |
| **B – Blocked** | h3 → h1 (port 3 ACL) | ❌ Fails (dropped) |

---

## Repository Structure

```
.
├── ryu_app.py          # Ryu controller — L2 switch + ACL + port monitoring + REST API
├── mininet_topo.py     # Mininet topology script (1 switch, 3 hosts)
├── port_dashboard.html # Live web dashboard (polls REST API every 3 s)
└── README.md           # This file
```

---

## Prerequisites

```bash
# Ubuntu 20.04 / 22.04 recommended
sudo apt update
sudo apt install -y mininet openvswitch-switch python3-pip

pip3 install ryu eventlet==0.30.2
```

> **Note:** Ryu requires `eventlet==0.30.2`. Newer versions break the WSGI layer used by the REST API.

---

## Setup & Execution

### Step 1 — Start the Ryu Controller

Open **Terminal 1**. The `--wsapi-port 8080` flag enables the live REST API used by the dashboard:

```bash
ryu-manager ryu_app.py --verbose
```

You should see:
```
loading app ryu_app.py
instantiating app ryu_app.py of L2LearningSwitch
```

> 📸 **Screenshot 1** 
<img width="940" height="474" alt="image" src="https://github.com/user-attachments/assets/ff0325f2-297a-411b-b22e-eb03634629ec" />

---

### Step 2 — Launch the Mininet Topology

Open **Terminal 2**:

```bash
sudo python3 mininet_topo.py
```

The topology:
```
h1 (10.0.0.1) ──┐
h2 (10.0.0.2) ──┤── s1 ──── Ryu Controller (127.0.0.1:6633)
h3 (10.0.0.3) ──┘
(port 3 is ACL-blocked in ryu_app.py via BLOCKED_PORT = 3)
```

> 📸 **Screenshot 2** 
<img width="940" height="568" alt="image" src="https://github.com/user-attachments/assets/0813d40b-7ef9-4173-b0d8-7a5edbe26ce1" />

---

### Step 3 — Open the Live Dashboard

Open `port_dashboard.html` in any browser (Chrome / Firefox):

```bash
# Linux
xdg-open port_dashboard.html

# Or just drag the file into your browser
```

The dashboard auto-polls `http://localhost:8080/status` every 3 seconds and shows:
- **Summary cards** — total ports UP, ports DOWN, events logged
- **Live port cards** — colour-coded per port (green = UP, red = DOWN, amber = ACL-blocked)
- **Port event log** — timestamped list of every UP/DOWN/ADD/MODIFY event
- **MAC learning table** — live view of which MAC was learned on which port

> 📸 **Screenshot 3**
<img width="940" height="434" alt="image" src="https://github.com/user-attachments/assets/9854038d-1409-4220-960c-c4e7c69c48e7" />

You can also query the REST API directly from a terminal:

```bash
# Full JSON status
curl http://localhost:8080/status | python3 -m json.tool

# Port states only
curl http://localhost:8080/status/ports | python3 -m json.tool

# Event log only
curl http://localhost:8080/status/events | python3 -m json.tool
```

> 📸 **Screenshot 4** 
<img width="940" height="218" alt="image" src="https://github.com/user-attachments/assets/dbe4b139-4ed2-49f3-b2d4-2dc4b0d2c27d" />

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

> 📸 **Screenshot 5 and 6** 
<img width="940" height="347" alt="image" src="https://github.com/user-attachments/assets/2191068a-58e8-4119-8141-1d832e2bbec3" />

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

The controller logs in Terminal 1 will show:
```
[ACL-DROP] dpid=0000000000000001  in_port=3  src=00:00:00:00:00:03  dst=00:00:00:00:00:01
```

> 📸 **Screenshot 7** 
<img width="940" height="197" alt="image" src="https://github.com/user-attachments/assets/2b1ff97a-fdce-4818-8cba-680e2b92fc7c" />

---

### Port Status Monitoring Demo

Simulate a link going down and back up from the Mininet CLI:

```
mininet> link s1 h3 down
```

**What happens:**
1. OVS detects the link state change and sends an `OFPPortStatus` message to Ryu
2. `port_status_handler` fires, logs a `[PORT EVENT]` warning
3. `_generate_alert` logs an `[ALERT]` error and evicts stale MAC entries for that port
4. The dashboard's port card for port 3 turns **red** within 3 seconds
5. The event log shows a new DOWN entry with a timestamp

```
mininet> link s1 h3 up
```

The dashboard port card returns to its normal state, and a new UP event appears in the log.

> 📸 **Screenshot 8** 
<img width="940" height="143" alt="image" src="https://github.com/user-attachments/assets/64994b22-6ac8-4305-a43a-406757375189" />

> 📸 **Screenshot 9**
<img width="940" height="340" alt="image" src="https://github.com/user-attachments/assets/87a3dbdf-b175-43ba-8c84-6730a8e704a5" />

> 📸 **Screenshot 10** 
<img width="940" height="323" alt="image" src="https://github.com/user-attachments/assets/2d208086-8d36-4251-9d85-4fada55a7eb6" />

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

> 📸 **Screenshot 11** 
<img width="940" height="73" alt="image" src="https://github.com/user-attachments/assets/363f7745-f5c6-4cf8-8f74-16ee0cebcb09" />

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

Any port state change
      │
      ▼
port_status_handler()
      │  logs [PORT EVENT] with reason + state
      │  updates port_states table with timestamp
      │  appends to event ring buffer (maxlen=50)
      │
      └─ _generate_alert()
             ├─ DOWN → [ALERT] error log + evict stale MACs
             └─ UP   → [ALERT] info log
```

### Flow Rule Design (Match–Action)

| Rule | Match | Action | Priority |
|------|-------|--------|----------|
| Table-miss | `*` (all) | Send to controller | 0 |
| ACL drop | `in_port=3` | Drop (no actions) | 10 |
| Unicast | `in_port, eth_src, eth_dst` | `output:<port>` | 10 |

### REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Full JSON: port states + event log + MAC table |
| `/status/ports` | GET | Current live port states per switch per port |
| `/status/events` | GET | Ring buffer of last 50 port events |

### Dashboard Features

| Feature | Detail |
|---------|--------|
| Auto-refresh | Polls REST API every 3 seconds |
| Port cards | Colour-coded: green (UP), red (DOWN), amber (ACL-blocked) |
| Event log | Reverse-chronological, flashes on new events |
| MAC table | Live view of learned MAC → port mappings |
| Connection badge | Shows if controller is reachable; turns red if offline |

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

---

## Wireshark Capture Instructions

```bash
# Capture on s1's first interface
sudo wireshark 
# Select interface: s1-eth1
# Filter: icmp
# Then run: h1 ping h2 -c 4 in Mininet CLI
```

> 📸 **Screenshot 12** 
<img width="940" height="436" alt="image" src="https://github.com/user-attachments/assets/0c8597d5-e5ea-4f85-b0b0-142eed83d629" />

---


## Cleanup

```bash
# Stop Mininet and clean up virtual interfaces
sudo mn -c
```
