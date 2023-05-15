# Local Dev Config

Use the following configuration to locally run and test the OTEL demo:

- For additional help go [here](https://opensearch.org/docs/latest/install-and-configure/install-opensearch/docker/)

### Raise your host's ulimits:
Rais the upper liits for OpenSearch to be able handling high I/O :

`sudo sysctl -w vm.max_map_count=512000`

### Map domain name to local dns

run the [following script](add_hosts_locally.sh) to map the docker-compose service names to your local dns

```text
# The hostname you want to associate with the IP address

OPENSEARCH_HOST="opensearch-node1"
OPENSEARCH_DASHBOARD="opensearch-dashboards"
OTEL_STORE="frontend"
OTEL_LOADER="loadgenerator"
PROMETHEUS="prometheus"

# Add the entry to the /etc/hosts file

echo "$IP    $OPENSEARCH_HOST" | sudo tee -a /etc/hosts
echo "$IP    $OPENSEARCH_DASHBOARD" | sudo tee -a /etc/hosts
echo "$IP    $OTEL_STORE" | sudo tee -a /etc/hosts
echo "$IP    $PROMETHEUS" | sudo tee -a /etc/hosts
echo "$IP    $OTEL_LOADER" | sudo tee -a /etc/hosts

```