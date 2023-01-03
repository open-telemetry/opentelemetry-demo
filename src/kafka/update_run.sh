#!/bin/sh

# https://github.com/confluentinc/learn-kafka-kraft/blob/4c75598779c4a993464f6979dc0d702552df8f3b/kraft/scripts/update_run.sh

# Docker workaround: Remove check for KAFKA_ZOOKEEPER_CONNECT parameter
sed -i '/KAFKA_ZOOKEEPER_CONNECT/d' /etc/confluent/docker/configure

# Docker workaround: Remove check for KAFKA_ADVERTISED_LISTENERS parameter
sed -i '/dub ensure KAFKA_ADVERTISED_LISTENERS/d' /etc/confluent/docker/configure

# Docker workaround: Ignore cub zk-ready
sed -i 's/cub zk-ready/echo ignore zk-ready/' /etc/confluent/docker/ensure

# KRaft required step: Format the storage directory with a new cluster ID
echo "kafka-storage format --ignore-formatted -t $(cat /tmp/clusterID) -c /etc/kafka/kafka.properties" >> /etc/confluent/docker/ensure
