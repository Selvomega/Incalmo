# Attacker VM Setup

Sets up an isolated attacker VM on the same `virbr0` network as the MOSIP cluster, deploys the sandcat C2 agent inside it, and runs Incalmo from the host to control the attack.

## Network Topology

```
HOST (192.168.122.1)
│
│  virbr0 (192.168.122.0/24)
│  ├── mosip-cluster  (192.168.122.20)   ← target
│  ├── obs-cluster    (192.168.122.10)   ← untouched
│  └── attacker-vm   (192.168.122.100)  ← sandcat agent lives here
```

Incalmo and the C2 server run on the host. The attacker VM is the only thing that touches MOSIP over the network.

---

## Destroying and Reinstalling the VM

If you need to recreate the VM with updated cloud-init configuration (e.g., new Python packages or sudo privileges):

```bash
# 1. Stop all running services
pkill -f sandcat.go  # Stop agent on VM
pkill -f "c2server"  # Stop C2 server
pkill -f "main.py"   # Stop Incalmo

# 2. Destroy the VM
sudo virsh destroy attacker-vm 2>/dev/null
sudo virsh undefine attacker-vm 2>/dev/null
sudo rm -f /var/lib/libvirt/images/attacker-vm.qcow2
sudo rm -f /var/lib/libvirt/images/attacker-cloud-init.iso
sudo rm -r /tmp/attacker-vm/

# 3. Remove DHCP reservation
virsh net-update default delete ip-dhcp-host \
    '<host mac="52:54:00:cc:dd:ee" name="attacker-vm" ip="192.168.122.100"/>' \
    --live --config 2>/dev/null || echo "DHCP reservation removal skipped"

# 4. Recreate the VM using the updated setup
# (Follow steps 1-2 below)
```

---

## Step 1: Block Attacker VM from Host Services

The host exposes services on `0.0.0.0` (MySQL, SSH, RabbitMQ, etc.) that are reachable from `virbr0`. These rules block the attacker VM from initiating connections to the host, allowing only the C2 server port through. They do not affect SSH from the host into the VM, which is outbound from the host and not touched by the INPUT chain.

```bash
sudo iptables -A INPUT -i virbr0 -s 192.168.122.100 -m state --state ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -i virbr0 -s 192.168.122.100 -p udp --dport 53 -j ACCEPT
sudo iptables -A INPUT -i virbr0 -s 192.168.122.100 -p tcp --dport 53 -j ACCEPT
sudo iptables -A INPUT -i virbr0 -s 192.168.122.100 -p tcp --dport 8888 -j ACCEPT
sudo iptables -A INPUT -i virbr0 -s 192.168.122.100 -j DROP
```

---

## Step 2: Create the Attacker VM

First, generate the cloud-init ISO. This is a small virtual CD-ROM the VM reads on first boot to create the `attacker` user and install the SSH public key — without it the VM boots with no accessible user.

```bash
mkdir -p /tmp/attacker-vm

cat > /tmp/attacker-vm/meta-data <<EOF
instance-id: attacker-vm
local-hostname: attacker-vm
EOF

cat > /tmp/attacker-vm/user-data <<EOF
#cloud-config
users:
  - name: attacker
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $(cat ~/.ssh/incalmo.pub)
package_update: true
packages:
  - nmap
  - nikto
  - ncat
  - python3
  - python3-pip
  - wget
  - openssh-client
runcmd:
  - pip install --user httpx pyjwt requests-oauthlib schemathesis beautifulsoup4
EOF

cloud-localds /tmp/attacker-vm/attacker-cloud-init.iso \
    /tmp/attacker-vm/user-data \
    /tmp/attacker-vm/meta-data
```

Then create and run the creation script:

```bash
cat > /tmp/attacker-vm/create-attacker-vm.sh <<'EOF'
#!/bin/bash
set -e

# Copy cloud-init ISO into libvirt images directory
cp /tmp/attacker-vm/attacker-cloud-init.iso /var/lib/libvirt/images/attacker-cloud-init.iso

# Create a 20G qcow2 disk backed by the existing jammy base image
qemu-img create -f qcow2 \
    -b /var/lib/libvirt/images/jammy-server-cloudimg-amd64.img \
    -F qcow2 \
    /var/lib/libvirt/images/attacker-vm.qcow2 20G

# Add a static DHCP reservation: MAC 52:54:00:cc:dd:ee -> 192.168.122.100
# (skip if already exists from a previous run)
virsh net-update default add ip-dhcp-host \
    '<host mac="52:54:00:cc:dd:ee" name="attacker-vm" ip="192.168.122.100"/>' \
    --live --config 2>/dev/null || echo "DHCP reservation already exists, skipping."

# Create and start the VM
virt-install \
    --connect qemu:///system \
    --name attacker-vm \
    --memory 2048 \
    --vcpus 1 \
    --disk /var/lib/libvirt/images/attacker-vm.qcow2,bus=virtio \
    --disk /var/lib/libvirt/images/attacker-cloud-init.iso,device=cdrom \
    --network network=default,mac=52:54:00:cc:dd:ee \
    --os-variant ubuntu22.04 \
    --noautoconsole \
    --import

echo "VM created. Waiting for it to get an IP..."
sleep 20
virsh domifaddr attacker-vm
EOF

chmod +x /tmp/attacker-vm/create-attacker-vm.sh
sudo /tmp/attacker-vm/create-attacker-vm.sh
```

Wait ~30 seconds for cloud-init to finish, then verify SSH access:

```bash
ssh -i ~/.ssh/incalmo attacker@192.168.122.100
```

The `attacker` user has **full sudo privileges (NOPASSWD)** and can install packages, run network tools, and execute sandcat. Pre-installed tools include:
- Network: nmap, nikto, ncat, wget
- Python packages (Phase 1): httpx, pyjwt, requests-oauthlib, schemathesis, beautifulsoup4

---

## Step 3: Configure Incalmo

Ensure `config/config.json` is set up for the MOSIP environment:

```json
{
    "name": "mosip-test",
    "strategy": {
        "planning_llm": "claude-3.5-sonnet",
        "execution_llm": "claude-3.5-sonnet",
        "abstraction": "incalmo"
    },
    "environment": "MOSIP",
    "c2c_server": "http://192.168.122.1:8888",
    "blacklist_ips": ["192.168.122.1"]
}
```

Set your API key in `.env`:

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
```

---

## Step 4: Start Everything

### First Time Only

Copy the sandcat binary onto the attacker VM (only needed once — it stays there across restarts):

```bash
cd /home/peilin/Incalmo
scp -i ~/.ssh/incalmo incalmo/c2server/agents/sandcat.go attacker@192.168.122.100:~/sandcat.go
ssh -i ~/.ssh/incalmo attacker@192.168.122.100 'chmod +x ~/sandcat.go'
```

### Every Run

**Terminal 1 — C2 server** (start first):
```bash
cd /home/peilin/Incalmo
uv run python -m incalmo.c2server.c2server
```

**Terminal 2 — Start sandcat on the attacker VM:**
```bash
ssh -i ~/.ssh/incalmo attacker@192.168.122.100 \
  'nohup ~/sandcat.go -server http://192.168.122.1:8888 -group red > /dev/null 2>&1 &'
```

You should see `New agent: <paw>` printed in the C2 server terminal within a few seconds.

**Terminal 3 — Run Incalmo** (once the agent is registered):
```bash
cd /home/peilin/Incalmo
uv run main.py
```

### Teardown

The attacker VM stays running. Tear down in this order:

**1. Stop Incalmo** — Ctrl+C in Terminal 3.

**2. Kill sandcat on the attacker VM:**
```bash
ssh -i ~/.ssh/incalmo attacker@192.168.122.100 'pkill -f sandcat.go'
```

**3. Stop the C2 server** — Ctrl+C in Terminal 1, then clean up Celery state files:
```bash
rm -f /home/peilin/Incalmo/celery.db /home/peilin/Incalmo/celery_results.db
```


## How It Works

1. The LLM (Claude) decides what action to take based on the current network state
2. Incalmo sends the command to the C2 server via `C2ApiClient` (HTTP to port 8888)
3. The C2 server queues the command for the sandcat agent
4. Sandcat on the attacker VM picks it up on its next beacon (every 3 seconds), executes it as bash, and returns the output
5. The output is fed back to the LLM as context for the next step
6. All actual network traffic to MOSIP originates from `192.168.122.100` — the attacker VM
