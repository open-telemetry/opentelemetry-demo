FROM lucee/lucee:6.1.0.175-BETA

# Provide test page by creating the directory and copying files
RUN mkdir -p /var/www
COPY www/ /var/www/

# Create data directory and initialize SQLite database
RUN mkdir -p /data
COPY sql/quotes_sqlite.sql /tmp/quotes_sqlite.sql
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*
RUN sqlite3 /data/quotes.db < /tmp/quotes_sqlite.sql && rm /tmp/quotes_sqlite.sql
RUN chmod 666 /data/quotes.db && chmod 777 /data

# copy a custom lucee config in place
COPY lucee-config.json /opt/lucee/server/lucee-server/context/.CFConfig.json

# Create directory for extensions and copy them
RUN mkdir -p /opt/lucee/extensions
COPY extensions/ /opt/lucee/extensions/

# Download SQLite JDBC driver for database connectivity
RUN mkdir -p /opt/lucee/server/lucee-server/context/lib
RUN curl -L https://repo1.maven.org/maven2/org/xerial/sqlite-jdbc/3.45.1.0/sqlite-jdbc-3.45.1.0.jar -o /opt/lucee/server/lucee-server/context/lib/sqlite-jdbc-3.45.1.0.jar

# add FR
RUN mkdir -p /opt/fusionreactor

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

# Set FusionReactor Java options with increased timeouts and heap size
ENV LUCEE_JAVA_OPTS="-Xmx1524m -Xms768m -javaagent:/opt/fusionreactor/fusionreactor.jar=name=quote-service-lucee,address=8088 -agentpath:/opt/fusionreactor/libfrjvmti.so"

# Expose FusionReactor web interface
EXPOSE 8088
