#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import ssl
import threading
import time
from urllib.parse import urlparse, urlunparse

import websocket
from opentelemetry._opamp import OpAMPAgent, OpAMPCallbacks, OpAMPClient
from opentelemetry._opamp import messages
from opentelemetry._opamp.proto import opamp_pb2
from opentelemetry._opamp.transport.base import HttpTransport
from opentelemetry.sdk.resources import Resource

OPAMP_SERVER_ENDPOINT_ENV = "OPAMP_SERVER_ENDPOINT"
OPAMP_SERVER_TLS_INSECURE_SKIP_VERIFY_ENV = "OPAMP_SERVER_TLS_INSECURE_SKIP_VERIFY"

IDENTIFYING_KEYS = {
    "service.name",
    "service.instance.id",
    "service.namespace",
}

CAPABILITIES = (
    opamp_pb2.AgentCapabilities.AgentCapabilities_ReportsStatus
    | opamp_pb2.AgentCapabilities.AgentCapabilities_ReportsHeartbeat
    | opamp_pb2.AgentCapabilities.AgentCapabilities_ReportsHealth
)


class HealthReportingOpAMPClient(OpAMPClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_time_unix_nano = time.time_ns()

    def build_full_state_message(self) -> bytes:
        message = opamp_pb2.AgentToServer(
            instance_uid=self._instance_uid,
            sequence_num=self._sequence_num,
            agent_description=self._agent_description,
            capabilities=CAPABILITIES,
            health=self._component_health(),
        )
        return message.SerializeToString()

    def build_heartbeat_message(self) -> bytes:
        message = opamp_pb2.AgentToServer(
            instance_uid=self._instance_uid,
            sequence_num=self._sequence_num,
            capabilities=CAPABILITIES,
            health=self._component_health(),
        )
        return message.SerializeToString()

    def build_agent_disconnect_message(self) -> bytes:
        message = opamp_pb2.AgentToServer(
            instance_uid=self._instance_uid,
            sequence_num=self._sequence_num,
            capabilities=CAPABILITIES,
            agent_disconnect=opamp_pb2.AgentDisconnect(),
        )
        return message.SerializeToString()

    def _component_health(self):
        return opamp_pb2.ComponentHealth(
            healthy=True,
            start_time_unix_nano=self._start_time_unix_nano,
            status="OK",
            status_time_unix_nano=time.time_ns(),
        )


class WebSocketTransport(HttpTransport):
    def __init__(self):
        self._socket = None
        self._lock = threading.Lock()

    def send(
        self,
        *,
        url,
        headers,
        data,
        timeout_millis,
        tls_certificate,
        tls_client_certificate=None,
        tls_client_key=None,
    ):
        with self._lock:
            try:
                if self._socket is None or not self._socket.connected:
                    self._socket = websocket.create_connection(
                        _websocket_url(url),
                        header=_websocket_headers(headers),
                        timeout=timeout_millis / 1e3,
                        sslopt=_ssl_options(tls_certificate),
                    )

                self._socket.send(
                    b"\x00" + data, opcode=websocket.ABNF.OPCODE_BINARY
                )
                response = self._socket.recv()
            except (OSError, websocket.WebSocketException):
                self._reset_socket()
                raise

            if not isinstance(response, bytes):
                self._reset_socket()
                raise ValueError(
                    "OpAMP server returned a non-binary WebSocket message"
                )

            if response.startswith(b"\x00"):
                response = response[1:]

            return messages.decode_message(response)

    def _reset_socket(self):
        socket = self._socket
        self._socket = None
        if socket is None:
            return

        try:
            socket.close()
        except (OSError, websocket.WebSocketException):
            logging.debug("Failed to close OpAMP WebSocket", exc_info=True)


def start_opamp_agent() -> OpAMPAgent | None:
    endpoint = os.environ.get(OPAMP_SERVER_ENDPOINT_ENV)
    if endpoint is None:
        return None

    try:
        skip_tls_certificate_verification = _parse_bool_env(
            OPAMP_SERVER_TLS_INSECURE_SKIP_VERIFY_ENV
        )
    except ValueError as error:
        logging.error("OpAMP client disabled: %s", error)
        return None

    identifying_attributes, non_identifying_attributes = _resource_attributes()
    client = HealthReportingOpAMPClient(
        endpoint=endpoint,
        agent_identifying_attributes=identifying_attributes,
        agent_non_identifying_attributes=non_identifying_attributes,
        transport=WebSocketTransport(),
        tls_certificate=not skip_tls_certificate_verification,
    )
    agent = OpAMPAgent(
        interval=30,
        callbacks=OpAMPCallbacks(),
        client=client,
    )
    agent.start()
    logging.info("Started OpAMP client")
    return agent


def stop_opamp_agent(agent: OpAMPAgent | None) -> None:
    if agent is None:
        return

    agent.stop(timeout=5)
    logging.info("Stopped OpAMP client")


def _resource_attributes():
    attributes = Resource.create({}).attributes
    identifying_attributes = {}
    non_identifying_attributes = {}
    for key, value in attributes.items():
        if value is None:
            continue

        attrs = (
            identifying_attributes
            if key in IDENTIFYING_KEYS
            else non_identifying_attributes
        )
        attrs[key] = value

    return identifying_attributes, non_identifying_attributes


def _parse_bool_env(key):
    value = os.environ.get(key)
    if value is None:
        return False

    normalized = value.lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False

    raise ValueError(f"{key} must be a boolean")


def _websocket_url(url):
    parsed = urlparse(url)
    scheme = {"https": "wss", "http": "ws"}.get(parsed.scheme, parsed.scheme)
    return urlunparse(parsed._replace(scheme=scheme))


def _websocket_headers(headers):
    return {
        key: value
        for key, value in headers.items()
        if key.lower() != "content-type"
    }


def _ssl_options(tls_certificate):
    if tls_certificate is False:
        return {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
    if isinstance(tls_certificate, str):
        return {
            "cert_reqs": ssl.CERT_REQUIRED,
            "ca_certs": tls_certificate,
        }

    return {}
