# Oracle Cloud Deployment (Always Free)

Deploy the Ministering Interviews app on Oracle Cloud's Always Free tier using your existing Dockerfile.

## What You Get (Free Forever)

- **2x AMD VMs**: 1 OCPU, 1 GB RAM each
- **200 GB block storage**
- **10 TB/month bandwidth**
- No credit card charges (verification only)

## Prerequisites

- Oracle Cloud account: https://www.oracle.com/cloud/free/
- SSH key pair (or Oracle will generate one)

## Step 1: Create the VM

1. Log in to Oracle Cloud Console
2. Navigate to **Compute → Instances → Create Instance**

Configure:
```
Name: ministering-app

Image and Shape:
  - Image: Oracle Linux 8 (default)
  - Shape: Click "Change Shape"
    → Virtual Machine
    → AMD
    → VM.Standard.E2.1.Micro (Always Free eligible)
    → 1 GB RAM

Networking:
  - Create new VCN (or use existing)
  - Create new public subnet
  - Assign public IPv4 address: Yes

Add SSH Keys:
  - Paste your public key OR
  - Generate a key pair (download the private key!)
```

3. Click **Create** and wait for the instance to be "Running"
4. Note the **Public IP address**

## Step 2: Configure Firewall (Security List)

1. Go to **Networking → Virtual Cloud Networks**
2. Click your VCN → **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules**

Add these rules:
```
Rule 1 (Web App):
  - Source CIDR: 0.0.0.0/0
  - IP Protocol: TCP
  - Destination Port: 8181

Rule 2 (HTTPS - optional):
  - Source CIDR: 0.0.0.0/0
  - IP Protocol: TCP
  - Destination Port: 443
```

## Step 3: Configure VM Firewall (iptables)

Oracle Linux has an additional firewall. SSH in and open the port:

```bash
ssh opc@<your-public-ip>

# Open port 8181
sudo firewall-cmd --permanent --add-port=8181/tcp
sudo firewall-cmd --reload
```

## Step 4: Install Docker

```bash
# Install Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to docker group (avoid sudo)
sudo usermod -aG docker opc

# Apply group change (log out and back in, or run:)
newgrp docker
```

## Step 5: Deploy the App

```bash
# Clone your repository
git clone https://github.com/YOUR_USERNAME/Ministering-Interviews.git
cd Ministering-Interviews

# Create environment file
cat > .env << 'EOF'
SECRET_KEY=your-secret-key-change-this-to-random-string
PORT=8181
EOF

# Generate a proper secret key
echo "SECRET_KEY=$(openssl rand -hex 32)" > .env

# Build and start
docker compose up -d --build

# Check it's running
docker compose ps
docker compose logs -f
```

## Step 6: Access Your App

Open in browser:
```
http://<your-public-ip>:8181
```

## Monitoring

```bash
# View logs
docker compose logs -f

# Check memory usage (important with 1GB RAM)
docker stats

# Restart if needed
docker compose restart
```

## Persistence

SQLite database is stored in a Docker volume. Data persists across container restarts.

To backup:
```bash
docker compose exec ministering-app cat /app/instance/interviews.db > backup.db
```

To restore:
```bash
docker compose cp backup.db ministering-app:/app/instance/interviews.db
docker compose restart
```

## If 1GB RAM Isn't Enough

Signs of memory issues:
- Container keeps restarting
- Scraping fails or browser crashes
- `docker stats` shows ~100% memory

Options:
1. **Add swap space** (quick fix):
   ```bash
   sudo dd if=/dev/zero of=/swapfile bs=1M count=1024
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
   ```

2. **Use ARM VM with Selenium sidecar** (more RAM, but more complex setup)

## Troubleshooting

**Can't connect to port 8181:**
- Check Security List ingress rules
- Check VM firewall: `sudo firewall-cmd --list-ports`
- Check container is running: `docker compose ps`

**Container keeps restarting:**
- Check logs: `docker compose logs`
- Check memory: `docker stats`
- Add swap if memory is the issue

**Scraping fails:**
- Check Selenium logs in container output
- May need more memory for Chrome
- Try adding swap first

## Cost

$0 forever, as long as you:
- Stay within Always Free limits
- Use the VM.Standard.E2.1.Micro shape
- Don't add paid services

Oracle may reclaim idle resources after 7 days of inactivity, so ensure your app has some traffic or set up a health check ping.
