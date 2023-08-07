FROM openjdk:17-buster

RUN apt-get update -y; apt-get install curl -y

WORKDIR /home/otel
RUN curl -Lo opentelemetry-javaagent.jar https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar
COPY ./src/orderproducerservice/ orderproducerservice/
WORKDIR /home/otel/orderproducerservice
COPY ./pb/ ./app/src/main/proto/
RUN ./gradlew shadowJar

ENV JAVA_TOOL_OPTIONS="-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=opentelemetry-demo-orderproducer -Dcom.sun.management.jmxremote.port=1097 -Dcom.sun.management.jmxremote.rmi.port=1097"
ENV JMX_PORT=1097

ENTRYPOINT ["java","-javaagent:../opentelemetry-javaagent.jar",  "-jar" , "app/build/libs/app-all.jar"]
