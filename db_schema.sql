--
-- PostgreSQL database dump
--

-- Dumped from database version 15.14 (Debian 15.14-0+deb12u1)
-- Dumped by pg_dump version 15.14 (Debian 15.14-0+deb12u1)

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

--
-- Name: log_inventario_changes(); Type: FUNCTION; Schema: public; Owner: togru_user
--

CREATE FUNCTION public.log_inventario_changes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    username TEXT;
BEGIN
    -- Recupera il nome utente dalla variabile di sessione
    username := current_setting('application_name', true);

    -- Log INSERT
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO inventario_audit (
            operation_type, record_id, new_data, executed_by
        ) VALUES (
            'INSERT', NEW.id, to_jsonb(NEW), username
        );
        RETURN NEW;
    END IF;

    -- Log UPDATE
    IF (TG_OP = 'UPDATE') THEN
        INSERT INTO inventario_audit (
            operation_type, record_id, old_data, new_data, executed_by
        ) VALUES (
            'UPDATE', NEW.id, to_jsonb(OLD), to_jsonb(NEW), username
        );
        RETURN NEW;
    END IF;

    -- Log DELETE
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO inventario_audit (
            operation_type, record_id, old_data, executed_by
        ) VALUES (
            'DELETE', OLD.id, to_jsonb(OLD), username
        );
        RETURN OLD;
    END IF;

    RETURN NULL;
END;
$$;


ALTER FUNCTION public.log_inventario_changes() OWNER TO togru_user;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: inventario; Type: TABLE; Schema: public; Owner: togru_user
--

CREATE TABLE public.inventario (
    id integer NOT NULL,
    descrizione_inventario text,
    num_inventario text,
    num_inventario_ateneo text,
    data_carico text,
    descrizione_bene text,
    codice_sipi_torino text,
    codice_sipi_grugliasco text,
    destinazione text,
    rosso_fase_alimentazione_privilegiata boolean,
    valore_convenzionale text,
    esercizio_bene_migrato text,
    responsabile_laboratorio text,
    denominazione_fornitore text,
    anno_fabbricazione text,
    numero_seriale text,
    categoria_inventoriale text,
    catalogazione_materiale_strumentazione text,
    peso text,
    dimensioni text,
    ditta_costruttrice_fornitrice text,
    note text,
    deleted timestamp without time zone,
    microscopia boolean DEFAULT false,
    catena_del_freddo boolean DEFAULT false,
    alta_specialistica boolean DEFAULT false,
    da_movimentare boolean DEFAULT false,
    trasporto_in_autonomia boolean DEFAULT false,
    da_disinventariare boolean DEFAULT false,
    didattica boolean DEFAULT false,
    quantita integer DEFAULT 1
);


ALTER TABLE public.inventario OWNER TO togru_user;

--
-- Name: inventario_audit; Type: TABLE; Schema: public; Owner: togru_user
--

CREATE TABLE public.inventario_audit (
    id integer NOT NULL,
    operation_type text NOT NULL,
    record_id integer,
    old_data jsonb,
    new_data jsonb,
    executed_by text,
    executed_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.inventario_audit OWNER TO togru_user;

--
-- Name: inventario_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: togru_user
--

CREATE SEQUENCE public.inventario_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.inventario_audit_id_seq OWNER TO togru_user;

--
-- Name: inventario_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: togru_user
--

ALTER SEQUENCE public.inventario_audit_id_seq OWNED BY public.inventario_audit.id;


--
-- Name: inventario_id_seq; Type: SEQUENCE; Schema: public; Owner: togru_user
--

CREATE SEQUENCE public.inventario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.inventario_id_seq OWNER TO togru_user;

--
-- Name: inventario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: togru_user
--

ALTER SEQUENCE public.inventario_id_seq OWNED BY public.inventario.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: togru_user
--

CREATE TABLE public.users (
    email text,
    admin boolean
);


ALTER TABLE public.users OWNER TO togru_user;

--
-- Name: inventario id; Type: DEFAULT; Schema: public; Owner: togru_user
--

ALTER TABLE ONLY public.inventario ALTER COLUMN id SET DEFAULT nextval('public.inventario_id_seq'::regclass);


--
-- Name: inventario_audit id; Type: DEFAULT; Schema: public; Owner: togru_user
--

ALTER TABLE ONLY public.inventario_audit ALTER COLUMN id SET DEFAULT nextval('public.inventario_audit_id_seq'::regclass);


--
-- Name: inventario_audit inventario_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: togru_user
--

ALTER TABLE ONLY public.inventario_audit
    ADD CONSTRAINT inventario_audit_pkey PRIMARY KEY (id);


--
-- Name: inventario inventario_pkey; Type: CONSTRAINT; Schema: public; Owner: togru_user
--

ALTER TABLE ONLY public.inventario
    ADD CONSTRAINT inventario_pkey PRIMARY KEY (id);


--
-- Name: inventario_responsabile_idx; Type: INDEX; Schema: public; Owner: togru_user
--

CREATE INDEX inventario_responsabile_idx ON public.inventario USING btree (responsabile_laboratorio);


--
-- Name: inventario_sipi_torino_idx; Type: INDEX; Schema: public; Owner: togru_user
--

CREATE INDEX inventario_sipi_torino_idx ON public.inventario USING btree (codice_sipi_torino);


--
-- Name: inventario inventario_audit_trigger; Type: TRIGGER; Schema: public; Owner: togru_user
--

CREATE TRIGGER inventario_audit_trigger AFTER INSERT OR DELETE OR UPDATE ON public.inventario FOR EACH ROW EXECUTE FUNCTION public.log_inventario_changes();


--
-- PostgreSQL database dump complete
--

