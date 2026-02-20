# --- Bugsnag dependency resolution ---
FROM maven:3.9-eclipse-temurin-17-alpine AS bugsnag-deps
WORKDIR /deps
RUN printf '<project><modelVersion>4.0.0</modelVersion>\
<groupId>temp</groupId><artifactId>temp</artifactId><version>1</version>\
<dependencies><dependency><groupId>com.bugsnag</groupId>\
<artifactId>bugsnag</artifactId><version>3.7.1</version></dependency>\
</dependencies></project>' > pom.xml
RUN mvn dependency:copy-dependencies -DoutputDirectory=/bugsnag-jars \
    -DincludeScope=runtime -q

# --- Lucee stage ---
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
RUN mkdir -p /var/www/lib
COPY --from=bugsnag-deps /bugsnag-jars/ /var/www/lib/

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
