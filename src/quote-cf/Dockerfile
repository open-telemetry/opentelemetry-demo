FROM lucee/lucee:6.1.0.175-BETA

# Provide test page by creating the directory and copying files
RUN mkdir -p /var/www
COPY www/ /var/www/

# No longer using SQLite - MySQL connection will be external

# copy a custom lucee config in place
COPY lucee-config.json /opt/lucee/server/lucee-server/context/.CFConfig.json

# Create directory for extensions and copy them
RUN mkdir -p /opt/lucee/extensions
COPY extensions/ /opt/lucee/extensions/

# Download MySQL JDBC driver for database connectivity
RUN mkdir -p /opt/lucee/server/lucee-server/context/lib
RUN curl -L https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.33/mysql-connector-java-8.0.33.jar -o /opt/lucee/server/lucee-server/context/lib/mysql-connector-java-8.0.33.jar
# Download Bugsnag Java SDK and its runtime dependencies
RUN mkdir -p /var/www/lib
RUN curl -L https://repo1.maven.org/maven2/com/bugsnag/bugsnag/3.7.1/bugsnag-3.7.1.jar \
        -o /var/www/lib/bugsnag-3.7.1.jar && \
    curl -L https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-databind/2.14.1/jackson-databind-2.14.1.jar \
        -o /var/www/lib/jackson-databind-2.14.1.jar && \
    curl -L https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-core/2.14.1/jackson-core-2.14.1.jar \
        -o /var/www/lib/jackson-core-2.14.1.jar && \
    curl -L https://repo1.maven.org/maven2/com/fasterxml/jackson/core/jackson-annotations/2.14.1/jackson-annotations-2.14.1.jar \
        -o /var/www/lib/jackson-annotations-2.14.1.jar && \
    curl -L https://repo1.maven.org/maven2/org/slf4j/slf4j-api/1.7.25/slf4j-api-1.7.25.jar \
        -o /var/www/lib/slf4j-api-1.7.25.jar

# add FusionReactor
RUN mkdir -p /opt/fusionreactor/conf

# Copy FusionReactor configuration
COPY fusionreactor-conf/ /opt/fusionreactor/conf/

# Download FusionReactor jar (architecture-independent)
ADD https://download.fusionreactor.io/FR/Latest/fusionreactor.jar /opt/fusionreactor/fusionreactor.jar

# Download architecture-specific FusionReactor native library
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        curl -L https://download.fusionreactor.io/FR/Latest/libfrjvmti_x64.so -o /opt/fusionreactor/libfrjvmti.so; \
    elif [ "$ARCH" = "aarch64" ]; then \
        curl -L https://download.fusionreactor.io/FR/Latest/libfrjvmti_aarch64.so -o /opt/fusionreactor/libfrjvmti.so; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi

# Set FusionReactor Java options - let JVM auto-detect heap size from container limits
ENV LUCEE_JAVA_OPTS="-javaagent:/opt/fusionreactor/fusionreactor.jar=name=quote-service-lucee,address=8088 -agentpath:/opt/fusionreactor/libfrjvmti.so"

# Expose FusionReactor web interface
EXPOSE 8088
