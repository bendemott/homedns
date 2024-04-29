#!/bin/bash
set -e # fail on first error
if ! command -v homedns &> /dev/null
then
    echo "homedns is not installed or not on the path"
    exit 1
fi

# Create system account and group
sudo useradd -r homedns || true
sudo groupadd -f homedns

# Create default config and directories
sudo mkdir -p /etc/homedns
sudo mkdir -p /etc/homedns/jwt_secrets
sudo cp --no-clobber service/server_config.yaml /etc/homedns/config.yaml
if [[ ! -e /etc/homedns/auth_secrets.json ]]; then
    mkdir -p /Scripts
    sudo echo "{}" >> /etc/homedns/auth_secrets.json
fi

sudo chown -R homedns:homedns /etc/homedns
sudo chmod 644 -R /etc/homedns/config.yaml
sudo chmod 640 /etc/homedns/auth_secrets.json
sudo chmod 650 -R /etc/homedns/jwt_secrets

# We want our service to be able to listen on port (443, and 53)
sudo setcap 'cap_net_bind_service=+ep' $(which homedns)
sudo cp service/homedns.service /etc/systemd/system/
sudo chown root:root /etc/systemd/system/homedns.service
sudo chmod 644 /etc/systemd/system/homedns.service
sudo systemctl daemon-reload
sudo systemctl enable homedns.service
sudo systemctl start homedns.service
sudo journalctl -n 100 -u homedns

echo "Service created: 'homedns'"
echo "  status: systemctl status homedns"
echo "Done!"