#!/bin/bash
set -e # fail on first error
if ! command -v homedns-server &> /dev/null
then
    echo "homedns-server is not installed or not on the path, please install homedns first"
    exit 1
fi

# Create system account and group
sudo useradd -r homedns || true
sudo groupadd -f homedns

# Create default config and directories
sudo mkdir -p /etc/homedns
sudo mkdir -p /etc/homedns/jwt_secrets
if [[ ! -e /etc/homedns/config.yaml ]]; then
    # have the application write a default config out (will not overwrite existing configs)
    sudo homedns-server config-dump --save-to-default
fi

if [[ ! -e /etc/homedns/auth_secrets.json ]]; then
    sudo echo "{}" >> /etc/homedns/auth_secrets.json
fi

if [[ ! -e /etc/homedns/auth_secrets.json ]]; then
    sudo touch /etc/homedns/jwt_secrets/jwt_subjects.yaml
fi


sudo chown -R homedns:homedns /etc/homedns
sudo chmod 644 -R /etc/homedns/config.yaml
sudo chmod 640 /etc/homedns/auth_secrets.json
sudo chmod 640 /etc/homedns/jwt_secrets/jwt_subjects.yaml
sudo chmod 770 -R /etc/homedns/jwt_secrets

# We want our service to be able to listen on port (443, and 53)
sudo setcap 'cap_net_bind_service=+ep' $(which homedns-server)
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