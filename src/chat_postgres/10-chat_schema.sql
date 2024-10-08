-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE public.messages (
    topic character varying(255),
    name character varying(255),
    message character varying(255),
    sent_at timestamp(0) without time zone,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);

