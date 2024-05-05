#!/bin/bash
# Install the Updater Service (Dynamic DNS Updates)
set -e # fail on first error
if ! command -v homedns-updater &> /dev/null
then
    echo "homedns-updater is not installed or not on the path, please install homedns first"
    exit 1
fi

# Create system account and group
sudo useradd -r homedns || true
sudo groupadd -f homedns

# Create default config and directories
sudo mkdir -p /etc/homedns/updater
sudo mkdir -p /etc/homedns/updater
sudo cp --no-clobber service/updater_config.yaml /etc/homedns/updater/config.yaml
if [[ ! -e /etc/homedns/updater/jwt_key.pem ]]; then
    mkdir -p /Scripts
    sudo touch /etc/homedns/updater/jwt_key.pem
fi

# Directory and file permissions
sudo chown -R homedns:homedns /etc/homedns/updater
sudo chmod 644 -R /etc/homedns/updater/config.yaml
sudo chmod 640 /etc/homedns/updater/jwt_key.pem
sudo chmod 650 -R /etc/homedns/updater

sudo cp service/homedns-updater.service /etc/systemd/system/
sudo chown root:root /etc/systemd/system/homedns-updater.service
sudo chmod 644 /etc/systemd/system/homedns-updater.service
sudo systemctl daemon-reload
sudo systemctl enable homedns-updater.service
sudo systemctl start homedns-updater.service
sudo journalctl -n 100 -u homedns-updater

echo "Service created: 'homedns-updater'"
echo "  status: systemctl status homedns-updater"
echo "Done!"