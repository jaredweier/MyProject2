# Cloudflare Tunnel Setup Guide

Deploy your Dodgeville Scheduler to your Cloudflare domain securely using Cloudflare Tunnel.

## What is Cloudflare Tunnel?

Cloudflare Tunnel creates a secure connection from your local machine to Cloudflare's edge network, allowing you to access your scheduler from anywhere using your domain — without exposing your IP or opening ports.

## Prerequisites

- Cloudflare account (you already have this — you bought a domain)
- Local machine running the scheduler
- Cloudflare Tunnel CLI installed

## Setup Steps

### Step 1: Install Cloudflare Tunnel

**Windows:**
```bash
choco install cloudflared
# or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

**macOS:**
```bash
brew install cloudflare/cloudflare/cloudflared
```

**Linux:**
```bash
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
```

### Step 2: Authenticate with Cloudflare

Run:
```bash
cloudflared tunnel login
```

This opens a browser to authorize Cloudflare Tunnel. Select your domain and click **Authorize**.

### Step 3: Create a Tunnel

```bash
cloudflared tunnel create dodgeville-scheduler
```

Save the **Tunnel ID** — you'll need it.

### Step 4: Configure the Tunnel

Create or update `~/.cloudflared/config.yml`:

```yaml
tunnel: dodgeville-scheduler
credentials-file: /Users/YOUR_USERNAME/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: yourdomain.com
    service: http://localhost:8080
  - service: http_status:404
```

Replace:
- `yourdomain.com` with your actual Cloudflare domain
- `localhost:8080` with the port your scheduler runs on (check `main.py`)
- `/Users/YOUR_USERNAME/` with your home directory path (Windows: `C:\Users\USERNAME\AppData\Roaming\.cloudflared`)

### Step 5: Point Your Domain to the Tunnel

In Cloudflare dashboard:

1. Go to **DNS** → **Records**
2. Delete any existing CNAME or A record for your domain
3. Add a new **CNAME record:**
   - **Name:** `@` (root domain)
   - **Target:** `<TUNNEL_ID>.cfargotunnel.com`
   - **Proxy status:** Proxied (orange cloud)
   - **TTL:** Auto
4. Click **Save**

### Step 6: Run the Tunnel

```bash
cloudflared tunnel run dodgeville-scheduler
```

You should see:
```
Registered tunnel connection connID...
```

### Step 7: Test It

- Open `https://yourdomain.com` in your browser
- You should see your scheduler running

---

## Keeping It Running (Optional)

To keep the tunnel running after you close the terminal:

**Windows (create shortcut):**
1. Right-click desktop → **New** → **Shortcut**
2. Paste: `C:\Program Files (x86)\cloudflared\cloudflared.exe tunnel run dodgeville-scheduler`
3. Name it "Start Tunnel"
4. Run at startup by moving to `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup`

**macOS/Linux (systemd service):**
```bash
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

---

## Troubleshooting

**"Port already in use"**
- Check what port your scheduler uses in `main.py`
- Update `config.yml` to match that port

**"Connection refused"**
- Make sure your scheduler is running locally
- Verify the port in `config.yml` is correct

**"Invalid hostname"**
- Ensure your Cloudflare domain is added to your account
- Check spelling in `config.yml`

---

## Next Steps

Once tunnel is running:
- Officers can access scheduler at `https://yourdomain.com`
- Tunnel stays secure—no port forwarding needed
- Your IP is never exposed
- Cloudflare provides DDoS protection automatically

For help, see [Cloudflare Tunnel Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
