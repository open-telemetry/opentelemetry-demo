-- Copyright The OpenTelemetry Authors
-- SPDX-License-Identifier: Apache-2.0

CREATE TABLE IF NOT EXISTS public.featureflags (
    name character varying(255),
    description character varying(255),
    enabled double precision DEFAULT 0.0 NOT NULL
);

ALTER TABLE ONLY public.featureflags DROP CONSTRAINT IF EXISTS featureflags_pkey;
ALTER TABLE ONLY public.featureflags ADD CONSTRAINT featureflags_pkey PRIMARY KEY (name);

CREATE UNIQUE INDEX IF NOT EXISTS featureflags_name_index ON public.featureflags USING btree (name);

