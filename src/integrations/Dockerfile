FROM alpine:latest

RUN apk update && apk add curl netcat-openbsd

COPY install-observability.sh /install-observability.sh
RUN chmod +x /install-observability.sh

CMD /install-observability.sh
