#!/bin/sh

if [ -n "$http_proxy" ]
then
  host=$(echo $http_proxy | awk -F'[/:]' '{print $4}')
  port=$(echo $http_proxy | awk -F'[/:]' '{print $5}')

  echo "systemProp.http.proxyHost=$host" >> gradle.properties
  echo "systemProp.http.proxyPort=$port" >> gradle.properties
fi

if [ -n "$https_proxy" ]
then
  host=$(echo $https_proxy | awk -F'[/:]' '{print $4}')
  port=$(echo $https_proxy | awk -F'[/:]' '{print $5}')

  echo "systemProp.https.proxyHost=$host" >> gradle.properties
  echo "systemProp.https.proxyPort=$port" >> gradle.properties
fi
