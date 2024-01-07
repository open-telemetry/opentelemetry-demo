--
-- PostgreSQL database dump
--

-- Dumped from database version 16.1 (Debian 16.1-1.pgdg120+1)
-- Dumped by pg_dump version 16.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: featureflags; Type: TABLE; Schema: public; Owner: ffs
--

CREATE TABLE public.featureflags (
    id bigint NOT NULL,
    name character varying(255),
    description character varying(255),
    enabled double precision DEFAULT 0.0 NOT NULL,
    inserted_at timestamp(0) without time zone NOT NULL,
    updated_at timestamp(0) without time zone NOT NULL
);


ALTER TABLE public.featureflags OWNER TO ffs;

--
-- Name: featureflags_id_seq; Type: SEQUENCE; Schema: public; Owner: ffs
--

CREATE SEQUENCE public.featureflags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.featureflags_id_seq OWNER TO ffs;

--
-- Name: featureflags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ffs
--

ALTER SEQUENCE public.featureflags_id_seq OWNED BY public.featureflags.id;


ALTER TABLE public.schema_migrations OWNER TO ffs;

--
-- Name: featureflags id; Type: DEFAULT; Schema: public; Owner: ffs
--

ALTER TABLE ONLY public.featureflags ALTER COLUMN id SET DEFAULT nextval('public.featureflags_id_seq'::regclass);


--
-- Data for Name: featureflags; Type: TABLE DATA; Schema: public; Owner: ffs
--

COPY public.featureflags (id, name, description, enabled, inserted_at, updated_at) FROM stdin;
1	productCatalogFailure	Fail product catalog service on a specific product	0	2024-01-07 20:06:29	2024-01-07 20:06:29
2	recommendationCache	Cache recommendations	0	2024-01-07 20:06:29	2024-01-07 20:06:29
3	adServiceFailure	Fail ad service requests sporadically	0	2024-01-07 20:06:29	2024-01-07 20:06:29
4	cartServiceFailure	Fail cart service requests sporadically	0	2024-01-07 20:06:29	2024-01-07 20:06:29
\.


--
-- Name: featureflags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ffs
--

SELECT pg_catalog.setval('public.featureflags_id_seq', 4, true);


--
-- Name: featureflags featureflags_pkey; Type: CONSTRAINT; Schema: public; Owner: ffs
--

ALTER TABLE ONLY public.featureflags
    ADD CONSTRAINT featureflags_pkey PRIMARY KEY (id);


--
-- Name: featureflags_name_index; Type: INDEX; Schema: public; Owner: ffs
--

CREATE UNIQUE INDEX featureflags_name_index ON public.featureflags USING btree (name);


--
-- PostgreSQL database dump complete
--

