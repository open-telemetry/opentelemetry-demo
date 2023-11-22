# Declare a build argument for the version
ARG OPENSEARCH_VERSION

# Use OpenSearch image as base
FROM opensearchproject/opensearch-dashboards:${OPENSEARCH_VERSION}

# Install custom observabilityDashboards plugin

COPY observabilityDashboards-2.11.0.zip /tmp

RUN /usr/share/opensearch-dashboards/bin/opensearch-dashboards-plugin remove observabilityDashboards
RUN /usr/share/opensearch-dashboards/bin/opensearch-dashboards-plugin list
RUN /usr/share/opensearch-dashboards/bin/opensearch-dashboards-plugin install file:///tmp/observabilityDashboards-2.11.0.zip

# Switch back to opensearch user
USER opensearch-dashboards