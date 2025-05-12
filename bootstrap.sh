# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

sudo docker run hello-world

groups
sudo usermod -aG docker ubuntu
newgrp docker
groups


# Install kubectl

sudo apt-get update
# apt-transport-https may be a dummy package; if so, you can skip that package
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg


curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.33/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
sudo chmod 644 /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.33/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo chmod 644 /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubectl


# Install Terraform

sudo apt-get update && sudo apt-get install -y gnupg software-properties-common
wget -O- https://apt.releases.hashicorp.com/gpg | \
gpg --dearmor | \
sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null


gpg --no-default-keyring \
--keyring /usr/share/keyrings/hashicorp-archive-keyring.gpg \
--fingerprint

echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" | \
sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update
sudo apt-get install terraform




# 1. Validate & view your compose file
docker compose config

# 2. Build images defined in docker-compose.yml
docker compose build
# or rebuild without cache:
docker compose build --no-cache

# 3. Start all services
docker compose up
# in the background (detached):
docker compose up -d

# 4. Stop and remove containers, networks, volumes
docker compose down
# also remove named volumes
docker compose down --volumes

# 5. List running services
docker compose ps

# 6. View service logs
# all services, follow output
docker compose logs -f
# only one service
docker compose logs -f <service-name>

# 7. Run a one‑off command in a service container
docker compose run <service-name> <command>
# e.g., open a shell
docker compose run frontend sh

# 8. Execute a command in a running container
docker compose exec <service-name> <command>
# e.g., open a bash shell
docker compose exec frontend bash

# 9. Pull updated images from registry
docker compose pull

# 10. Push built images to registry
docker compose push

# 11. Show images for your services
docker compose images

# 12. View or filter port mappings
docker compose port <service-name> <container-port>

# 13. Scale a service (override “replicas” in docker‑compose.yml)
docker compose up -d --scale <service>=<count>
