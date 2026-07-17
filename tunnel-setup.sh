#!/bin/bash
# Cloudflare Tunnel Setup Script
# Run this to quickly set up and start the tunnel

set -e

echo "🚀 Dodgeville Scheduler - Cloudflare Tunnel Setup"
echo "=================================================="
echo ""

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install cloudflare/cloudflare/cloudflared
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
        sudo dpkg -i cloudflared.deb
        rm cloudflared.deb
    else
        echo "❌ Automatic installation not supported on this OS. See TUNNEL_SETUP.md"
        exit 1
    fi
fi

echo "✅ cloudflared is installed"
echo ""

# Check if tunnel exists
if cloudflared tunnel list | grep -q "dodgeville-scheduler"; then
    echo "✅ Tunnel 'dodgeville-scheduler' already exists"
else
    echo "🔐 Creating tunnel 'dodgeville-scheduler'..."
    cloudflared tunnel create dodgeville-scheduler
fi

echo ""
echo "📋 Next steps:"
echo "1. Edit ~/.cloudflared/config.yml (template in .cloudflared/config.yml.example)"
echo "2. Replace 'yourdomain.com' with your actual Cloudflare domain"
echo "3. Verify the port matches your scheduler (check main.py)"
echo "4. Run: cloudflared tunnel run dodgeville-scheduler"
echo ""
echo "🌐 Then update your Cloudflare DNS:"
echo "   - Go to DNS > Records in Cloudflare dashboard"
echo "   - Add CNAME: @ → <TUNNEL_ID>.cfargotunnel.com (Proxied)"
echo ""
