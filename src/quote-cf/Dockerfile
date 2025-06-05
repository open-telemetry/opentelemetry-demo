FROM lucee/lucee:6.1.0.175-BETA

# Provide test page by creating the directory and copying files
RUN mkdir -p /var/www
COPY www/ /var/www/

# copy a custom lucee config in place
COPY lucee-config.json /opt/lucee/server/lucee-server/context/.CFConfig.json

# Create directory for extensions and copy them
RUN mkdir -p /opt/lucee/extensions
COPY extensions/ /opt/lucee/extensions/

# add FR
RUN mkdir -p /opt/fusionreactor

# Download FusionReactor files
ADD https://download.fusionreactor.io/FR/Latest/fusionreactor.jar /opt/fusionreactor/fusionreactor.jar
ADD https://download.fusionreactor.io/FR/Latest/libfrjvmti_x64.so /opt/fusionreactor/libfrjvmti_x64.so

# Set FusionReactor Java options
ENV LUCEE_JAVA_OPTS="-javaagent:/opt/fusionreactor/fusionreactor.jar=name=otlp-lucee-fr,address=8088 -agentpath:/opt/fusionreactor/libfrjvmti_x64.so"

# Expose FusionReactor web interface
EXPOSE 8088
