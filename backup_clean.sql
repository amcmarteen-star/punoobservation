--
-- PostgreSQL database dump
--


-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--



--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: 
--



SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: location; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.location (
    location_id integer NOT NULL,
    psgc_code character varying(20),
    region character varying(100) NOT NULL,
    province character varying(100) NOT NULL,
    municipality character varying(100) NOT NULL,
    barangay character varying(100) NOT NULL,
    latitude double precision,
    longitude double precision,
    elevation_m double precision,
    avg_temp_c double precision,
    annual_rainfall_mm double precision,
    soil_type character varying(100),
    soil_texture character varying(50),
    agro_ecological_zone character varying(50),
    coastal_exposure integer
);


ALTER TABLE public.location OWNER TO postgres;

--
-- Name: location_location_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.location_location_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.location_location_id_seq OWNER TO postgres;

--
-- Name: location_location_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.location_location_id_seq OWNED BY public.location.location_id;


--
-- Name: monitoring_photo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.monitoring_photo (
    photo_id integer NOT NULL,
    report_id integer NOT NULL,
    photo_url character varying(255) NOT NULL,
    date_time_taken timestamp without time zone,
    upload_time timestamp without time zone NOT NULL,
    inside_boundary boolean NOT NULL,
    plot_id integer,
    file_hash character varying(64),
    photo_type character varying(20) NOT NULL,
    latitude double precision,
    longitude double precision,
    distance_from_centroid_m double precision,
    flags character varying(300)
);


ALTER TABLE public.monitoring_photo OWNER TO postgres;

--
-- Name: monitoring_photo_photo_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.monitoring_photo_photo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.monitoring_photo_photo_id_seq OWNER TO postgres;

--
-- Name: monitoring_photo_photo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.monitoring_photo_photo_id_seq OWNED BY public.monitoring_photo.photo_id;


--
-- Name: monitoring_plot; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.monitoring_plot (
    plot_id integer NOT NULL,
    report_id integer NOT NULL,
    plot_number integer NOT NULL,
    seedlings_alive integer NOT NULL,
    plot_notes character varying(300),
    latitude double precision,
    longitude double precision
);


ALTER TABLE public.monitoring_plot OWNER TO postgres;

--
-- Name: monitoring_plot_plot_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.monitoring_plot_plot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.monitoring_plot_plot_id_seq OWNER TO postgres;

--
-- Name: monitoring_plot_plot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.monitoring_plot_plot_id_seq OWNED BY public.monitoring_plot.plot_id;


--
-- Name: monitoring_report; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.monitoring_report (
    report_id integer NOT NULL,
    record_id integer NOT NULL,
    user_id integer NOT NULL,
    monitoring_date date NOT NULL,
    survival_rate double precision NOT NULL,
    record_version integer NOT NULL,
    approval_status character varying(30) NOT NULL,
    site_id integer,
    plots_recorded integer,
    plot_size_sqm double precision,
    total_counted integer,
    mean_per_plot double precision,
    stdev_per_plot double precision,
    density_per_ha double precision,
    estimated_survivors integer,
    sampling_intensity double precision,
    captured_area_ha double precision,
    area_difference_pct double precision,
    boundary_geojson text,
    remarks text,
    review_note text,
    reviewed_by integer,
    date_reviewed timestamp without time zone,
    submitted_at timestamp without time zone NOT NULL
);


ALTER TABLE public.monitoring_report OWNER TO postgres;

--
-- Name: monitoring_report_report_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.monitoring_report_report_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.monitoring_report_report_id_seq OWNER TO postgres;

--
-- Name: monitoring_report_report_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.monitoring_report_report_id_seq OWNED BY public.monitoring_report.report_id;


--
-- Name: notification; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notification (
    notification_id integer NOT NULL,
    user_id integer NOT NULL,
    report_id integer,
    notification_type character varying(100) NOT NULL,
    message text NOT NULL,
    is_read boolean NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.notification OWNER TO postgres;

--
-- Name: notification_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notification_notification_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notification_notification_id_seq OWNER TO postgres;

--
-- Name: notification_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notification_notification_id_seq OWNED BY public.notification.notification_id;


--
-- Name: organization; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.organization (
    organization_id integer NOT NULL,
    organization_name character varying(150) NOT NULL,
    organization_type character varying(100) NOT NULL
);


ALTER TABLE public.organization OWNER TO postgres;

--
-- Name: organization_organization_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.organization_organization_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.organization_organization_id_seq OWNER TO postgres;

--
-- Name: organization_organization_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.organization_organization_id_seq OWNED BY public.organization.organization_id;


--
-- Name: reforestation_record; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reforestation_record (
    record_id integer NOT NULL,
    site_id integer NOT NULL,
    tree_id integer NOT NULL,
    date_planted date NOT NULL,
    target_quantity integer NOT NULL,
    date_validated date,
    survival_rate double precision,
    actual_quantity_planted integer
);


ALTER TABLE public.reforestation_record OWNER TO postgres;

--
-- Name: reforestation_record_record_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reforestation_record_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reforestation_record_record_id_seq OWNER TO postgres;

--
-- Name: reforestation_record_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reforestation_record_record_id_seq OWNED BY public.reforestation_record.record_id;


--
-- Name: request; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.request (
    request_id integer NOT NULL,
    user_id integer NOT NULL,
    request_type character varying(100) NOT NULL,
    description text,
    status character varying(30) NOT NULL,
    location_id integer,
    proposed_area_ha double precision,
    contact_number character varying(30),
    date_submitted timestamp without time zone NOT NULL,
    date_reviewed timestamp without time zone,
    reviewed_by integer,
    review_note text
);


ALTER TABLE public.request OWNER TO postgres;

--
-- Name: request_request_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.request_request_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.request_request_id_seq OWNER TO postgres;

--
-- Name: request_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.request_request_id_seq OWNED BY public.request.request_id;


--
-- Name: site; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.site (
    site_id integer NOT NULL,
    location_id integer NOT NULL,
    organization_id integer NOT NULL,
    site_name character varying(150) NOT NULL,
    area_size_ha double precision NOT NULL,
    date_established date NOT NULL,
    site_status character varying(50) NOT NULL,
    climate_zone character varying(100),
    soil_type character varying(100),
    site_code character varying(50),
    zone_type character varying(50),
    loa_contract_code character varying(50),
    year_contracted integer,
    area_contracted_ha double precision,
    date_contract_executed date,
    date_contract_expiry date,
    project_cost_3yr numeric(12,2),
    retention_fee_amount_paid numeric(12,2),
    retention_fee_date_paid date,
    amount_under_land_improvement numeric(12,2),
    amount_still_in_cip numeric(12,2),
    penro character varying(100),
    cenro character varying(100),
    congressional_district character varying(20),
    land_classification character varying(50),
    major_land_use character varying(200),
    contact_person character varying(120),
    component character varying(100),
    commodity character varying(200),
    boundary_geojson text,
    boundary_area_ha double precision,
    boundary_captured_at timestamp without time zone
);


ALTER TABLE public.site OWNER TO postgres;

--
-- Name: site_site_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.site_site_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.site_site_id_seq OWNER TO postgres;

--
-- Name: site_site_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.site_site_id_seq OWNED BY public.site.site_id;


--
-- Name: tree_specie; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tree_specie (
    tree_id integer NOT NULL,
    specie_name character varying(100) NOT NULL,
    scientific_name character varying(150),
    native_to character varying(100),
    min_rainfall_mm double precision,
    max_rainfall_mm double precision,
    min_elevation_m double precision,
    max_elevation_m double precision,
    min_temp_c double precision,
    max_temp_c double precision,
    preferred_soil character varying(200),
    source character varying(300),
    is_reference boolean DEFAULT false NOT NULL,
    salinity_requirement integer
);


ALTER TABLE public.tree_specie OWNER TO postgres;

--
-- Name: tree_specie_tree_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tree_specie_tree_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tree_specie_tree_id_seq OWNER TO postgres;

--
-- Name: tree_specie_tree_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tree_specie_tree_id_seq OWNED BY public.tree_specie.tree_id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    organization_id integer,
    username character varying(80) NOT NULL,
    email_address character varying(120) NOT NULL,
    password_hash character varying(200) NOT NULL,
    role character varying(20) NOT NULL,
    CONSTRAINT users_role_check CHECK (((role)::text = ANY ((ARRAY['admin'::character varying, 'field_officer'::character varying, 'normal_user'::character varying])::text[])))
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_user_id_seq OWNER TO postgres;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: location location_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.location ALTER COLUMN location_id SET DEFAULT nextval('public.location_location_id_seq'::regclass);


--
-- Name: monitoring_photo photo_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_photo ALTER COLUMN photo_id SET DEFAULT nextval('public.monitoring_photo_photo_id_seq'::regclass);


--
-- Name: monitoring_plot plot_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_plot ALTER COLUMN plot_id SET DEFAULT nextval('public.monitoring_plot_plot_id_seq'::regclass);


--
-- Name: monitoring_report report_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report ALTER COLUMN report_id SET DEFAULT nextval('public.monitoring_report_report_id_seq'::regclass);


--
-- Name: notification notification_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification ALTER COLUMN notification_id SET DEFAULT nextval('public.notification_notification_id_seq'::regclass);


--
-- Name: organization organization_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.organization ALTER COLUMN organization_id SET DEFAULT nextval('public.organization_organization_id_seq'::regclass);


--
-- Name: reforestation_record record_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reforestation_record ALTER COLUMN record_id SET DEFAULT nextval('public.reforestation_record_record_id_seq'::regclass);


--
-- Name: request request_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.request ALTER COLUMN request_id SET DEFAULT nextval('public.request_request_id_seq'::regclass);


--
-- Name: site site_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.site ALTER COLUMN site_id SET DEFAULT nextval('public.site_site_id_seq'::regclass);


--
-- Name: tree_specie tree_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tree_specie ALTER COLUMN tree_id SET DEFAULT nextval('public.tree_specie_tree_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
79a7f9dce1f9
\.


--
-- Data for Name: location; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.location (location_id, psgc_code, region, province, municipality, barangay, latitude, longitude, elevation_m, avg_temp_c, annual_rainfall_mm, soil_type, soil_texture, agro_ecological_zone, coastal_exposure) FROM stdin;
457	\N	Region I	Pangasinan	San Quintin	Gonzalo	15.991667	120.865656	263	25.34	2890.8	Annam clay loam	clay loam	Uplands	0
458	\N	Region I	Pangasinan	San Quintin	Labuan	15.9487	120.73175	45	27.18	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
459	\N	Region I	Pangasinan	San Quintin	Lagasit	15.997458	120.790825	83	26.77	2480.6	Umingan silt loam	silt loam	Lowlands	0
460	\N	Region I	Pangasinan	San Quintin	Lumayao	15.96647	120.74172	51	26.96	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
461	\N	Region I	Pangasinan	San Quintin	Mabini	16.028263	120.855238	1016	20.64	2600.1	Annam clay loam	clay loam	Uplands	0
462	\N	Region I	Pangasinan	San Quintin	Mantacdang	15.958912	120.758682	57	27.04	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
467	\N	Region I	Pangasinan	San Quintin	Ungib	15.978483	120.797767	88	26.73	2606.4	Umingan silt loam	silt loam	Lowlands	0
468	\N	Region I	Pangasinan	Santa Maria	Bal-Loy	15.98052	120.72016	46	26.97	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
469	\N	Region I	Pangasinan	Santa Maria	Bantog	15.96855	120.694417	41	27.13	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
470	\N	Region I	Pangasinan	Santa Maria	Caboluan	15.9653	120.72146	45	26.97	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
471	\N	Region I	Pangasinan	Santa Maria	Cal-Litang	15.948025	120.651612	33	27.11	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
472	\N	Region I	Pangasinan	Santa Maria	Capandanan	15.96148	120.6765	39	27.38	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
473	\N	Region I	Pangasinan	Santa Maria	Cauplasan	15.96159	120.66668	37	27.38	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
474	\N	Region I	Pangasinan	Santa Maria	Dalayap	15.960257	120.697671	43	27.13	2344.7	San Manuel silt loam	silt loam	Lowlands	0
475	\N	Region I	Pangasinan	Santa Maria	Libsong	15.9594	120.72216	45	26.97	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
476	\N	Region I	Pangasinan	Santa Maria	Namagbagan	15.954523	120.683238	39	27.13	2344.7	San Manuel silt loam	silt loam	Lowlands	0
477	\N	Region I	Pangasinan	Santa Maria	Paitan	15.977086	120.671457	42	27.37	2288.8	Pangasinan river sand	sand	Lowlands	0
478	\N	Region I	Pangasinan	Santa Maria	Pataquid	15.969889	120.728856	46	26.97	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
479	\N	Region I	Pangasinan	Santa Maria	Pilar	15.963073	120.650391	35	27.38	2288.8	San Manuel sand	sand	Lowlands	0
482	\N	Region I	Pangasinan	Santa Maria	Pugot	15.981488	120.741825	53	26.95	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
483	\N	Region I	Pangasinan	Santa Maria	Samon	15.94137	120.63935	34	27.1	2469.2	San Manuel sand	sand	Lowlands	0
180	\N	Region I	Pangasinan	San Manuel	Santo Domingo	16.055129	120.6444	56	27.16	2222.9	Umingan sand	sand	Lowlands	0
172	\N	Region I	Pangasinan	San Nicolas	San Felipe East	16.173607	120.706553	281	25.82	2481.8	Annam clay loam	clay loam	Uplands	0
173	\N	Region I	Pangasinan	Sison	Calunetan	16.158371	120.596329	669	22.92	2747.9	Annam clay loam	clay loam	Uplands	0
174	\N	Region I	Pangasinan	San Nicolas	Santa Maria East	16.1137	120.8093	318	25.38	2848.3	Annam clay loam	clay loam	Uplands	0
175	\N	Region I	Pangasinan	San Nicolas	Dalumpinas	16.143956	120.790278	383	24.89	2840.8	Annam clay loam	clay loam	Uplands	0
176	\N	Region I	Pangasinan	Natividad	Cacandungan	16.060467	120.834967	222	25.8	2848.3	Annam clay loam	clay loam	Uplands	0
177	\N	Region I	Pangasinan	San Quintin	Nangapugan	15.98223	120.87086	483	23.99	2628.1	Annam clay loam	clay loam	Uplands	0
178	\N	Region I	Pangasinan	San Manuel	Lapalo	16.144	120.631117	325	25.18	2281.5	Annam clay loam	clay loam	Uplands	0
179	\N	Region I	Pangasinan	San Quintin	Cabangaran	16.01865	120.85517	921	21.28	2548.6	Annam clay loam	clay loam	Uplands	0
181	\N	Region I	Pangasinan	Sison	Alibeng	16.135789	120.613189	421	24.52	2732.4	Annam clay loam	clay loam	Uplands	0
182	\N	Region I	Pangasinan	San Nicolas	Malico	16.143675	120.829375	584	23.66	2840.8	Annam clay loam	clay loam	Uplands	0
183	\N	Region I	Pangasinan	San Nicolas	Fianza	16.1511	120.810767	826	22.42	2611.5	Annam clay loam	clay loam	Uplands	0
184	\N	Region I	Pangasinan	San Nicolas	Salingcob	16.110563	120.776525	243	25.65	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
185	\N	Region I	Pangasinan	San Manuel	San Roque	16.153538	120.682758	341	25.72	2481.8	Pangasinan river sand	sand	Lowlands	0
493	\N	Region I	Pangasinan	Santo Tomas	Salvacion	15.885967	120.58405	31	26.89	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
498	\N	Region I	Pangasinan	Santo Tomas	Santo Domingo	15.866967	120.576133	26	26.9	2561.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
603	\N	Region I	Pangasinan	Urdaneta City	Anonas	16.001314	120.577886	27	26.95	2478.6	San Manuel silty clay loam	silty clay loam	Lowlands	0
605	\N	Region I	Pangasinan	Urdaneta City	Bayaoas	15.977457	120.579443	32	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
606	\N	Region I	Pangasinan	Urdaneta City	Bolaoen	15.99705	120.6132	33	27.35	2260.2	San Manuel sandy loam	sandy loam	Lowlands	0
607	\N	Region I	Pangasinan	Urdaneta City	Cabaruan	15.9476	120.520683	25	26.82	2666.7	San Fabian clay loam	clay loam	Highlands	0
608	\N	Region I	Pangasinan	Urdaneta City	Cabuloan	15.97556	120.5997	37	26.94	2478.6	San Manuel silt loam	silt loam	Lowlands	0
609	\N	Region I	Pangasinan	Urdaneta City	Camanang	15.962029	120.585157	30	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
610	\N	Region I	Pangasinan	Urdaneta City	Camantiles	15.999229	120.545095	25	26.99	2478.6	San Manuel fine sandy loam	sandy loam	Lowlands	0
611	\N	Region I	Pangasinan	Urdaneta City	Casantaan	15.991557	120.6122	31	27.35	2260.2	San Manuel sandy loam	sandy loam	Lowlands	0
612	\N	Region I	Pangasinan	Urdaneta City	Catablan	15.980508	120.493342	16	26.83	2637.1	San Manuel fine sandy loam	sandy loam	Lowlands	0
613	\N	Region I	Pangasinan	Urdaneta City	Cayambanan	16.006733	120.586933	29	26.95	2478.6	San Manuel sandy loam	sandy loam	Lowlands	0
614	\N	Region I	Pangasinan	Urdaneta City	Consolacion	15.96005	120.61695	30	27.02	2440.6	San Manuel sandy loam	sandy loam	Lowlands	0
621	\N	Region I	Pangasinan	Urdaneta City	Nancalobasaan	16.00953	120.60469	32	26.94	2478.6	San Manuel sandy loam	sandy loam	Lowlands	0
624	\N	Region I	Pangasinan	Urdaneta City	Nancayasan	15.961167	120.573378	29	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
625	\N	Region I	Pangasinan	Urdaneta City	Oltama	15.938817	120.506367	32	26.8	2666.7	San Fabian clay loam	clay loam	Highlands	0
628	\N	Region I	Pangasinan	Urdaneta City	Pinmaludpod	15.993575	120.523992	24	26.82	2637.1	San Manuel fine sandy loam	sandy loam	Lowlands	0
629	\N	Region I	Pangasinan	Urdaneta City	Poblacion	15.9788	120.56842	26	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
634	\N	Region I	Pangasinan	Urdaneta City	Sugcong	15.944443	120.541043	27	26.82	2666.7	San Manuel silt loam	silt loam	Lowlands	0
635	\N	Region I	Pangasinan	Urdaneta City	Tipuso	15.974929	120.620657	34	27.35	2260.2	San Manuel sandy loam	sandy loam	Lowlands	0
636	\N	Region I	Pangasinan	Urdaneta City	Tulong	16.005777	120.561831	33	26.94	2478.6	San Manuel silty clay loam	silty clay loam	Lowlands	0
490	\N	Region I	Pangasinan	Santo Tomas	La Luna	15.87796	120.57042	28	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
491	\N	Region I	Pangasinan	Santo Tomas	Poblacion East	15.87785	120.578467	26	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
492	\N	Region I	Pangasinan	Santo Tomas	Poblacion West	15.88046	120.57138	32	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
494	\N	Region I	Pangasinan	Santo Tomas	San Agustin	15.87832	120.5811	30	26.9	2721.2	San Manuel sand	sand	Lowlands	0
495	\N	Region I	Pangasinan	Santo Tomas	San Antonio	15.868183	120.563483	30	26.9	2561.4	San Manuel sand	sand	Lowlands	0
496	\N	Region I	Pangasinan	Santo Tomas	San Jose	15.871317	120.565317	25	26.91	2561.4	San Manuel sand	sand	Lowlands	0
497	\N	Region I	Pangasinan	Santo Tomas	San Marcos	15.8758	120.56836	31	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
212	\N	Region I	Pangasinan	Alcala	Pindangan East	15.86336	120.55856	30	26.89	2561.4	San Manuel sand	sand	Lowlands	0
213	\N	Region I	Pangasinan	Alcala	Pindangan West	15.86882	120.5512	26	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
214	\N	Region I	Pangasinan	Alcala	Poblacion East	15.8475	120.524571	27	26.88	2444.7	San Manuel sand	sand	Lowlands	0
215	\N	Region I	Pangasinan	Alcala	Poblacion West	15.84815	120.528937	28	26.88	2444.7	San Manuel sand	sand	Lowlands	0
216	\N	Region I	Pangasinan	Alcala	San Juan	15.83908	120.52136	23	26.89	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
217	\N	Region I	Pangasinan	Alcala	San Nicolas	15.85454	120.5325	25	26.91	2444.7	San Manuel sand	sand	Lowlands	0
218	\N	Region I	Pangasinan	Alcala	San Pedro Apartado	15.8492	120.56177	21	26.94	2561.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
219	\N	Region I	Pangasinan	Alcala	San Pedro Ili	15.85472	120.53864	27	26.89	2444.7	San Manuel sand	sand	Lowlands	0
220	\N	Region I	Pangasinan	Alcala	San Vicente	15.85475	120.516175	24	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
222	\N	Region I	Pangasinan	Asingan	Ariston Este	16.039	120.69976	54	27.16	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
223	\N	Region I	Pangasinan	Asingan	Ariston Weste	16.031715	120.694769	53	27.16	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
229	\N	Region I	Pangasinan	Asingan	Carosucan Norte	15.979357	120.638829	33	27.35	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
230	\N	Region I	Pangasinan	Asingan	Carosucan Sur	15.96051	120.63873	35	27.34	2288.8	Pangasinan river sand	sand	Lowlands	0
236	\N	Region I	Pangasinan	Asingan	Poblacion East	16.010838	120.672363	48	27.36	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
237	\N	Region I	Pangasinan	Asingan	Poblacion West	16.009167	120.663333	47	27.35	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
238	\N	Region I	Pangasinan	Asingan	San Vicente Este	16.037267	120.669433	53	27.16	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
239	\N	Region I	Pangasinan	Asingan	San Vicente Weste	16.031492	120.6546	46	27.36	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
243	\N	Region I	Pangasinan	Balungao	Angayan Norte	15.911458	120.695	41	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
244	\N	Region I	Pangasinan	Balungao	Angayan Sur	15.90045	120.687892	41	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
253	\N	Region I	Pangasinan	Balungao	San Aurelio 1st	15.902922	120.678267	40	27.2	2344.7	San Manuel silt loam	silt loam	Lowlands	0
254	\N	Region I	Pangasinan	Balungao	San Aurelio 2nd	15.893562	120.6835	43	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
255	\N	Region I	Pangasinan	Balungao	San Aurelio 3rd	15.9173	120.68485	42	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
256	\N	Region I	Pangasinan	Balungao	San Joaquin	15.940943	120.70345	40	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
257	\N	Region I	Pangasinan	Balungao	San Julian	15.9371	120.671417	38	27.2	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
258	\N	Region I	Pangasinan	Balungao	San Leon	15.92285	120.710383	42	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
259	\N	Region I	Pangasinan	Balungao	San Marcelino	15.936125	120.655012	36	27.11	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
260	\N	Region I	Pangasinan	Balungao	San Miguel	15.9276	120.65869	38	27.11	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
261	\N	Region I	Pangasinan	Balungao	San Raymundo	15.926543	120.685443	43	27.2	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
269	\N	Region I	Pangasinan	Bautista	Nibaliw Norte	15.8168	120.468983	24	27.14	2308.8	San Manuel sand	sand	Lowlands	0
270	\N	Region I	Pangasinan	Bautista	Nibaliw Sur	15.8119	120.47082	22	27.13	2308.8	San Manuel sand	sand	Lowlands	0
272	\N	Region I	Pangasinan	Bautista	Poblacion East	15.814113	120.485687	22	27.14	2308.8	San Manuel sand	sand	Lowlands	0
273	\N	Region I	Pangasinan	Bautista	Poblacion West	15.813863	120.477375	21	27.13	2308.8	San Manuel sand	sand	Lowlands	0
291	\N	Region I	Pangasinan	Binalonan	Pasileng Norte	16.041062	120.593238	41	27.05	2209.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
292	\N	Region I	Pangasinan	Binalonan	Pasileng Sur	16.03302	120.60294	36	27.06	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
294	\N	Region I	Pangasinan	Binalonan	San Felipe Central	16.049486	120.6271	49	27.04	2238	San Manuel sandy loam	sandy loam	Lowlands	0
295	\N	Region I	Pangasinan	Binalonan	San Felipe Sur	16.051045	120.603	41	27.09	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
296	\N	Region I	Pangasinan	Binalonan	San Pablo	16.03578	120.61882	39	27.06	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
297	\N	Region I	Pangasinan	Binalonan	Santa Catalina	16.096712	120.620118	106	26.22	2178.9	Umingan silt loam	silt loam	Lowlands	0
298	\N	Region I	Pangasinan	Binalonan	Santa Maria Norte	16.069067	120.587489	41	27.09	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
300	\N	Region I	Pangasinan	Binalonan	Santo Ni├▒o	16.061925	120.593437	43	27.1	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
309	\N	Region I	Pangasinan	Laoac	Cabilaoan West	16.023143	120.5419	23	27	2478.6	San Manuel silty clay loam	silty clay loam	Lowlands	0
316	\N	Region I	Pangasinan	Laoac	Domingo Alarcio	16.023383	120.55195	25	26.95	2478.6	San Manuel silty clay loam	silty clay loam	Lowlands	0
327	\N	Region I	Pangasinan	Natividad	Batchelor East	16.0514	120.814783	120	26.48	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
328	\N	Region I	Pangasinan	Natividad	Batchelor West	16.049067	120.806367	105	26.59	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
333	\N	Region I	Pangasinan	Natividad	Poblacion East	16.04176	120.79306	88	26.67	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
334	\N	Region I	Pangasinan	Natividad	Poblacion West	16.04678	120.79798	92	26.64	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
337	\N	Region I	Pangasinan	Natividad	San Macario Norte	16.053092	120.84245	437	24.58	2805.8	Annam clay loam	clay loam	Uplands	0
338	\N	Region I	Pangasinan	Natividad	San Macario Sur	16.035614	120.8279	187	26.07	2848.3	Annam clay loam	clay loam	Uplands	0
339	\N	Region I	Pangasinan	Natividad	San Maximo	16.040156	120.803522	98	26.62	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
340	\N	Region I	Pangasinan	Natividad	San Miguel	16.0219	120.79655	82	26.78	2480.6	Umingan sandy loam	sandy loam	Lowlands	0
342	\N	Region I	Pangasinan	Pozorrubio	Alipangpang	16.112171	120.553243	56	26.37	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
343	\N	Region I	Pangasinan	Pozorrubio	Amagbagan	16.09131	120.53622	38	26.84	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
344	\N	Region I	Pangasinan	Pozorrubio	Balacag	16.13625	120.4776	91	26.8	2524.9	San Fabian clay loam	clay loam	Highlands	0
345	\N	Region I	Pangasinan	Pozorrubio	Banding	16.1039	120.54356	52	26.41	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
346	\N	Region I	Pangasinan	Pozorrubio	Bantugan	16.107988	120.52075	38	26.94	2532.4	Umingan silt loam	silt loam	Lowlands	0
347	\N	Region I	Pangasinan	Pozorrubio	Batakil	16.150457	120.516643	66	26.49	2453.4	Umingan silt loam	silt loam	Lowlands	0
348	\N	Region I	Pangasinan	Pozorrubio	Bobonan	16.140322	120.5203	53	26.39	2453.4	Umingan silt loam	silt loam	Lowlands	0
349	\N	Region I	Pangasinan	Pozorrubio	Buneg	16.126175	120.56195	72	26.34	2453.4	Umingan silt loam	silt loam	Lowlands	0
350	\N	Region I	Pangasinan	Pozorrubio	Cablong	16.12784	120.53274	62	26.39	2453.4	Umingan silt loam	silt loam	Lowlands	0
351	\N	Region I	Pangasinan	Pozorrubio	Casanfernandoan	16.124829	120.477243	61	26.85	2442.1	San Fabian clay loam	clay loam	Highlands	0
352	\N	Region I	Pangasinan	Pozorrubio	Casta├▒o	16.114736	120.506436	40	26.87	2442.1	San Fabian clay loam	clay loam	Highlands	0
353	\N	Region I	Pangasinan	Pozorrubio	Dilan	16.088471	120.520557	36	26.86	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
354	\N	Region I	Pangasinan	Pozorrubio	Don Benito	16.141843	120.497871	61	26.39	2453.4	Pangasinan river sand	sand	Lowlands	0
355	\N	Region I	Pangasinan	Pozorrubio	Haway	16.114767	120.481917	62	26.86	2442.1	San Fabian clay loam	clay loam	Highlands	0
356	\N	Region I	Pangasinan	Pozorrubio	Imbalbalatong	16.128771	120.549471	73	26.36	2453.4	Umingan silt loam	silt loam	Lowlands	0
357	\N	Region I	Pangasinan	Pozorrubio	Inoman	16.150243	120.529286	61	26.5	2453.4	Umingan silt loam	silt loam	Lowlands	0
358	\N	Region I	Pangasinan	Pozorrubio	Laoac	16.14382	120.50617	81	26.35	2453.4	Umingan silt loam	silt loam	Lowlands	0
359	\N	Region I	Pangasinan	Pozorrubio	Maambal	16.10248	120.4878	52	26.88	2442.1	San Fabian clay loam	clay loam	Highlands	0
360	\N	Region I	Pangasinan	Pozorrubio	Malasin	16.10045	120.51985	36	26.84	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
361	\N	Region I	Pangasinan	Pozorrubio	Malokiat	16.127514	120.496329	49	26.89	2524.9	San Fabian clay loam	clay loam	Highlands	0
362	\N	Region I	Pangasinan	Pozorrubio	Manaol	16.118883	120.510183	45	26.85	2442.1	Pangasinan river sand	sand	Lowlands	0
363	\N	Region I	Pangasinan	Pozorrubio	Nama	16.137325	120.534125	61	26.39	2453.4	Umingan silt loam	silt loam	Lowlands	0
364	\N	Region I	Pangasinan	Pozorrubio	Nantangalan	16.092491	120.503209	43	26.83	2532.4	San Fabian clay loam	clay loam	Highlands	0
365	\N	Region I	Pangasinan	Pozorrubio	Palacpalac	16.13195	120.52365	52	26.4	2453.4	Umingan silt loam	silt loam	Lowlands	0
366	\N	Region I	Pangasinan	Pozorrubio	Palguyod	16.128929	120.5124	48	26.41	2453.4	Pangasinan river sand	sand	Lowlands	0
367	\N	Region I	Pangasinan	Pozorrubio	Poblacion I	16.11972	120.53428	56	26.4	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
368	\N	Region I	Pangasinan	Pozorrubio	Poblacion II	16.115617	120.534817	49	26.41	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
369	\N	Region I	Pangasinan	Pozorrubio	Poblacion III	16.12086	120.54196	57	26.39	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
370	\N	Region I	Pangasinan	Pozorrubio	Poblacion IV	16.11468	120.54258	56	26.4	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
371	\N	Region I	Pangasinan	Pozorrubio	Rosario	16.10018	120.56152	53	26.38	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
372	\N	Region I	Pangasinan	Pozorrubio	Sugcong	16.148117	120.546817	150	26.21	2453.4	Umingan silt loam	silt loam	Lowlands	0
373	\N	Region I	Pangasinan	Pozorrubio	Talogtog	16.10945	120.534633	45	26.89	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
374	\N	Region I	Pangasinan	Pozorrubio	Tulnac	16.117529	120.525029	46	26.87	2370.5	San Manuel silty clay loam	silty clay loam	Lowlands	0
375	\N	Region I	Pangasinan	Pozorrubio	Villegas	16.141614	120.554571	85	26.32	2453.4	Umingan silt loam	silt loam	Lowlands	0
379	\N	Region I	Pangasinan	Rosales	Cabalaoangan Norte	15.885	120.627157	32	27.1	2469.2	San Manuel silt loam	silt loam	Lowlands	0
380	\N	Region I	Pangasinan	Rosales	Cabalaoangan Sur	15.879786	120.634929	34	27.11	2469.2	San Manuel silt loam	silt loam	Lowlands	0
383	\N	Region I	Pangasinan	Rosales	Capitan Tomas	15.909583	120.6458	35	27.1	2469.2	Annam clay loam	clay loam	Uplands	0
384	\N	Region I	Pangasinan	Rosales	Carmay East	15.91566	120.64044	33	27.1	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
385	\N	Region I	Pangasinan	Rosales	Carmay West	15.913167	120.624417	30	27.11	2440.6	San Manuel sandy loam	sandy loam	Lowlands	0
386	\N	Region I	Pangasinan	Rosales	Carmen East	15.88938	120.60206	28	26.9	2721.2	San Manuel sand	sand	Lowlands	0
387	\N	Region I	Pangasinan	Rosales	Carmen West	15.88992	120.5942	28	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
390	\N	Region I	Pangasinan	Rosales	Don Antonio Village	15.898567	120.623	34	27.09	2440.6	San Manuel sand	sand	Lowlands	0
397	\N	Region I	Pangasinan	Rosales	San Angel	15.8614	120.6575	65	27.05	2303.3	San Fabian clay loam	clay loam	Highlands	0
398	\N	Region I	Pangasinan	Rosales	San Antonio	15.85452	120.66194	74	27.06	2303.3	San Fabian clay loam	clay loam	Highlands	0
399	\N	Region I	Pangasinan	Rosales	San Bartolome	15.877	120.613937	30	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
400	\N	Region I	Pangasinan	Rosales	San Isidro	15.83744	120.62604	30	26.92	2587.8	San Manuel silt loam	silt loam	Lowlands	0
445	\N	Region I	Pangasinan	San Nicolas	San Roque	16.060889	120.752922	74	26.74	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
446	\N	Region I	Pangasinan	San Nicolas	Santa Maria West	16.09686	120.79538	230	25.83	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
447	\N	Region I	Pangasinan	San Nicolas	Santo Tomas	16.099786	120.7175	81	26.76	2222.9	Pangasinan river sand	sand	Lowlands	0
463	\N	Region I	Pangasinan	San Quintin	Poblacion Zone I	15.98915	120.80515	99	26.65	2606.4	Umingan silt loam	silt loam	Lowlands	0
464	\N	Region I	Pangasinan	San Quintin	Poblacion Zone II	15.98806	120.81588	116	26.49	2890.8	Umingan silt loam	silt loam	Lowlands	0
465	\N	Region I	Pangasinan	San Quintin	Poblacion Zone III	15.99424	120.81232	102	26.59	2890.8	Umingan silt loam	silt loam	Lowlands	0
466	\N	Region I	Pangasinan	San Quintin	San Pedro	15.969482	120.799636	85	26.73	2606.4	Umingan silt loam	silt loam	Lowlands	0
480	\N	Region I	Pangasinan	Santa Maria	Poblacion East	15.981	120.69622	49	26.96	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
481	\N	Region I	Pangasinan	Santa Maria	Poblacion West	15.98098	120.69246	46	27.36	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
484	\N	Region I	Pangasinan	Santa Maria	San Alejandro	15.978583	120.698217	47	26.96	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
485	\N	Region I	Pangasinan	Santa Maria	San Mariano	15.98695	120.711567	47	26.96	2480.6	San Manuel sand	sand	Lowlands	0
486	\N	Region I	Pangasinan	Santa Maria	San Pablo	15.9476	120.701983	37	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
487	\N	Region I	Pangasinan	Santa Maria	San Patricio	15.988543	120.692357	44	27.38	2288.8	Pangasinan river sand	sand	Lowlands	0
488	\N	Region I	Pangasinan	Santa Maria	San Vicente	15.996433	120.703233	44	26.97	2480.6	Pangasinan river sand	sand	Lowlands	0
489	\N	Region I	Pangasinan	Santa Maria	Santa Cruz	15.959933	120.7092	40	27.13	2344.7	San Manuel silt loam	silt loam	Lowlands	0
499	\N	Region I	Pangasinan	Santo Tomas	Santo Ni├▒o	15.87658	120.5621	27	26.9	2721.2	San Manuel fine sandy loam	sandy loam	Lowlands	0
521	\N	Region I	Pangasinan	Sison	Poblacion Central	16.17415	120.49775	93	26.64	2602.5	Umingan silt loam	silt loam	Lowlands	0
522	\N	Region I	Pangasinan	Sison	Poblacion Norte	16.180117	120.4913	90	26.66	2602.5	Umingan silt loam	silt loam	Lowlands	0
523	\N	Region I	Pangasinan	Sison	Poblacion Sur	16.166543	120.504914	82	26.76	2453.4	Umingan silt loam	silt loam	Lowlands	0
528	\N	Region I	Pangasinan	Tayug	Barangay A	16.031843	120.744371	65	26.82	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
529	\N	Region I	Pangasinan	Tayug	Barangay B	16.028867	120.743567	65	26.93	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
530	\N	Region I	Pangasinan	Tayug	Barangay C	16.03116	120.73876	57	26.94	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
531	\N	Region I	Pangasinan	Tayug	Barangay D	16.026243	120.739771	64	26.93	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
533	\N	Region I	Pangasinan	Tayug	C. Lichauco	15.983891	120.767073	63	27.03	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
543	\N	Region I	Pangasinan	Tayug	Santo Domingo	15.997383	120.73975	60	26.94	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
547	\N	Region I	Pangasinan	Umingan	Abot Molina	15.90409	120.83282	98	26.46	2606.4	Umingan silt loam	silt loam	Lowlands	0
561	\N	Region I	Pangasinan	Umingan	Carayungan Sur	15.889178	120.842633	100	26.37	2549.5	Umingan silt loam	silt loam	Lowlands	0
567	\N	Region I	Pangasinan	Umingan	Del Rosario	15.913428	120.799461	80	26.49	2606.4	Tarlac clay loam	clay loam	Uplands	0
602	\N	Region I	Pangasinan	Umingan	Tanggal Sawang	15.9428	120.75196	53	26.54	2606.4	San Manuel sandy loam	sandy loam	Lowlands	0
604	\N	Region I	Pangasinan	Urdaneta City	Bactad East	15.98535	120.626817	33	27.35	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
615	\N	Region I	Pangasinan	Urdaneta City	Dilan Paurido	15.982975	120.584862	28	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
622	\N	Region I	Pangasinan	Urdaneta City	Nancamaliran East	15.978833	120.558017	24	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
623	\N	Region I	Pangasinan	Urdaneta City	Nancamaliran West	15.975814	120.547871	30	26.98	2478.6	San Manuel silt loam	silt loam	Lowlands	0
626	\N	Region I	Pangasinan	Urdaneta City	Palina East	15.954467	120.560583	31	26.73	2666.7	San Manuel silt loam	silt loam	Lowlands	0
627	\N	Region I	Pangasinan	Urdaneta City	Palina West	15.95975	120.545587	22	26.78	2666.7	San Manuel silt loam	silt loam	Lowlands	0
630	\N	Region I	Pangasinan	Urdaneta City	San Jose	15.993071	120.501857	22	26.82	2637.1	San Manuel fine sandy loam	sandy loam	Lowlands	0
631	\N	Region I	Pangasinan	Urdaneta City	San Vicente	15.989957	120.568386	31	26.94	2478.6	San Manuel silt loam	silt loam	Lowlands	0
632	\N	Region I	Pangasinan	Urdaneta City	Santa Lucia	15.96884	120.55522	23	26.96	2478.6	San Manuel silt loam	silt loam	Lowlands	0
633	\N	Region I	Pangasinan	Urdaneta City	Santo Domingo	15.96472	120.56184	24	26.96	2478.6	San Manuel silt loam	silt loam	Lowlands	0
450	\N	Region I	Pangasinan	San Quintin	Alac	16.00235	120.798	105	26.63	2480.6	Umingan silt loam	silt loam	Lowlands	0
451	\N	Region I	Pangasinan	San Quintin	Baligayan	15.95046	120.7222	45	27.13	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
452	\N	Region I	Pangasinan	San Quintin	Bantog	15.962786	120.813643	96	26.65	2606.4	Umingan silt loam	silt loam	Lowlands	0
453	\N	Region I	Pangasinan	San Quintin	Bolintaguen	15.98075	120.782086	74	26.83	2480.6	Umingan silt loam	silt loam	Lowlands	0
454	\N	Region I	Pangasinan	San Quintin	Cabalaoangan	15.9811	120.809014	104	26.63	2606.4	Umingan silt loam	silt loam	Lowlands	0
455	\N	Region I	Pangasinan	San Quintin	Calomboyan	15.98305	120.821517	116	26.52	2890.8	Umingan silt loam	silt loam	Lowlands	0
456	\N	Region I	Pangasinan	San Quintin	Carayacan	15.969754	120.827385	116	26.53	2606.4	Umingan silt loam	silt loam	Lowlands	0
421	\N	Region I	Pangasinan	San Manuel	San Bonifacio	16.083056	120.679278	80	27.16	2222.9	Umingan sand	sand	Lowlands	0
408	\N	Region I	Pangasinan	Rosales	Zone I	15.888375	120.624075	30	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
409	\N	Region I	Pangasinan	Rosales	Zone II	15.897429	120.628114	35	27.1	2469.2	Annam clay loam	clay loam	Uplands	0
410	\N	Region I	Pangasinan	Rosales	Zone III	15.9049	120.620167	31	27.12	2440.6	San Manuel sand	sand	Lowlands	0
411	\N	Region I	Pangasinan	Rosales	Zone IV	15.90526	120.62972	30	27.1	2469.2	San Manuel sand	sand	Lowlands	0
412	\N	Region I	Pangasinan	Rosales	Zone V	15.8898	120.63062	39	27.1	2469.2	San Manuel silt loam	silt loam	Lowlands	0
416	\N	Region I	Pangasinan	San Manuel	Guiset Norte	16.07238	120.66876	74	27.17	2222.9	Umingan sand	sand	Lowlands	0
417	\N	Region I	Pangasinan	San Manuel	Guiset Sur	16.065029	120.666714	68	27.18	2222.9	Umingan sand	sand	Lowlands	0
420	\N	Region I	Pangasinan	San Manuel	San Antonio-Arzadon	16.057914	120.689343	62	27.19	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
422	\N	Region I	Pangasinan	San Manuel	San Juan	16.04944	120.67488	59	27.15	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
423	\N	Region I	Pangasinan	San Manuel	San Vicente	16.062945	120.710409	66	27.18	2222.9	Umingan sand	sand	Lowlands	0
413	\N	Region I	Pangasinan	San Manuel	Cabacaraan	16.05634	120.67174	61	27.19	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
414	\N	Region I	Pangasinan	San Manuel	Cabaritan	16.051075	120.658713	54	27.2	2222.9	Umingan sand	sand	Lowlands	0
415	\N	Region I	Pangasinan	San Manuel	Flores	16.068733	120.6855	68	27.18	2222.9	Umingan sand	sand	Lowlands	0
418	\N	Region I	Pangasinan	San Manuel	Nagsaag	16.06525	120.6565	66	27.18	2222.9	Umingan sand	sand	Lowlands	0
419	\N	Region I	Pangasinan	San Manuel	Narra	16.099693	120.698064	86	26.78	2222.9	Pangasinan river sand	sand	Lowlands	0
211	\N	Region I	Pangasinan	Alcala	Pindangan Centro	15.862686	120.5499	28	26.89	2444.7	San Manuel sand	sand	Lowlands	0
186	\N	Region I	Pangasinan	Santa Maria	Santa Rosa	15.98146	120.68564	36	27.38	2288.8	San Manuel sand	sand	Lowlands	0
187	\N	Region I	Pangasinan	Umingan	Maseil-seil	15.910573	120.879373	152	26.36	2592.2	Umingan silt loam	silt loam	Lowlands	0
188	\N	Region I	Pangasinan	San Nicolas	Salpad	16.18376	120.76676	499	24.09	2840.8	Annam clay loam	clay loam	Uplands	0
189	\N	Region I	Pangasinan	Balungao	San Andres	15.865917	120.675075	109	26.98	2303.3	San Fabian clay loam	clay loam	Highlands	0
191	\N	Region I	Pangasinan	Natividad	San Eugenio	16.074025	120.829775	413	24.82	2805.8	Annam clay loam	clay loam	Uplands	0
192	\N	Region I	Pangasinan	San Quintin	Casantamarian	16.008445	120.864073	751	22.33	2805.8	Annam clay loam	clay loam	Uplands	0
194	\N	Region I	Pangasinan	Umingan	Calitlitan	15.962063	120.863875	176	26.21	2655.4	Annam clay loam	clay loam	Uplands	0
201	\N	Region I	Pangasinan	Alcala	Anulid	15.8479	120.50105	21	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
202	\N	Region I	Pangasinan	Alcala	Atainan	15.861267	120.509017	22	26.91	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
203	\N	Region I	Pangasinan	Alcala	Bersamin	15.837625	120.554212	20	26.94	2561.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
204	\N	Region I	Pangasinan	Alcala	Canarvacanan	15.841114	120.540286	20	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
205	\N	Region I	Pangasinan	Alcala	Caranglaan	15.858829	120.498186	25	26.91	2444.7	San Manuel silt loam	silt loam	Lowlands	0
206	\N	Region I	Pangasinan	Alcala	Curareng	15.8638	120.522233	25	26.9	2444.7	San Manuel silt loam	silt loam	Lowlands	0
207	\N	Region I	Pangasinan	Alcala	Gualsic	15.87096	120.53908	27	26.9	2444.7	San Manuel silt loam	silt loam	Lowlands	0
208	\N	Region I	Pangasinan	Alcala	Kasikis	15.85285	120.544167	22	26.91	2444.7	San Manuel sand	sand	Lowlands	0
209	\N	Region I	Pangasinan	Alcala	Laoac	15.84218	120.51332	28	26.88	2444.7	San Manuel sand	sand	Lowlands	0
210	\N	Region I	Pangasinan	Alcala	Macayo	15.87914	120.55634	31	26.9	2721.2	San Manuel silt loam	silt loam	Lowlands	0
221	\N	Region I	Pangasinan	Alcala	Vacante	15.843429	120.568429	21	26.94	2561.4	San Manuel silt loam	silt loam	Lowlands	0
224	\N	Region I	Pangasinan	Asingan	Bantog	16.00277	120.684944	42	27.37	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
225	\N	Region I	Pangasinan	Asingan	Baro	16.000788	120.665987	45	27.36	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
226	\N	Region I	Pangasinan	Asingan	Bobonan	16.0401	120.6385	51	27.03	2238	San Manuel sandy loam	sandy loam	Lowlands	0
227	\N	Region I	Pangasinan	Asingan	Cabalitian	15.980733	120.653367	35	27.38	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
228	\N	Region I	Pangasinan	Asingan	Calepaan	16.026044	120.621267	38	27.06	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
231	\N	Region I	Pangasinan	Asingan	Coldit	16.0387	120.64692	50	27.14	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
232	\N	Region I	Pangasinan	Asingan	Domanpot	16.001543	120.643914	39	27.34	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
233	\N	Region I	Pangasinan	Asingan	Dupac	16.029814	120.679436	51	27.17	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
234	\N	Region I	Pangasinan	Asingan	Macalong	16.01705	120.65456	44	27.37	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
235	\N	Region I	Pangasinan	Asingan	Palaris	16.035983	120.631283	43	27.05	2238	San Manuel sandy loam	sandy loam	Lowlands	0
240	\N	Region I	Pangasinan	Asingan	Sanchez	15.989911	120.663578	42	27.37	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
241	\N	Region I	Pangasinan	Asingan	Sobol	16.01492	120.63005	39	27.34	2288.8	San Manuel sandy loam	sandy loam	Lowlands	0
242	\N	Region I	Pangasinan	Asingan	Toboy	16.028746	120.637646	48	27.32	2288.8	Pangasinan river sand	sand	Lowlands	0
245	\N	Region I	Pangasinan	Balungao	Capulaan	15.91538	120.65932	39	27.11	2469.2	San Manuel silt loam	silt loam	Lowlands	0
246	\N	Region I	Pangasinan	Balungao	Esmeralda	15.872327	120.709787	71	27.04	2303.3	San Manuel silt loam	silt loam	Lowlands	0
247	\N	Region I	Pangasinan	Balungao	Kita-Kita	15.89685	120.658475	43	27.1	2469.2	San Manuel silt loam	silt loam	Lowlands	0
248	\N	Region I	Pangasinan	Balungao	Mabini	15.859441	120.714159	74	27.03	2303.3	Annam clay loam	clay loam	Uplands	0
249	\N	Region I	Pangasinan	Balungao	Mauban	15.8999	120.718029	45	27.18	2344.7	San Manuel silt loam	silt loam	Lowlands	0
250	\N	Region I	Pangasinan	Balungao	Poblacion	15.90165	120.66475	40	27.09	2469.2	San Manuel silt loam	silt loam	Lowlands	0
251	\N	Region I	Pangasinan	Balungao	Pugaro	15.895045	120.672755	44	27.09	2465.3	San Manuel silt loam	silt loam	Lowlands	0
252	\N	Region I	Pangasinan	Balungao	Rajal	15.910554	120.703369	45	27.19	2344.7	San Manuel silt loam	silt loam	Lowlands	0
262	\N	Region I	Pangasinan	Bautista	Artacho	15.82542	120.55934	22	26.96	2517.6	San Manuel silt loam	silt loam	Lowlands	0
263	\N	Region I	Pangasinan	Bautista	Baluyot	15.806614	120.474443	21	27.14	2308.8	San Manuel sand	sand	Lowlands	0
264	\N	Region I	Pangasinan	Bautista	Cabuaan	15.809444	120.480122	23	27.13	2308.8	San Manuel sand	sand	Lowlands	0
265	\N	Region I	Pangasinan	Bautista	Cacandongan	15.828487	120.490687	25	26.88	2444.7	San Manuel sand	sand	Lowlands	0
266	\N	Region I	Pangasinan	Bautista	Diaz	15.80404	120.510033	19	27.14	2308.8	San Manuel silt loam	silt loam	Lowlands	0
267	\N	Region I	Pangasinan	Bautista	Ketegan	15.82368	120.49276	21	26.9	2444.7	San Manuel sand	sand	Lowlands	0
268	\N	Region I	Pangasinan	Bautista	Nandacan	15.81924	120.48736	23	27.14	2308.8	San Manuel sand	sand	Lowlands	0
271	\N	Region I	Pangasinan	Bautista	Palisoc	15.819143	120.500271	21	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
274	\N	Region I	Pangasinan	Bautista	Pogo	15.82454	120.50955	21	26.9	2444.7	San Manuel fine sandy loam	sandy loam	Lowlands	0
275	\N	Region I	Pangasinan	Bautista	Poponto	15.776871	120.537057	16	26.94	2517.6	San Manuel silt loam	silt loam	Lowlands	0
276	\N	Region I	Pangasinan	Bautista	Primicias	15.805289	120.549844	23	26.93	2517.6	San Manuel silt loam	silt loam	Lowlands	0
277	\N	Region I	Pangasinan	Bautista	Sinabaan	15.8202	120.472883	26	27.13	2308.8	San Manuel sand	sand	Lowlands	0
278	\N	Region I	Pangasinan	Bautista	Vacante	15.801264	120.492136	21	27.14	2308.8	San Manuel fine sandy loam	sandy loam	Lowlands	0
279	\N	Region I	Pangasinan	Bautista	Villanueva	15.822413	120.543262	19	26.9	2444.7	San Manuel silt loam	silt loam	Lowlands	0
280	\N	Region I	Pangasinan	Binalonan	Balangobong	16.02684	120.60524	34	27.06	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
281	\N	Region I	Pangasinan	Binalonan	Bued	16.04544	120.5784	32	27.07	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
282	\N	Region I	Pangasinan	Binalonan	Bugayong	16.088786	120.567114	49	27.08	2209.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
283	\N	Region I	Pangasinan	Binalonan	Camangaan	16.100983	120.585167	62	27.05	2209.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
284	\N	Region I	Pangasinan	Binalonan	Canarvacanan	16.06075	120.580462	45	27.09	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
285	\N	Region I	Pangasinan	Binalonan	Capas	16.05885	120.610283	46	27.08	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
286	\N	Region I	Pangasinan	Binalonan	Cili	16.08097	120.5827	49	27.07	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
287	\N	Region I	Pangasinan	Binalonan	Dumayat	16.067583	120.572483	41	27.09	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
288	\N	Region I	Pangasinan	Binalonan	Linmansangan	16.055356	120.573944	38	27.1	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
289	\N	Region I	Pangasinan	Binalonan	Mangcasuy	16.077392	120.620783	58	27.06	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
290	\N	Region I	Pangasinan	Binalonan	Moreno	16.109587	120.616263	253	25.96	2178.9	Umingan silt loam	silt loam	Lowlands	0
293	\N	Region I	Pangasinan	Binalonan	Poblacion	16.050267	120.587917	36	27.09	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
299	\N	Region I	Pangasinan	Binalonan	Santiago	16.04622	120.5712	36	27.06	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
301	\N	Region I	Pangasinan	Binalonan	Sumabnit	16.030617	120.573333	31	26.94	2478.6	San Manuel fine sandy loam	sandy loam	Lowlands	0
302	\N	Region I	Pangasinan	Binalonan	Tabuyoc	16.026162	120.587963	32	27.07	2209.4	San Manuel sandy loam	sandy loam	Lowlands	0
303	\N	Region I	Pangasinan	Binalonan	Vacante	16.075214	120.569993	50	27.08	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
304	\N	Region I	Pangasinan	Laoac	Anis	16.037138	120.56035	30	27.07	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
305	\N	Region I	Pangasinan	Laoac	Balligi	16.060614	120.557843	32	27.11	2209.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
306	\N	Region I	Pangasinan	Laoac	Banuar	16.059367	120.537083	26	26.86	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
307	\N	Region I	Pangasinan	Laoac	Botique	16.076333	120.553183	42	26.82	2532.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
308	\N	Region I	Pangasinan	Laoac	Caaringayan	16.03872	120.5523	26	26.81	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
310	\N	Region I	Pangasinan	Laoac	Cabulalaan	16.071222	120.542033	37	26.84	2532.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
311	\N	Region I	Pangasinan	Laoac	Calaoagan	16.06424	120.5325	34	26.86	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
312	\N	Region I	Pangasinan	Laoac	Calmay	16.035136	120.5117	23	26.85	2532.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
313	\N	Region I	Pangasinan	Laoac	Casampagaan	16.0512	120.551617	31	26.84	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
314	\N	Region I	Pangasinan	Laoac	Casanestebanan	16.0473	120.523786	20	26.85	2532.4	San Manuel silt loam	silt loam	Lowlands	0
315	\N	Region I	Pangasinan	Laoac	Casantiagoan	16.02328	120.56504	28	26.94	2478.6	San Manuel fine sandy loam	sandy loam	Lowlands	0
317	\N	Region I	Pangasinan	Laoac	Inmanduyan	16.04702	120.50936	19	26.85	2532.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
318	\N	Region I	Pangasinan	Laoac	Lebueg	16.028525	120.561337	29	26.95	2478.6	San Manuel silty clay loam	silty clay loam	Lowlands	0
319	\N	Region I	Pangasinan	Laoac	Maraboc	16.062956	120.521489	22	26.87	2532.4	San Manuel fine sandy loam	sandy loam	Lowlands	0
320	\N	Region I	Pangasinan	Laoac	Nanbagatan	16.039675	120.5306	21	26.85	2532.4	San Manuel silt loam	silt loam	Lowlands	0
321	\N	Region I	Pangasinan	Laoac	Panaga	16.0816	120.547255	37	26.84	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
322	\N	Region I	Pangasinan	Laoac	Poblacion	16.062333	120.5482	32	26.85	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
323	\N	Region I	Pangasinan	Laoac	Talogtog	16.057771	120.529643	28	26.87	2532.4	San Manuel silt loam	silt loam	Lowlands	0
324	\N	Region I	Pangasinan	Laoac	Turko	16.074367	120.531508	30	26.86	2532.4	San Manuel silty clay loam	silty clay loam	Lowlands	0
325	\N	Region I	Pangasinan	Laoac	Yatyat	16.013517	120.557417	27	26.95	2478.6	San Manuel fine sandy loam	sandy loam	Lowlands	0
326	\N	Region I	Pangasinan	Natividad	Barangobong	16.047371	120.780914	77	26.76	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
329	\N	Region I	Pangasinan	Natividad	Burgos	16.028643	120.7789	74	26.83	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
330	\N	Region I	Pangasinan	Natividad	Calapugan	16.037378	120.812667	106	26.57	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
331	\N	Region I	Pangasinan	Natividad	Canarem	16.037571	120.781371	76	26.75	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
332	\N	Region I	Pangasinan	Natividad	Luna	16.0139	120.787238	80	26.79	2480.6	San Manuel sand	sand	Lowlands	0
335	\N	Region I	Pangasinan	Natividad	Rizal	16.042729	120.779243	72	26.78	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
336	\N	Region I	Pangasinan	Natividad	Salud	16.053383	120.790067	85	26.7	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
341	\N	Region I	Pangasinan	Natividad	Silag	16.011586	120.782686	77	26.8	2480.6	San Manuel sand	sand	Lowlands	0
376	\N	Region I	Pangasinan	Rosales	Acop	15.86822	120.65452	42	27.09	2303.3	San Fabian clay loam	clay loam	Highlands	0
377	\N	Region I	Pangasinan	Rosales	Bakitbakit	15.8806	120.6515	35	27.11	2465.3	San Manuel silt loam	silt loam	Lowlands	0
378	\N	Region I	Pangasinan	Rosales	Balingcanaway	15.896867	120.651517	40	27.11	2469.2	San Manuel silt loam	silt loam	Lowlands	0
381	\N	Region I	Pangasinan	Rosales	Calanutan	15.86538	120.63548	31	26.89	2587.8	San Manuel silt loam	silt loam	Lowlands	0
382	\N	Region I	Pangasinan	Rosales	Camangaan	15.848967	120.634317	33	26.92	2587.8	San Manuel silt loam	silt loam	Lowlands	0
388	\N	Region I	Pangasinan	Rosales	Casanicolasan	15.927971	120.641871	32	27.11	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
389	\N	Region I	Pangasinan	Rosales	Coliling	15.85408	120.62198	33	26.89	2561.4	San Manuel silt loam	silt loam	Lowlands	0
391	\N	Region I	Pangasinan	Rosales	Guiling	15.84982	120.6235	31	26.92	2561.4	San Manuel silt loam	silt loam	Lowlands	0
392	\N	Region I	Pangasinan	Rosales	Palakipak	15.864083	120.617833	32	26.89	2561.4	San Manuel silt loam	silt loam	Lowlands	0
393	\N	Region I	Pangasinan	Rosales	Pangaoan	15.83765	120.643483	33	27.13	2303.3	San Fabian clay loam	clay loam	Highlands	0
394	\N	Region I	Pangasinan	Rosales	Rabago	15.85694	120.63296	30	26.89	2587.8	San Manuel silt loam	silt loam	Lowlands	0
395	\N	Region I	Pangasinan	Rosales	Rizal	15.924167	120.630889	30	27.11	2469.2	San Manuel sand	sand	Lowlands	0
396	\N	Region I	Pangasinan	Rosales	Salvacion	15.84498	120.66118	67	27.05	2303.3	San Fabian clay loam	clay loam	Highlands	0
424	\N	Region I	Pangasinan	San Nicolas	Bensican	16.159717	120.785383	457	24.68	2840.8	Annam clay loam	clay loam	Uplands	0
425	\N	Region I	Pangasinan	San Nicolas	Cabitnongan	16.07854	120.77106	97	26.59	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
426	\N	Region I	Pangasinan	San Nicolas	Caboloan	16.08765	120.73284	79	26.79	2222.9	Umingan sandy loam	sandy loam	Lowlands	0
427	\N	Region I	Pangasinan	San Nicolas	Cacabugaoan	16.107175	120.839363	934	21.26	2600.1	Annam clay loam	clay loam	Uplands	0
428	\N	Region I	Pangasinan	San Nicolas	Calanutian	16.134363	120.68725	181	25.75	2481.8	Annam clay loam	clay loam	Uplands	0
429	\N	Region I	Pangasinan	San Nicolas	Calaocan	16.080433	120.78185	104	26.54	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
430	\N	Region I	Pangasinan	San Nicolas	Camanggaan	16.0953	120.73158	83	26.74	2222.9	Umingan sandy loam	sandy loam	Lowlands	0
431	\N	Region I	Pangasinan	San Nicolas	Camindoroan	16.117686	120.702914	126	26.43	2407.8	Pangasinan river sand	sand	Lowlands	0
432	\N	Region I	Pangasinan	San Nicolas	Casaratan	16.070667	120.7584	83	26.67	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
433	\N	Region I	Pangasinan	San Nicolas	Lungao	16.085114	120.761486	88	26.61	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
434	\N	Region I	Pangasinan	San Nicolas	Malilion	16.107267	120.745183	98	26.56	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
435	\N	Region I	Pangasinan	San Nicolas	Nagkaysa	16.06784	120.76056	85	26.65	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
436	\N	Region I	Pangasinan	San Nicolas	Nining	16.06404	120.7898	93	26.62	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
448	\N	Region I	Pangasinan	San Nicolas	Siblot	16.069962	120.776913	92	26.63	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
449	\N	Region I	Pangasinan	San Nicolas	Sobol	16.0579	120.7426	72	26.77	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
439	\N	Region I	Pangasinan	San Nicolas	San Felipe West	16.148975	120.7008	305	25.6	2481.8	Annam clay loam	clay loam	Uplands	0
401	\N	Region I	Pangasinan	Rosales	San Luis	15.84218	120.65192	44	27.1	2303.3	San Fabian clay loam	clay loam	Highlands	0
402	\N	Region I	Pangasinan	Rosales	San Pedro East	15.894833	120.64655	38	27.09	2469.2	San Manuel silt loam	silt loam	Lowlands	0
403	\N	Region I	Pangasinan	Rosales	San Pedro West	15.89378	120.63666	36	27.1	2469.2	San Manuel silt loam	silt loam	Lowlands	0
404	\N	Region I	Pangasinan	Rosales	San Vicente	15.84742	120.67394	91	27.02	2303.3	San Fabian clay loam	clay loam	Highlands	0
405	\N	Region I	Pangasinan	Rosales	Station District	15.89274	120.62038	32	27.11	2440.6	San Manuel sand	sand	Lowlands	0
406	\N	Region I	Pangasinan	Rosales	Tomana East	15.893543	120.612914	34	27.1	2440.6	San Manuel sand	sand	Lowlands	0
407	\N	Region I	Pangasinan	Rosales	Tomana West	15.892029	120.608743	28	27.12	2440.6	San Manuel sand	sand	Lowlands	0
437	\N	Region I	Pangasinan	San Nicolas	Poblacion East	16.074275	120.762375	86	26.63	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
438	\N	Region I	Pangasinan	San Nicolas	Poblacion West	16.074267	120.75725	83	26.68	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
440	\N	Region I	Pangasinan	San Nicolas	San Isidro	16.116886	120.758243	322	25.53	2407.8	Umingan sandy loam	sandy loam	Lowlands	0
441	\N	Region I	Pangasinan	San Nicolas	San Jose	16.057067	120.774167	77	26.7	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
442	\N	Region I	Pangasinan	San Nicolas	San Rafael Centro	16.0757	120.734117	70	26.84	2222.9	Umingan sandy loam	sandy loam	Lowlands	0
443	\N	Region I	Pangasinan	San Nicolas	San Rafael East	16.073867	120.749167	77	26.69	2848.3	Umingan sandy loam	sandy loam	Lowlands	0
444	\N	Region I	Pangasinan	San Nicolas	San Rafael West	16.063025	120.7324	69	26.85	2222.9	San Manuel sandy loam	sandy loam	Lowlands	0
500	\N	Region I	Pangasinan	Sison	Agat	16.211391	120.502936	145	26.04	2602.5	Umingan clay loam	clay loam	Lowlands	0
501	\N	Region I	Pangasinan	Sison	Amagbagan	16.17132	120.48238	77	26.75	2524.9	Umingan silt loam	silt loam	Lowlands	0
502	\N	Region I	Pangasinan	Sison	Artacho	16.1978	120.49812	117	26.09	2602.5	Pangasinan river sand	sand	Lowlands	0
506	\N	Region I	Pangasinan	Sison	Bila	16.183429	120.5134	104	26.11	2602.5	Umingan sandy loam	sandy loam	Lowlands	0
507	\N	Region I	Pangasinan	Sison	Binmeckeg	16.207287	120.475887	112	26.1	2602.5	Umingan clay loam	clay loam	Lowlands	0
510	\N	Region I	Pangasinan	Sison	Cabaritan	16.194317	120.479733	98	26.6	2602.5	Umingan silt loam	silt loam	Lowlands	0
511	\N	Region I	Pangasinan	Sison	Camangaan	16.1559	120.49035	93	26.92	2524.9	San Fabian clay loam	clay loam	Highlands	0
512	\N	Region I	Pangasinan	Sison	Cauringan	16.189486	120.4981	109	26.11	2602.5	Umingan silt loam	silt loam	Lowlands	0
513	\N	Region I	Pangasinan	Sison	Dungon	16.226417	120.51705	258	25.83	2602.5	Annam clay loam	clay loam	Uplands	0
514	\N	Region I	Pangasinan	Sison	Esperanza	16.201225	120.489025	114	26.09	2602.5	Pangasinan river sand	sand	Lowlands	0
515	\N	Region I	Pangasinan	Sison	Inmalog	16.196567	120.551917	214	25.95	2602.5	Annam clay loam	clay loam	Uplands	0
516	\N	Region I	Pangasinan	Sison	Killo	16.119163	120.575437	67	26.36	2370.5	Umingan silt loam	silt loam	Lowlands	0
517	\N	Region I	Pangasinan	Sison	Labayug	16.182656	120.592789	783	22.22	3261.4	Annam clay loam	clay loam	Uplands	0
518	\N	Region I	Pangasinan	Sison	Paldit	16.170625	120.5182	92	26.44	2453.4	Umingan sandy loam	sandy loam	Lowlands	0
503	\N	Region I	Pangasinan	Sison	Asan Norte	16.19168	120.52068	128	26.07	2602.5	Umingan sandy loam	sandy loam	Lowlands	0
504	\N	Region I	Pangasinan	Sison	Asan Sur	16.1587	120.5194	78	26.47	2453.4	Umingan sandy loam	sandy loam	Lowlands	0
505	\N	Region I	Pangasinan	Sison	Bantay Insik	16.187225	120.463025	111	26.1	2602.5	Pangasinan river sand	sand	Lowlands	0
508	\N	Region I	Pangasinan	Sison	Bulaoen East	16.19356	120.46962	93	26.63	2602.5	Pangasinan river sand	sand	Lowlands	0
509	\N	Region I	Pangasinan	Sison	Bulaoen West	16.179443	120.463914	146	26.02	2602.5	San Fabian clay loam	clay loam	Highlands	0
519	\N	Region I	Pangasinan	Sison	Pindangan	16.176883	120.471317	98	26.58	2602.5	Pangasinan river sand	sand	Lowlands	0
520	\N	Region I	Pangasinan	Sison	Pinmilapil	16.203871	120.4551	160	26.01	2602.5	San Fabian clay loam	clay loam	Highlands	0
524	\N	Region I	Pangasinan	Sison	Sagunto	16.203888	120.51255	143	26.05	2602.5	Umingan sandy loam	sandy loam	Lowlands	0
525	\N	Region I	Pangasinan	Sison	Tara-Tara	16.157843	120.476829	63	26.98	2524.9	Pangasinan river sand	sand	Lowlands	0
526	\N	Region I	Pangasinan	Tayug	Agno	16.021992	120.719992	56	26.95	2480.6	Pangasinan river sand	sand	Lowlands	0
527	\N	Region I	Pangasinan	Tayug	Amistad	16.033462	120.733675	58	26.95	2480.6	San Manuel sand	sand	Lowlands	0
532	\N	Region I	Pangasinan	Tayug	Barangobong	16.008789	120.719278	50	26.96	2480.6	San Manuel sand	sand	Lowlands	0
534	\N	Region I	Pangasinan	Tayug	Carriedo	16.03884	120.75762	68	26.87	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
535	\N	Region I	Pangasinan	Tayug	Evangelista	16.010583	120.739733	58	26.95	2480.6	San Manuel sand	sand	Lowlands	0
536	\N	Region I	Pangasinan	Tayug	Guzon	16.031683	120.709089	55	27.16	2222.9	Pangasinan river sand	sand	Lowlands	0
537	\N	Region I	Pangasinan	Tayug	Lawak	15.99591	120.75107	60	27.03	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
538	\N	Region I	Pangasinan	Tayug	Legaspi	16.049688	120.737088	64	26.79	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
539	\N	Region I	Pangasinan	Tayug	Libertad	16.022614	120.759314	68	27.02	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
540	\N	Region I	Pangasinan	Tayug	Magallanes	16.01881	120.73012	53	26.95	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
541	\N	Region I	Pangasinan	Tayug	Panganiban	16.0084	120.768575	70	27.01	2480.6	San Manuel sand	sand	Lowlands	0
542	\N	Region I	Pangasinan	Tayug	Saleng	15.99514	120.75916	62	27.03	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
544	\N	Region I	Pangasinan	Tayug	Toketec	16.014489	120.763667	66	27.02	2480.6	San Manuel sand	sand	Lowlands	0
545	\N	Region I	Pangasinan	Tayug	Trenchera	16.0292	120.758217	65	26.88	2480.6	San Manuel sandy loam	sandy loam	Lowlands	0
546	\N	Region I	Pangasinan	Tayug	Zamora	15.99795	120.775967	69	27.01	2480.6	Umingan silt loam	silt loam	Lowlands	0
548	\N	Region I	Pangasinan	Umingan	Alo-O	15.903155	120.885264	154	26.35	2592.2	Umingan silt loam	silt loam	Lowlands	0
549	\N	Region I	Pangasinan	Umingan	Amaronan	15.948667	120.829144	100	26.45	2606.4	Umingan silt loam	silt loam	Lowlands	0
550	\N	Region I	Pangasinan	Umingan	Annam	15.947818	120.859364	138	26.4	2606.4	Annam clay loam	clay loam	Uplands	0
551	\N	Region I	Pangasinan	Umingan	Bantug	15.914314	120.846557	115	26.53	2606.4	Umingan silt loam	silt loam	Lowlands	0
552	\N	Region I	Pangasinan	Umingan	Baracbac	15.848754	120.851142	95	26.35	2387.5	Annam clay loam	clay loam	Uplands	0
553	\N	Region I	Pangasinan	Umingan	Barat	15.943936	120.810782	85	26.48	2606.4	Umingan silt loam	silt loam	Lowlands	0
554	\N	Region I	Pangasinan	Umingan	Buenavista	15.938517	120.789533	72	26.51	2606.4	Tarlac clay loam	clay loam	Uplands	0
555	\N	Region I	Pangasinan	Umingan	Cabalitian	15.927117	120.747283	55	27.16	2344.7	Annam clay loam	clay loam	Uplands	0
556	\N	Region I	Pangasinan	Umingan	Cabangaran	15.876975	120.870087	118	26.36	2549.5	Umingan silt loam	silt loam	Lowlands	0
557	\N	Region I	Pangasinan	Umingan	Cabaruan	15.901563	120.740138	56	27.16	2344.7	Annam clay loam	clay loam	Uplands	0
558	\N	Region I	Pangasinan	Umingan	Cabatuan	15.90125	120.852663	115	26.61	2549.5	Umingan silt loam	silt loam	Lowlands	0
559	\N	Region I	Pangasinan	Umingan	Cadiz	15.864057	120.749043	63	26.91	2271.9	Annam clay loam	clay loam	Uplands	0
560	\N	Region I	Pangasinan	Umingan	Capas	15.91285	120.826392	97	26.46	2606.4	Umingan silt loam	silt loam	Lowlands	0
562	\N	Region I	Pangasinan	Umingan	Carosalesan	15.887321	120.865407	121	26.59	2549.5	Umingan silt loam	silt loam	Lowlands	0
563	\N	Region I	Pangasinan	Umingan	Casilan	15.88294	120.77689	74	26.91	2433.8	Annam clay loam	clay loam	Uplands	0
564	\N	Region I	Pangasinan	Umingan	Caurdanetaan	15.924825	120.847737	118	26.5	2606.4	Umingan silt loam	silt loam	Lowlands	0
565	\N	Region I	Pangasinan	Umingan	Concepcion	15.85781	120.77099	67	26.93	2271.9	Annam clay loam	clay loam	Uplands	0
566	\N	Region I	Pangasinan	Umingan	Decreto	15.931643	120.724186	44	27.18	2344.7	San Manuel silt loam	silt loam	Lowlands	0
568	\N	Region I	Pangasinan	Umingan	Diaz	15.838085	120.824763	121	26.3	2387.5	Annam clay loam	clay loam	Uplands	0
569	\N	Region I	Pangasinan	Umingan	Diket	15.9432	120.889753	305	25.33	2592.2	Annam clay loam	clay loam	Uplands	0
572	\N	Region I	Pangasinan	Umingan	Esperanza	15.941264	120.799391	78	26.5	2606.4	Tarlac clay loam	clay loam	Uplands	0
573	\N	Region I	Pangasinan	Umingan	Evangelista	15.949725	120.844667	120	26.49	2606.4	Umingan silt loam	silt loam	Lowlands	0
574	\N	Region I	Pangasinan	Umingan	Flores	15.935822	120.778189	67	26.51	2606.4	San Manuel sandy loam	sandy loam	Lowlands	0
575	\N	Region I	Pangasinan	Umingan	Fulgosino	15.900705	120.795967	87	26.46	2606.4	Annam clay loam	clay loam	Uplands	0
576	\N	Region I	Pangasinan	Umingan	Gonzales	15.919069	120.752175	53	26.54	2606.4	Annam clay loam	clay loam	Uplands	0
578	\N	Region I	Pangasinan	Umingan	Labuan	15.94004	120.73552	45	27.18	2344.7	San Manuel sandy loam	sandy loam	Lowlands	0
579	\N	Region I	Pangasinan	Umingan	Lauren	15.938487	120.830925	98	26.46	2606.4	Umingan silt loam	silt loam	Lowlands	0
580	\N	Region I	Pangasinan	Umingan	Lubong	15.92115	120.80891	81	26.49	2606.4	Tarlac clay loam	clay loam	Uplands	0
583	\N	Region I	Pangasinan	Umingan	Mantacdang	15.944671	120.763471	59	26.53	2606.4	San Manuel sandy loam	sandy loam	Lowlands	0
584	\N	Region I	Pangasinan	Umingan	Nampalcan	15.902041	120.820894	83	26.48	2606.4	Tarlac clay loam	clay loam	Uplands	0
585	\N	Region I	Pangasinan	Umingan	Nancalabasaan	15.9313	120.82938	96	26.46	2606.4	Umingan silt loam	silt loam	Lowlands	0
586	\N	Region I	Pangasinan	Umingan	Pangangaan	15.880553	120.815753	131	26.32	2549.5	Umingan silt loam	silt loam	Lowlands	0
587	\N	Region I	Pangasinan	Umingan	Papallasen	15.928414	120.738557	50	27.17	2344.7	Annam clay loam	clay loam	Uplands	0
588	\N	Region I	Pangasinan	Umingan	Pemienta	15.921364	120.826464	93	26.46	2606.4	Umingan silt loam	silt loam	Lowlands	0
591	\N	Region I	Pangasinan	Umingan	Prado	15.898269	120.769977	71	26.5	2606.4	Annam clay loam	clay loam	Uplands	0
592	\N	Region I	Pangasinan	Umingan	Resurreccion	15.889138	120.736712	64	27.15	2344.7	Annam clay loam	clay loam	Uplands	0
593	\N	Region I	Pangasinan	Umingan	Ricos	15.873677	120.845085	101	26.37	2387.5	Umingan silt loam	silt loam	Lowlands	0
601	\N	Region I	Pangasinan	Umingan	Sinabaan	15.929462	120.758363	63	26.53	2606.4	Annam clay loam	clay loam	Uplands	0
570	\N	Region I	Pangasinan	Umingan	Don Justo Abalos	15.9331	120.858857	126	26.49	2606.4	Umingan silt loam	silt loam	Lowlands	0
571	\N	Region I	Pangasinan	Umingan	Don Montano	15.917867	120.864067	133	26.49	2655.4	Umingan silt loam	silt loam	Lowlands	0
577	\N	Region I	Pangasinan	Umingan	La Paz	15.917262	120.736537	53	27.17	2344.7	Annam clay loam	clay loam	Uplands	0
581	\N	Region I	Pangasinan	Umingan	Luna Este	15.843488	120.806788	156	26.74	2271.9	Annam clay loam	clay loam	Uplands	0
582	\N	Region I	Pangasinan	Umingan	Luna Weste	15.863714	120.78535	77	26.91	2271.9	Annam clay loam	clay loam	Uplands	0
589	\N	Region I	Pangasinan	Umingan	Poblacion East	15.924	120.83936	110	26.57	2606.4	Umingan silt loam	silt loam	Lowlands	0
590	\N	Region I	Pangasinan	Umingan	Poblacion West	15.92582	120.83406	102	26.45	2606.4	Umingan silt loam	silt loam	Lowlands	0
594	\N	Region I	Pangasinan	Umingan	San Andres	15.9028	120.74565	58	27.16	2344.7	Annam clay loam	clay loam	Uplands	0
595	\N	Region I	Pangasinan	Umingan	San Juan	15.846791	120.7852	125	26.8	2271.9	Annam clay loam	clay loam	Uplands	0
596	\N	Region I	Pangasinan	Umingan	San Leon	15.908729	120.730271	53	27.17	2344.7	Annam clay loam	clay loam	Uplands	0
597	\N	Region I	Pangasinan	Umingan	San Pablo	15.8533	120.756267	71	26.92	2271.9	Annam clay loam	clay loam	Uplands	0
598	\N	Region I	Pangasinan	Umingan	San Vicente	15.876944	120.771775	69	26.92	2433.8	Annam clay loam	clay loam	Uplands	0
599	\N	Region I	Pangasinan	Umingan	Santa Maria	15.914922	120.779611	75	26.5	2606.4	Annam clay loam	clay loam	Uplands	0
600	\N	Region I	Pangasinan	Umingan	Santa Rosa	15.87836	120.74549	59	26.93	2433.8	Annam clay loam	clay loam	Uplands	0
637	\N	Region I	Pangasinan	Villasis	Amamperez	15.889357	120.537971	28	26.81	2666.7	San Manuel silt loam	silt loam	Lowlands	0
638	\N	Region I	Pangasinan	Villasis	Bacag	15.94225	120.586733	28	27.12	2440.6	San Manuel silt loam	silt loam	Lowlands	0
639	\N	Region I	Pangasinan	Villasis	Barangobong	15.8893	120.560333	26	26.82	2666.7	San Manuel silt loam	silt loam	Lowlands	0
640	\N	Region I	Pangasinan	Villasis	Barraca	15.918445	120.571791	26	26.82	2666.7	San Manuel silt loam	silt loam	Lowlands	0
641	\N	Region I	Pangasinan	Villasis	Capulaan	15.9044	120.541167	39	26.79	2666.7	San Manuel silt loam	silt loam	Lowlands	0
642	\N	Region I	Pangasinan	Villasis	Caramutan	15.926743	120.615186	30	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
644	\N	Region I	Pangasinan	Villasis	Labit	15.93212	120.53218	45	26.77	2666.7	San Manuel silt loam	silt loam	Lowlands	0
645	\N	Region I	Pangasinan	Villasis	Lipay	15.903943	120.605343	29	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
646	\N	Region I	Pangasinan	Villasis	Lomboy	15.917533	120.59255	27	27.12	2440.6	San Manuel silt loam	silt loam	Lowlands	0
647	\N	Region I	Pangasinan	Villasis	Piaz	15.942733	120.630389	34	27.1	2469.2	San Manuel sandy loam	sandy loam	Lowlands	0
648	\N	Region I	Pangasinan	Villasis	Puelay	15.896544	120.5858	31	26.9	2721.2	San Manuel silt loam	silt loam	Lowlands	0
651	\N	Region I	Pangasinan	Villasis	Tombod	15.9424	120.55932	24	26.82	2666.7	San Manuel silt loam	silt loam	Lowlands	0
652	\N	Region I	Pangasinan	Villasis	Unzad	15.919429	120.538629	44	26.78	2666.7	San Manuel silt loam	silt loam	Lowlands	0
619	\N	Region I	Pangasinan	Urdaneta City	Mabanogbog	15.985571	120.550257	25	26.95	2478.6	San Manuel silt loam	silt loam	Lowlands	0
620	\N	Region I	Pangasinan	Urdaneta City	Macalong	15.966733	120.617183	31	27.35	2260.2	San Manuel sandy loam	sandy loam	Lowlands	0
616	\N	Region I	Pangasinan	Urdaneta City	Dr. Pedro T. Orata	15.982133	120.614633	34	27.35	2260.2	San Manuel sandy loam	sandy loam	Lowlands	0
617	\N	Region I	Pangasinan	Urdaneta City	Labit Proper	15.961967	120.533333	20	26.78	2666.7	San Manuel silt loam	silt loam	Lowlands	0
618	\N	Region I	Pangasinan	Urdaneta City	Labit West	15.960729	120.507143	19	26.82	2637.1	San Manuel silt loam	silt loam	Lowlands	0
643	\N	Region I	Pangasinan	Villasis	La Paz	15.9178	120.51852	72	26.72	2666.7	San Fabian clay loam	clay loam	Highlands	0
649	\N	Region I	Pangasinan	Villasis	San Blas	15.91576	120.60112	28	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
650	\N	Region I	Pangasinan	Villasis	San Nicolas	15.922929	120.587429	27	27.12	2440.6	San Manuel silt loam	silt loam	Lowlands	0
653	\N	Region I	Pangasinan	Villasis	Zone I	15.90652	120.59052	27	27.12	2440.6	San Manuel silt loam	silt loam	Lowlands	0
654	\N	Region I	Pangasinan	Villasis	Zone II	15.9035	120.58634	30	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
655	\N	Region I	Pangasinan	Villasis	Zone III	15.90428	120.58448	30	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
656	\N	Region I	Pangasinan	Villasis	Zone IV	15.90622	120.58328	32	27.11	2440.6	San Manuel silt loam	silt loam	Lowlands	0
657	\N	Region I	Pangasinan	Villasis	Zone V	15.90906	120.5876	28	27.12	2440.6	San Manuel silt loam	silt loam	Lowlands	0
\.


--
-- Data for Name: monitoring_photo; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.monitoring_photo (photo_id, report_id, photo_url, date_time_taken, upload_time, inside_boundary, plot_id, file_hash, photo_type, latitude, longitude, distance_from_centroid_m, flags) FROM stdin;
1	1	uploads/monitoring/r1_1_20260828095407.jpg	\N	2026-08-28 09:54:07.663461	f	\N	e8b4ce660d4503e0d2f92f2ad41decc5ebfa5b24be5650bf64e03fc39774ecc2	plot	\N	\N	\N	no_exif
2	1	uploads/monitoring/r1_2_20260828095407.jpg	\N	2026-08-28 09:54:07.670577	f	\N	e8b4ce660d4503e0d2f92f2ad41decc5ebfa5b24be5650bf64e03fc39774ecc2	boundary	\N	\N	\N	no_exif,duplicate_in_report,duplicate_of_earlier_photo
3	2	uploads/monitoring/r2_1_20260828100903.jpg	2026-08-28 16:37:16	2026-08-28 10:09:03.271531	f	\N	f00203095d8d19c2e7e0cade557680edf1172f3cc6904ae04cd9588f127fc55a	plot	16.043846	120.64401	22702.7	outside_barangay
4	2	uploads/monitoring/r2_2_20260828100903.jpg	2026-08-28 16:37:16	2026-08-28 10:09:03.279227	f	\N	f00203095d8d19c2e7e0cade557680edf1172f3cc6904ae04cd9588f127fc55a	boundary	16.043846	120.64401	22702.7	duplicate_in_report,duplicate_of_earlier_photo,outside_barangay
5	4	uploads/monitoring/r4_1_20260831231106.jpg	2026-08-28 16:37:16	2026-08-31 23:11:06.782173	f	\N	f00203095d8d19c2e7e0cade557680edf1172f3cc6904ae04cd9588f127fc55a	plot	16.043846	120.64401	1255.3	duplicate_of_earlier_photo,outside_barangay
6	5	uploads/monitoring/r5_1_20260902064404.jpg	2026-09-02 13:34:08	2026-09-02 06:44:04.740045	f	\N	3aadd95befd76cba4a2b711ed3458c4be12512e632191e970b9f908a27aa5da3	boundary	16.043846	120.64401	11221.5	outside_barangay
7	5	uploads/monitoring/r5_2_20260902064404.jpg	2026-09-02 13:34:01	2026-09-02 06:44:04.748678	f	\N	1b978e4cc06a7d1528199fae4102f412806b1b4593de1c31c8fad733742655eb	boundary	16.043846	120.64401	11221.5	outside_barangay
8	5	uploads/monitoring/r5_3_20260902064404.jpg	2026-09-02 13:33:52	2026-09-02 06:44:04.75879	f	\N	b09ae8e40f8605c5c4d593d8b108b34fe63f60c4f0928d32c4d96db0493d5001	boundary	16.043846	120.64401	11221.5	outside_barangay
9	5	uploads/monitoring/r5_4_20260902064404.jpg	2026-09-02 13:33:42	2026-09-02 06:44:04.765485	f	\N	3bfcd8956344167f31a41fc7cb163d1093c5c170231b09f749cdfca416af698d	boundary	16.043846	120.64401	11221.5	outside_barangay
\.


--
-- Data for Name: monitoring_plot; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.monitoring_plot (plot_id, report_id, plot_number, seedlings_alive, plot_notes, latitude, longitude) FROM stdin;
1	1	1	35	5 ded	\N	\N
2	1	2	35	\N	\N	\N
3	1	3	35	\N	\N	\N
4	2	1	50	\N	\N	\N
5	2	2	35	\N	\N	\N
6	2	3	35	\N	\N	\N
7	3	1	63	\N	\N	\N
8	3	2	69	\N	\N	\N
9	3	3	68	\N	\N	\N
10	3	4	65	\N	\N	\N
11	4	1	46	\N	\N	\N
12	4	2	46	\N	\N	\N
13	4	3	46	\N	\N	\N
14	4	4	46	\N	\N	\N
15	4	5	46	\N	\N	\N
16	4	6	46	\N	\N	\N
17	4	7	46	\N	\N	\N
18	4	8	46	\N	\N	\N
19	4	9	46	\N	\N	\N
20	4	10	46	\N	\N	\N
21	5	1	750	\N	\N	\N
22	5	2	750	\N	\N	\N
23	5	3	750	\N	\N	\N
24	5	4	750	\N	\N	\N
\.


--
-- Data for Name: monitoring_report; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.monitoring_report (report_id, record_id, user_id, monitoring_date, survival_rate, record_version, approval_status, site_id, plots_recorded, plot_size_sqm, total_counted, mean_per_plot, stdev_per_plot, density_per_ha, estimated_survivors, sampling_intensity, captured_area_ha, area_difference_pct, boundary_geojson, remarks, review_note, reviewed_by, date_reviewed, submitted_at) FROM stdin;
2	73	2	2026-08-28	85.11	1	Rejected	73	3	400	120	40	7.07	1000	60000	0.2	\N	\N	\N	\N	too inconsistent	1	2026-08-28 10:11:33.882437	2026-08-28 10:09:03.201325
1	43	2	2026-08-28	87.5	1	Rejected	43	3	400	105	35	0	875	43750	0.24	\N	\N	\N	\N	low details need more	1	2026-08-28 10:11:49.840966	2026-08-28 09:54:07.388565
3	7	2	2026-08-31	99.3	1	Pending	7	4	400	265	66.25	2.38	1656.2	48031	0.55	\N	\N	\N	\N	\N	\N	\N	2026-08-31 22:16:28.226946
4	36	2	2026-08-31	97.87	1	Approved	36	10	400	460	46	0	1150	69000	0.67	\N	\N	\N	\N	\N	1	2026-08-31 23:20:53.985898	2026-08-31 23:11:06.421356
5	7	2	2026-09-02	89.93	1	Approved	7	4	5000	3000	750	0	1500	43500	6.9	\N	\N	\N	testing the site maker	\N	1	2026-09-02 06:45:04.735468	2026-09-02 06:44:04.557734
\.


--
-- Data for Name: notification; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notification (notification_id, user_id, report_id, notification_type, message, is_read, created_at) FROM stdin;
1	3	\N	Request Update	Your reforestation request for Atainan, Alcala is now Rejected. Note: wala	t	2026-08-25 09:13:27.936301
2	3	\N	Request Update	Your reforestation request for Cabaritan, San Manuel is now Approved.	t	2026-08-25 09:13:34.554199
5	3	\N	Request Update	Your reforestation request for AristonWeste, Asingan is now Rejected. Note: wala wlaa	t	2026-08-25 09:41:14.744514
3	3	\N	Request Update	Your reforestation request for Bugayong, Binalonan is now Approved.	t	2026-08-25 09:35:35.991545
4	1	\N	New Request	user_prime requested New Planting Site for AristonWeste, Asingan.	t	2026-08-25 09:36:23.692126
8	2	2	Report	Your monitoring report for Malico, San Nicolas was rejected. Note: too inconsistent	f	2026-08-28 10:11:33.914422
9	2	1	Report	Your monitoring report for Malico, San Nicolas was rejected. Note: low details need more	f	2026-08-28 10:11:49.84647
13	3	\N	Request Update	Your reforestation request for Dumayat, Binalonan is now Approved. Note: come to the office	t	2026-08-31 22:51:46.386942
15	2	4	Report	Your monitoring report for Santo Domingo, San Manuel was approved.	f	2026-08-31 23:20:54.030059
14	1	4	Report	officer_prime submitted a monitoring report for Santo Domingo, San Manuel. Survival 97.87%.	t	2026-08-31 23:11:06.787498
12	1	\N	New Request	user_prime requested New Planting Site for Dumayat, Binalonan.	t	2026-08-31 22:46:29.093773
11	1	\N	New Request	user_prime requested New Planting Site for Nagsaag, San Manuel.	t	2026-08-31 22:21:08.529524
10	1	3	Report	officer_prime submitted a monitoring report for Lapalo, San Manuel. Survival 99.3%.	t	2026-08-31 22:16:28.310042
7	1	2	Report	officer_prime submitted a monitoring report for Malico, San Nicolas. Survival 85.11%.	t	2026-08-28 10:09:03.2825
6	1	1	Report	officer_prime submitted a monitoring report for Malico, San Nicolas. Survival 87.5%.	t	2026-08-28 09:54:07.673621
17	2	5	Report	Your monitoring report for Lapalo, San Manuel was approved.	f	2026-09-02 06:45:04.768223
16	1	5	Report	officer_prime submitted a monitoring report for Lapalo, San Manuel. Survival 89.93%.	t	2026-09-02 06:44:04.769185
\.


--
-- Data for Name: organization; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.organization (organization_id, organization_name, organization_type) FROM stdin;
172	San Felipe Watershed Management Association, Inc.	Partner/Contractor
173	Barangay Council of Calunetan	Partner/Contractor
174	Cabalisyan Kalanguya Tribal Association, Inc.	Partner/Contractor
175	Dalumpinas Tree Planters Association, Inc.	Partner/Contractor
176	Viva Cacandungan San Jose Tree Planters Association, Inc.	Partner/Contractor
177	Barangay Government of Nangapugan	Partner/Contractor
178	Barangay Government of Lapalo	Partner/Contractor
179	Barangay Government of Cabangaran	Partner/Contractor
180	Rang-ay Bantay Association, Inc.	Partner/Contractor
181	Alibeng Bel-bel Upland Farmers Association, Inc.	Partner/Contractor
182	San Felipe Watershed Management Association,Inc.	Partner/Contractor
183	Skyline Green Forest Conservation Association,Inc.	Partner/Contractor
184	I-Owak Tribe Earth Savers Association,Inc.	Partner/Contractor
185	Ubbog ti Daya Multi-Purpose Cooperative	Partner/Contractor
186	Barangay Council of Salingcob	Partner/Contractor
187	Barangay Council of San Roque	Partner/Contractor
188	Cabalisian Tree Planters Association,Inc.	Partner/Contractor
189	Local Government of Santa Maria De Pila	Partner/Contractor
190	Alibeng Bel-bel Upland Farmers Association,Inc.	Partner/Contractor
191	Greener Environment for Maseil-seil Inc.	Partner/Contractor
192	Salpad Forest Workers Association,Inc.	Partner/Contractor
193	Mabini San Andres Balungao Hilltop Developers Association,Inc.	Partner/Contractor
194	Cabalisyan Kalanguya Tribal Association,Inc.	Partner/Contractor
195	Aquille Mountain Climbers Association,Inc.	Partner/Contractor
196	Animo Tacnien Association,Inc.	Partner/Contractor
198	Samahang Masa ng San eugenio Natividad Association,Inc.	Partner/Contractor
199	Dalumpinas Tree Planters Association,Inc.	Partner/Contractor
200	Puyao Forest Workers Association,Inc.	Partner/Contractor
201	Malico Indigeneous Peoples Development Association,Inc.	Partner/Contractor
202	Barangay Government of Casantamaria-an	Partner/Contractor
207	NAEVAM Irrigators Association,Inc.	Partner/Contractor
208	Rang-ay Bantay Association,Inc.	Partner/Contractor
209	Viva Cacandungan San Jose Tree Planters Association,Inc.	Partner/Contractor
220	Puyao Forest Workers Association, Inc.	Partner/Contractor
221	Mabini San Andres Balungao Hilltop Developers Association Inc.	Partner/Contractor
222	MLGU Pangasinan	Partner/Contractor
223	BLGU Casantamarian	Partner/Contractor
224	Skyline Green Forest Conservation Association, Inc.	Partner/Contractor
\.


--
-- Data for Name: reforestation_record; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reforestation_record (record_id, site_id, tree_id, date_planted, target_quantity, date_validated, survival_rate, actual_quantity_planted) FROM stdin;
1	1	2	2021-03-22	33462	2023-11-24	0.8761	33462
2	2	2	2021-03-22	12500	2023-11-28	0.885	12500
3	3	2	2021-03-22	25000	2023-11-23	0.87	25000
4	4	2	2021-03-22	41700	2023-11-21	0.8959	41700
5	5	2	2021-03-22	50040	2023-11-29	0.889	50040
6	6	2	2021-03-22	12500	2023-11-22	0.865	12500
8	8	2	2021-03-22	41700	2023-11-21	0.89	41700
9	9	2	2022-03-25	10000	2024-11-27	0.862	10000
10	10	2	2022-03-25	19000	2024-11-21	0.8752	19000
11	11	2	2022-03-25	5000	2024-11-28	0.8664	5000
12	12	2	2022-03-25	5000	2024-11-27	0.8978	5000
13	13	2	2026-08-18	60040	2025-11-21	0.8624	60040
14	14	2	2017-03-30	6000	2019-10-10	0.8832	6000
15	15	2	2017-03-30	83300	2019-09-28	0.896	83300
16	16	2	2017-03-30	10000	2019-11-14	0.8676	10000
17	17	2	2017-03-28	6000	2019-10-30	0.9044	6000
18	18	2	2017-03-28	5000	2019-11-21	0.8706	5000
19	19	2	2017-03-28	10000	2019-10-19	0.8836	10000
20	20	2	2017-03-29	8000	2019-10-10	0.8832	8000
21	21	2	2017-03-28	10000	2019-11-14	0.8676	10000
22	22	2	2017-03-30	10000	2019-09-10	0.8824	10000
23	23	2	2017-03-28	5000	2019-10-01	0.8752	5000
24	24	2	2017-03-16	83300	2019-09-12	0.8873	83300
25	25	2	2017-03-30	83300	2019-10-29	0.8991	83300
26	26	2	2017-03-16	83300	2019-11-20	0.8558	83300
27	27	2	2017-03-13	83300	2019-09-05	0.9371	83300
28	28	2	2017-03-10	83300	2019-09-20	0.864	83300
29	29	2	2017-03-30	83300	2019-10-11	0.8668	83300
30	30	2	2017-03-13	83300	2019-09-12	0.92	83300
31	31	2	2017-03-28	83586	2019-09-04	0.9213	83586
32	32	2	2017-03-28	83300	2019-10-02	0.8957	83300
33	33	2	2017-04-10	83300	2019-10-17	0.8689	83300
34	34	2	2018-02-28	70500	2020-11-18	0.93	70500
35	35	2	2018-02-23	70500	2020-11-24	0.87	70500
37	37	2	2018-02-23	50000	2020-10-30	0.8716	50000
38	38	2	2018-02-23	50000	2020-10-29	0.8698	50000
39	39	2	2018-02-23	50000	2020-11-10	0.8805	50000
40	40	2	2018-02-23	70500	2020-11-06	0.8761	70500
41	41	2	2018-02-23	70500	2020-11-04	0.8918	70500
42	42	2	2018-02-23	50000	2020-11-13	0.89	50000
43	43	2	2018-02-23	50000	2020-11-13	0.9	50000
44	44	2	2018-02-28	83300	2020-11-04	0.8519	83300
45	45	2	2019-06-20	58750	2020-11-10	0.8822	58750
46	46	2	2018-02-22	50000	2020-11-27	0.899	50000
47	47	2	2020-03-12	24990	2022-11-11	0.8675	24990
48	48	2	2020-03-12	41650	2022-11-11	0.8624	41650
49	49	2	2020-03-12	33320	2022-11-10	0.8624	33320
50	50	2	2020-03-12	33320	2022-11-08	0.8544	33320
51	51	2	2020-03-12	33320	2022-11-09	0.8574	33320
52	52	2	2020-03-12	41650	2022-11-24	0.8579	41650
53	53	2	2020-03-12	41650	2022-11-23	0.8572	41650
54	54	2	2020-03-12	41650	2022-11-24	0.8609	41650
55	55	2	2020-03-12	41650	2022-11-24	0.8531	41650
56	56	2	2020-03-12	15000	2022-10-26	0.8891	15000
57	57	2	2020-03-12	15000	2022-10-27	0.8975	15000
58	58	2	2020-07-23	33320	2022-11-17	0.87	33320
59	59	2	2020-03-12	21000	2022-11-15	0.8655	21000
60	60	2	2020-07-23	15172	2022-11-16	0.8661	15172
61	61	2	2020-07-23	33320	2022-11-15	0.8652	33320
62	62	2	2020-03-12	41650	2022-11-09	0.8745	41650
63	63	2	2020-03-12	41650	2022-11-10	0.8715	41650
64	64	2	2020-03-12	41650	2022-11-17	0.8657	41650
65	65	2	2020-03-12	41650	2022-11-18	0.875	41650
66	66	2	2020-07-23	25000	2022-10-27	0.86	25000
67	67	2	2020-07-23	41650	2022-10-27	0.873	41650
68	68	2	2020-03-12	41650	2022-11-23	0.87	41650
69	69	2	2026-08-18	20000	\N	\N	20000
70	70	2	2026-08-18	4000	\N	\N	4000
72	72	2	2026-08-18	17000	\N	\N	17000
73	73	2	2026-08-18	70500	\N	\N	70500
36	36	2	2018-02-23	70500	2026-08-31	97.87	70500
7	7	2	2021-03-22	48372	2026-09-02	89.93	48372
\.


--
-- Data for Name: request; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.request (request_id, user_id, request_type, description, status, location_id, proposed_area_ha, contact_number, date_submitted, date_reviewed, reviewed_by, review_note) FROM stdin;
1	3	New Planting Site	gusto ko mag karoon ng reforestation site	Rejected	202	25	09927581922	2026-08-25 09:07:15.763273	2026-08-25 09:13:27.916884	1	wala
2	3	New Planting Site	gusto ko mag karoon ng reforestation site	Approved	414	25	09927581922	2026-08-25 09:08:58.059067	2026-08-25 09:13:34.543253	1	\N
3	3	New Planting Site	please	Approved	282	45	\N	2026-08-25 09:18:22.680213	2026-08-25 09:35:35.985683	1	\N
4	3	New Planting Site	qweqdq	Rejected	223	54	1316210	2026-08-25 09:36:23.675425	2026-08-25 09:41:14.724127	1	wala wlaa
5	3	New Planting Site	gusto ko ng site sa bahay ko	Submitted	418	2.5	\N	2026-08-31 22:21:08.514711	\N	\N	\N
6	3	New Planting Site	d ko alam yung exact measurement	Approved	287	2.5	\N	2026-08-31 22:46:29.06855	2026-08-31 22:51:46.368141	1	come to the office
\.


--
-- Data for Name: site; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.site (site_id, location_id, organization_id, site_name, area_size_ha, date_established, site_status, climate_zone, soil_type, site_code, zone_type, loa_contract_code, year_contracted, area_contracted_ha, date_contract_executed, date_contract_expiry, project_cost_3yr, retention_fee_amount_paid, retention_fee_date_paid, amount_under_land_improvement, amount_still_in_cip, penro, cenro, congressional_district, land_classification, major_land_use, contact_person, component, commodity, boundary_geojson, boundary_area_ha, boundary_captured_at) FROM stdin;
4	175	175	Dalumpinas, San Nicolas Reforestation Site	25	2021-03-22	Active	\N	\N	21-015546-0074-0025	Production	21-015546-0025-071	2021	25	2021-03-22	2023-12-31	796100.00	\N	\N	\N	796100.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Ruben Martinez	Reforestation	Timber	\N	\N	\N
5	176	176	Cacandungan, Natividad Reforestation Site	30	2021-03-22	Active	\N	\N	21-015546-0075-0030	Production	21-015546-0030-072	2021	30	2021-03-22	2023-12-31	955320.00	\N	\N	\N	955320.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Monico Castillo	Reforestation	Timber	\N	\N	\N
7	178	178	Lapalo, San Manuel Reforestation Site	29	2021-03-22	Active	\N	\N	21-015546-0077-0029	Production	21-015546-0029-074	2021	29	2021-03-22	2023-12-31	923476.00	\N	\N	\N	778476.00	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Wilferdo Cayoao	Reforestation	Timber	\N	\N	\N
8	179	179	Cabangaran, San Quintin Reforestation Site	25	2021-03-22	Active	\N	\N	21-015546-0078-0025	Production	21-015546-0025-075	2021	25	2021-03-22	2023-12-31	796100.00	\N	\N	\N	796100.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Julio Ramos	Reforestation	Timber	\N	\N	\N
9	174	174	Santa Maria East, San Nicolas Reforestation Site	20	2022-03-25	Active	\N	\N	22-015546-0071-0020	Production and Protection	22-015546-0020-068	2022	20	2022-03-25	2024-12-31	520000.00	\N	\N	\N	520000.00	Pangasinan	Urdaneta City	VI	Regular	Agno River Basin	Carlito Alvarez	Agroforestry	Fruit trees	\N	\N	\N
12	173	173	Calunetan, Sison Reforestation Site	10	2022-03-25	Active	\N	\N	22-015546-0074-0010	Production	22-015546-0010-071	2022	10	2022-03-25	2024-12-31	260000.00	\N	\N	\N	260000.00	Pangasinan	Urdaneta City	V	Regular	Toboy-Tacnien River Watershed	Fernando Abitong	Agroforestry	Fruit trees	\N	\N	\N
13	181	181	Alibeng, Sison Reforestation Site	50	2026-08-18	Active	\N	\N	23-015546-0004-0050	Production	23-015546-0050-004	2023	50	\N	2025-12-30	\N	\N	\N	\N	\N	Pangasinan	Urdaneta City	V	Watershed	Taboy-Tacnien River Watershed	Mr. Renerio S. Ingean Jr.	Agroforestry	Fruit trees, Timber	\N	\N	\N
15	182	183	Malico, San Nicolas Reforestation Site	50	2017-03-30	Active	\N	\N	17-015545-0174-0050	Protection	17-015546-0050-227	2017	50	2017-03-30	2019-12-31	1891400.00	\N	2021-06-21	2041400.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Romy Paay	Agroforestry	Coffee,Timber	\N	\N	\N
16	183	184	Fianza, San Nicolas Reforestation Site	50	2017-03-30	Active	\N	\N	17-015546-0088-0050	Production and Protection	17-015546-0050-216	2017	50	2017-03-30	2019-12-31	975000.00	\N	2021-06-28	\N	1125000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Bamboo	\N	\N	\N
18	177	177	Nangapugan, San Quintin Reforestation Site	25	2017-03-28	Active	\N	\N	17-015546-0090-0025	Production	17-015546-0025-218	2017	25	2017-03-28	2019-12-31	562500.00	\N	2021-06-29	562500.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Imelda Abuan	Reforestation	Bamboo	\N	\N	\N
2	173	173	Calunetan, Sison Reforestation Site	25	2021-03-22	Active	\N	\N	21-015546-0072-0025	Production	21-015546-0025-069	2021	25	2021-03-22	2023-12-31	900000.00	\N	\N	\N	900000.00	Pangasinan	Urdaneta City	V	\N	Bued River Watershed, Toboy-Tacnien River Watershed	Fernando Abitong	Agroforestry	Fruit trees,Timber	\N	\N	\N
19	184	186	Salingcob, San Nicolas Reforestation Site	50	2017-03-28	Active	\N	\N	17-015546-0091-0050	Production	17-015546-0050-219	2017	50	2017-03-28	2019-12-31	1125000.00	\N	2021-06-29	1125000.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Cesario Marquez	Reforestation	Bamboo	\N	\N	\N
20	172	182	San Felipe East, San Nicolas Reforestation Site	40	2017-03-29	Active	\N	\N	17-015546-0093-0040	Protection	17-015546-0040-221	2017	40	2017-03-29	2019-12-31	900000.00	\N	\N	\N	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Fernando Amarillo	Reforestation	Bamboo	\N	\N	\N
22	174	188	Santa Maria East, San Nicolas Reforestation Site	50	2017-03-30	Active	\N	\N	17-015546-0095-0050	Production	17-015546-0050-223	2017	50	2017-03-30	2019-12-31	1125000.00	\N	2021-07-05	1125000.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Francisco Florentin	Reforestation	Bamboo	\N	\N	\N
23	186	189	Santa Rosa, Santa Maria Reforestation Site	25	2017-03-28	Active	\N	\N	17-015546-0096-0025	Production	17-015546-0025-224	2017	25	2017-03-28	2019-12-31	562500.00	\N	2021-06-29	562500.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Municipal Mayor	Reforestation	Bamboo	\N	\N	\N
25	183	185	Fianza, San Nicolas Reforestation Site	50	2017-03-30	Active	\N	\N	17-015546-0173-0050	Production and Protection	17-015546-0050-226	2017	50	2017-03-30	2019-12-31	2041400.00	\N	\N	\N	2041400.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Jovencio Macayan	Reforestation	Coffee,Fruit trees	\N	\N	\N
26	187	191	Maseil-seil, Umingan Reforestation Site	50	2017-03-16	Active	\N	\N	17-015546-0175-0050	Production	17-015546-0050-228	2017	50	2017-03-16	2019-12-31	2041400.00	\N	2021-07-05	2041400.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Benito Valdrez	Agroforestry	Fruit trees,Timber	\N	\N	\N
28	189	193	San Andres, Balungao Reforestation Site	50	2017-03-10	Active	\N	\N	17-015546-0177-0050	Production	17-015546-0050-230	2017	50	2017-03-10	2019-12-31	2041400.00	\N	2021-06-21	2041400.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Marcelo Cabito	Agroforestry	Fruit trees,Timber	\N	\N	\N
29	172	182	San Felipe East, San Nicolas Reforestation Site	50	2017-03-30	Active	\N	\N	17-015546-0178-0050	Production and Protection	17-015546-0050-231	2017	50	2017-03-30	2019-12-31	2041400.00	\N	\N	\N	2041400.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Fernando Amarillo	Agroforestry	Fruit trees,Timber	\N	\N	\N
31	174	195	Santa Maria East, San Nicolas Reforestation Site	50	2017-03-28	Active	\N	\N	17-015546-0180-0050	Production	17-015546-0050-233	2017	50	2017-03-28	2019-12-31	2041400.00	\N	\N	\N	2041400.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Teresa Abrue	Agroforestry	Fruit trees,Timber	\N	\N	\N
32	180	196	Santo Domingo, San Manuel Reforestation Site	50	2017-03-28	Active	\N	\N	17-015546-0181-0050	Production	17-015546-0050-234	2017	50	2017-03-28	2019-12-31	2041400.00	\N	2021-07-05	2041400.00	\N	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Wilfredo Jaime	Agroforestry	Fruit trees,Timber	\N	\N	\N
34	183	184	Fianza, San Nicolas Reforestation Site	60	2018-02-28	Active	\N	\N	18-015545-0217-0060	Production and Protection	18-015546-0060-204	2018	60	2018-02-28	2020-12-31	1614000.00	\N	\N	\N	1614000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Timber	\N	\N	\N
35	191	198	San Eugenio, Natividad Reforestation Site	60	2018-02-23	Active	\N	\N	18-015546-0210-0060	Production and Protection	18-015546-0060-197	2018	60	2018-02-23	2020-12-31	1614000.00	\N	\N	\N	1614000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Fernando Ilasin	Reforestation	Timber	\N	\N	\N
36	180	196	Santo Domingo, San Manuel Reforestation Site	60	2018-02-23	Active	\N	\N	18-015546-0211-0060	Production	18-015546-0060-198	2018	60	2018-02-23	2020-12-31	1614000.00	\N	\N	\N	1614000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Alfredo Jaime	Reforestation	Timber	\N	\N	\N
38	183	185	Fianza, San Nicolas Reforestation Site	50	2018-02-23	Active	\N	\N	18-015546-0213-0050	Production and Protection	18-015546-0050-200	2018	50	2018-02-23	2020-12-31	1820050.00	\N	\N	\N	1820050.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Jovencio Macayan	Agroforestry	Coffee,Fruit trees,Timber	\N	\N	\N
39	183	200	Fianza, San Nicolas Reforestation Site	50	2018-02-23	Active	\N	\N	18-015546-0214-0050	Production	18-015546-0050-201	2018	50	2018-02-23	2020-12-31	1820050.00	\N	\N	\N	1820050.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Herminigildo Ayang	Agroforestry	Fruit trees,Timber	\N	\N	\N
1	172	172	San Felipe East, San Nicolas Reforestation Site	20	2021-03-22	Active	\N	\N	21-015546-0071-0020	Production and Protection	21-015546-0020-068	2021	20	2021-03-22	2023-12-31	637696.00	\N	\N	\N	637696.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Fernando Amarillo	Reforestation	Timber	\N	\N	\N
3	174	174	Santa Maria East, San Nicolas Reforestation Site	50	2021-03-22	Active	\N	\N	21-015546-0073-0050	Production	21-015546-0050-070	2021	50	2021-03-22	2023-12-31	1800000.00	\N	\N	\N	1800000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Agroforestry	Fruit trees,Timber	\N	\N	\N
6	177	177	Nangapugan, San Quintin Reforestation Site	25	2021-03-22	Active	\N	\N	21-015546-0076-0025	Production	21-015546-0025-073	2021	25	2021-03-22	2023-12-31	900000.00	\N	\N	\N	900000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Imelda Abuan	Agroforestry	Fruit trees,Timber	\N	\N	\N
40	174	188	Santa Maria East, San Nicolas Reforestation Site	60	2018-02-23	Active	\N	\N	18-015546-0215-0060	Production and Protection	18-015546-0060-202	2018	60	2018-02-23	2020-12-31	1614000.00	\N	\N	\N	1614000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Francisco Florentin	Reforestation	Timber	\N	\N	\N
41	174	194	Santa Maria East, San Nicolas Reforestation Site	60	2018-02-23	Active	\N	\N	18-015546-0216-0060	Production and Protection	18-015546-0060-203	2018	60	2018-02-23	2020-12-31	1614000.00	\N	\N	\N	1614000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Reforestation	Timber	\N	\N	\N
43	182	183	Malico, San Nicolas Reforestation Site	50	2018-02-23	Active	\N	\N	18-015546-0219-0050	Protection	18-015546-0050-206	2018	50	2018-02-23	2020-12-31	1820050.00	\N	\N	\N	1820050.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Romy Paay	Reforestation	Coffee,Fuelwood	\N	\N	\N
44	192	202	Casantamarian, San Quintin Reforestation Site	50	2018-02-28	Active	\N	\N	18-015546-0220-0050	Production	18-015546-0050-207	2018	50	2018-02-28	2020-12-31	2624500.00	\N	\N	\N	2124500.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Zenaida Liberato	Reforestation	Ilang ilang	\N	\N	\N
45	179	179	Cabangaran, San Quintin Reforestation Site	50	2019-06-20	Active	\N	\N	18-015546-0221-0050	Production	18-015546-0050-208	2018	50	2019-06-20	2020-12-31	1345000.00	\N	\N	\N	1270000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Rudy Ramos Sr.	Reforestation	Timber	\N	\N	\N
70	189	221	San Andres, Balungao Reforestation Site	20	2026-08-18	Active	\N	\N	18-015546-0235-0020	Production	18-015546-0020-210	2018	20	\N	\N	\N	\N	\N	\N	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Marcelo B. Cabico	Reforestation	Bamboo	\N	\N	\N
73	182	224	Malico, San Nicolas Reforestation Site	60	2026-08-18	Active	\N	\N	18-015546-0270-0060	Production	18-015546-0060-212	2018	60	\N	\N	\N	\N	\N	\N	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Romy L. Paay	Reforestation	Timber	\N	\N	\N
48	174	194	Santa Maria East, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0107-0025	Production and Protection	20-015546-0085-102	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Reforestation	Timber	\N	\N	\N
49	174	194	Santa Maria East, San Nicolas Reforestation Site	20	2020-03-12	Active	\N	\N	20-015546-0108-0020	Production and Protection	20-015546-0085-102	2020	20	2020-03-12	2022-12-31	636560.00	\N	\N	\N	636560.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Reforestation	Timber	\N	\N	\N
50	174	194	Santa Maria East, San Nicolas Reforestation Site	20	2020-03-12	Active	\N	\N	20-015546-0109-0020	Production	20-015546-0085-102	2020	20	2020-03-12	2022-12-31	636560.00	\N	\N	\N	636560.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Reforestation	Timber	\N	\N	\N
52	183	184	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0111-0025	Production and Protection	20-015546-0100-103	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Timber	\N	\N	\N
53	183	184	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0112-0025	Production and Protection	20-015546-0100-103	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Timber	\N	\N	\N
54	183	184	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0113-0025	Production and Protection	20-015546-0100-103	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Timber	\N	\N	\N
56	173	173	Calunetan, Sison Reforestation Site	15	2020-03-12	Active	\N	\N	20-015546-0115-0015	Production	20-015546-0030-104	2020	15	2020-03-12	2022-12-31	540000.00	\N	\N	\N	540000.00	Pangasinan	Urdaneta City	V	\N	Bued River Watershed	Fernando Abitong	Agroforestry	Agroforestry	\N	\N	\N
57	173	173	Calunetan, Sison Reforestation Site	15	2020-03-12	Active	\N	\N	20-015546-0116-0015	Production	20-015546-0030-104	2020	15	2020-03-12	2022-12-31	540000.00	\N	\N	\N	540000.00	Pangasinan	Urdaneta City	V	\N	Bued River Watershed	Fernando Abitong	Agroforestry	Agroforestry	\N	\N	\N
59	183	200	Fianza, San Nicolas Reforestation Site	21	2020-03-12	Active	\N	\N	20-015546-0118-0021	Production	20-015546-0020-106	2020	21	2020-03-12	2022-12-31	756000.00	\N	\N	\N	756000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Herminigildo Ayang	Agroforestry	Fruit trees,Timber	\N	\N	\N
60	183	200	Fianza, San Nicolas Reforestation Site	9	2020-07-23	Active	\N	\N	20-015546-0119-0009	Production	20-015546-0029-106	2020	9	2020-07-23	2022-12-31	287876.00	\N	\N	\N	287876.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Herminigildo Ayang	Agroforestry	Fruit trees,Timber	\N	\N	\N
62	180	208	Santo Domingo, San Manuel Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0121-0025	Production	20-015546-0050-107	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Rolando Apilado	Reforestation	Timber	\N	\N	\N
63	180	208	Santo Domingo, San Manuel Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0122-0025	Production	20-015546-0050-107	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Rolando Apilado	Reforestation	Timber	\N	\N	\N
65	183	185	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0124-0025	Production	20-015546-0050-108	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Jovencio Macayan	Reforestation	Timber	\N	\N	\N
66	176	209	Cacandungan, Natividad Reforestation Site	25	2020-07-23	Active	\N	\N	20-015546-0125-0025	Production	20-015546-0050-109	2020	25	2020-07-23	2022-12-31	900000.00	\N	\N	\N	900000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Monico Castillo	Agroforestry	Fruit trees,Timber	\N	\N	\N
68	194	207	Calitlitan, Umingan Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0127-0025	Production and Protection	20-015546-0025-110	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Raul Paluyo	Reforestation	Timber	\N	\N	\N
10	175	175	Dalumpinas, San Nicolas Reforestation Site	38	2022-03-25	Active	\N	\N	22-015546-0072-0038	Production	22-015546-0038-069	2022	38	2022-03-25	2024-12-31	988000.00	\N	\N	\N	988000.00	Pangasinan	Urdaneta City	VI	Regular	Agno River Basin	Ruben Martinez	Agroforestry	Fruit trees	\N	\N	\N
11	180	180	Santo Domingo, San Manuel Reforestation Site	10	2022-03-25	Active	\N	\N	22-015546-0073-0010	Production	22-015546-0010-070	2022	10	2022-03-25	2024-12-31	260000.00	\N	\N	\N	310000.00	Pangasinan	Urdaneta City	VI	Regular	Toboy-Tacnien River Watershed	Ronaldo Apilado	Agroforestry	Fruit trees	\N	\N	\N
14	172	182	San Felipe East, San Nicolas Reforestation Site	30	2017-03-30	Active	\N	\N	17-015545-0092-0030	Production	17-015546-0030-220	2017	30	2017-03-30	2019-12-31	585000.00	\N	2021-06-28	1575000.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Fernando Amarillo	Reforestation	Bamboo	\N	\N	\N
17	183	185	Fianza, San Nicolas Reforestation Site	30	2017-03-28	Active	\N	\N	17-015546-0089-0030	Production and Protection	17-015546-0030-217	2017	30	2017-03-28	2019-12-31	585000.00	\N	\N	\N	675000.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Jovencio Macayan	Reforestation	Bamboo	\N	\N	\N
21	185	187	San Roque, San Manuel Reforestation Site	50	2017-03-28	Active	\N	\N	17-015546-0094-0050	Production and Protection	17-015546-0050-222	2017	50	2017-03-28	2019-12-31	1125000.00	\N	2021-06-21	1125000.00	\N	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Primo Lopez	Reforestation	Bamboo	\N	\N	\N
24	181	190	Alibeng, Sison Reforestation Site	50	2017-03-16	Active	\N	\N	17-015546-0172-0050	Production	17-015546-0050-225	2017	50	2017-03-16	2019-12-31	2041400.00	\N	2021-07-05	2041400.00	\N	Pangasinan	Urdaneta City	V	\N	Toboy-Tacnien River Watershed	Eduardo Luzan	Reforestation	Fruit trees,Timber	\N	\N	\N
27	188	192	Salpad, San Nicolas Reforestation Site	50	2017-03-13	Active	\N	\N	17-015546-0176-0050	Production	17-015546-0050-229	2017	50	2017-03-13	2019-12-31	2041400.00	\N	\N	\N	2041400.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Danilo Serios	Agroforestry	Fruit trees,Timber	\N	\N	\N
30	174	194	Santa Maria East, San Nicolas Reforestation Site	50	2017-03-13	Active	\N	\N	17-015546-0179-0050	Production	17-015546-0050-232	2017	50	2017-03-13	2019-12-31	2041400.00	\N	\N	\N	2041400.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Agroforestry	Fruit trees,Timber	\N	\N	\N
33	177	177	Nangapugan, San Quintin Reforestation Site	50	2017-04-10	Active	\N	\N	17-015546-0195-0050	Production	17-015546-0050-235	2017	50	2017-04-10	2019-12-31	2024500.00	\N	2021-07-05	2024500.00	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Imelda Abuan	Reforestation	Ilang ilang	\N	\N	\N
37	175	199	Dalumpinas, San Nicolas Reforestation Site	50	2018-02-23	Active	\N	\N	18-015546-0212-0050	Production	18-015546-0050-199	2018	50	2018-02-23	2020-12-31	1820050.00	\N	\N	\N	1820050.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Ruben Martinez	Agroforestry	Fruit trees,Timber	\N	\N	\N
42	182	201	Malico, San Nicolas Reforestation Site	50	2018-02-23	Active	\N	\N	18-015546-0218-0050	Production and Protection	18-015546-0050-205	2018	50	2018-02-23	2020-12-31	1820050.00	\N	\N	\N	1820050.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Tito Ancheta	Reforestation	Coffee,Fuelwood	\N	\N	\N
46	173	173	Calunetan, Sison Reforestation Site	50	2018-02-22	Active	\N	\N	18-015546-0222-0050	Production	18-015546-0050-209	2018	50	2018-02-22	2020-12-31	1820050.00	\N	\N	\N	1539542.50	Pangasinan	Urdaneta City	V	\N	Bued River Watershed, Toboy-Tacnien River Watershed	Fernando Abitong	Reforestation	Agroforestry	\N	\N	\N
72	192	223	Casantamarian, San Quintin Reforestation Site	17	2026-08-18	Active	\N	\N	18-015546-0269-0017	Production	18-015546-0017-211	2018	17	\N	\N	\N	\N	\N	\N	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Zenaida A. Liberato	Agroforestry	Agroforestry	\N	\N	\N
47	180	196	Santo Domingo, San Manuel Reforestation Site	15	2020-03-12	Active	\N	\N	20-015546-0106-0015	Production	20-015546-0015-101	2020	15	2020-03-12	2022-12-31	477420.00	\N	\N	\N	447420.00	Pangasinan	Urdaneta City	VI	\N	Toboy-Tacnien River Watershed	Alfredo Jaime	Reforestation	Timber	\N	\N	\N
51	174	194	Santa Maria East, San Nicolas Reforestation Site	20	2020-03-12	Active	\N	\N	20-015546-0110-0020	Production and Protection	20-015546-0085-102	2020	20	2020-03-12	2022-12-31	636560.00	\N	\N	\N	636560.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Carlito Alvarez	Reforestation	Timber	\N	\N	\N
55	183	184	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0114-0025	Production and Protection	20-015546-0100-103	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Felix Lorenzo	Reforestation	Timber	\N	\N	\N
58	177	207	Nangapugan, San Quintin Reforestation Site	20	2020-07-23	Active	\N	\N	20-015546-0117-0020	Production and Protection	20-015546-0020-105	2020	20	2020-07-23	2022-12-31	636560.00	\N	\N	\N	636560.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Raul Paluyo	Reforestation	Timber	\N	\N	\N
61	183	200	Fianza, San Nicolas Reforestation Site	20	2020-07-23	Active	\N	\N	20-015546-0120-0020	Production	20-015546-0029-106	2020	20	2020-07-23	2022-12-31	636560.00	\N	\N	\N	636560.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Herminigildo Ayang	Agroforestry	Fruit trees,Timber	\N	\N	\N
64	183	185	Fianza, San Nicolas Reforestation Site	25	2020-03-12	Active	\N	\N	20-015546-0123-0025	Production	20-015546-0050-108	2020	25	2020-03-12	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Jovencio Macayan	Reforestation	Timber	\N	\N	\N
67	176	209	Cacandungan, Natividad Reforestation Site	25	2020-07-23	Active	\N	\N	20-015546-0126-0025	Production	20-015546-0050-109	2020	25	2020-07-23	2022-12-31	795700.00	\N	\N	\N	795700.00	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Monico Castillo	Reforestation	Timber	\N	\N	\N
69	174	220	Sta. Maria East, San Nicolas Reforestation Site	40	2026-08-18	Active	\N	\N	17-015546-0279-0040	Production	17-015546-0040-236	2017	40	\N	\N	\N	\N	\N	\N	\N	Pangasinan	Urdaneta City	VI	\N	Agno River Basin	Herminildo Ayang	Reforestation	Indigeneous	\N	\N	\N
\.


--
-- Data for Name: spatial_ref_sys; Type: TABLE DATA; Schema: public; Owner: postgres
--



--
-- Data for Name: tree_specie; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tree_specie (tree_id, specie_name, scientific_name, native_to, min_rainfall_mm, max_rainfall_mm, min_elevation_m, max_elevation_m, min_temp_c, max_temp_c, preferred_soil, source, is_reference, salinity_requirement) FROM stdin;
2	Unspecified (Pending Match)	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	f	\N
4	Tamarind (Sampalok)	Tamarindus indica	\N	350	2700	0	1500	20	33	sandy loam,silt loam,clay loam,sand,silty clay loam	World Agroforestry Centre (ICRAF)	f	\N
5	Gmelina (Yemane)	Gmelina arborea	\N	750	4500	0	1200	21	35	sandy loam,silt loam	World Agroforestry Centre (ICRAF)	f	\N
9	Guyabano (Soursop)	Annona muricata	\N	1000	2500	0	1200	25	30	sandy loam,clay loam,silty clay loam	World Agroforestry Centre (ICRAF)	f	\N
10	Duhat (Java Plum)	Syzygium cumini	\N	900	5000	0	1800	20	32	silt loam,clay loam,sandy loam	World Agroforestry Centre (ICRAF)	f	\N
11	Bayog (Bamboo)	Bambusa blumeana var. luzonensis	\N	1500	3000	0	800	22	32	clay loam,silty clay loam,silt loam	World Agroforestry Centre (ICRAF)	f	\N
12	Coffee	Coffea canephora / arabica	\N	1500	2500	600	1800	18	25	silt loam,clay loam	World Agroforestry Centre (ICRAF)	f	\N
15	Batino	Alstonia macrophylla	\N	1500	3500	0	700	22	31	clay loam	World Agroforestry Centre (ICRAF)	f	\N
34	Hagakhak	Dipterocarpus validus	\N	2500	4500	0	300	24	32	silt loam,clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
35	Manggachapui	Hopea acuminata	\N	2200	4000	100	800	20	30	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
36	Narig	Vatica mangachapoi	\N	1800	3600	0	700	22	32	sandy loam,clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
18	Palosapis	Anisoptera thurifera	\N	1500	3500	0	700	22	33	clay loam,silty clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
37	Ipil	Intsia bijuga	\N	1500	3000	0	600	20	34	sandy loam,sand	World Agroforestry Centre (ICRAF)	t	1
17	Molave	Vitex parviflora	\N	800	2500	0	700	22	35	clay loam	World Agroforestry Centre (ICRAF)	t	0
38	Kamagong	Diospyros blancoi	\N	1600	3000	0	800	20	32	clay loam,silt loam	World Agroforestry Centre (ICRAF)	t	0
39	Tindalo	Afzelia rhomboidea	\N	1500	3000	0	500	22	32	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
16	Calumpit	Terminalia microcarpa	\N	1500	2500	0	800	22	30	silt loam,sandy loam,clay loam	World Agroforestry Centre (ICRAF)	f	\N
20	Benguet Pine (B.Pine)	Pinus kesiya	\N	1500	3000	300	2700	15	22	sandy loam,sand	World Agroforestry Centre (ICRAF)	f	\N
21	Atis (Sugar Apple)	Annona squamosa	\N	700	1200	0	1000	22	34	sandy loam,sand,silt loam	World Agroforestry Centre (ICRAF)	f	\N
7	Eucalyptus	Eucalyptus spp. (grandis/tereticornis)	\N	650	1800	0	1000	17	24	silt loam,clay loam	World Agroforestry Centre (ICRAF)	f	\N
22	Yakal-yamban	Shorea falciferoides	\N	2000	4500	0	800	22	32	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
23	Yakal-gisok	Shorea gisok	\N	2500	5000	0	700	22	32	clay loam,silty clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
24	Yakal-saplungan	Hopea plagata	\N	1800	3500	0	800	20	32	clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
25	Guijo	Shorea guiso	\N	1800	4000	0	600	22	34	clay loam,silty clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
26	Tangile	Shorea polysperma	\N	2500	4500	100	1500	18	28	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
27	Red Lauan	Shorea negrosensis	\N	2000	4000	0	1000	22	30	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
28	White Lauan	Shorea contorta	\N	2000	4500	0	900	22	32	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
29	Almon	Shorea almon	\N	2200	4000	0	800	22	31	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
30	Bagtikan	Parashorea malaanonan	\N	2000	5000	0	700	22	32	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
40	Acle	Albizia acle	\N	1200	2500	0	400	22	34	sandy loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
41	Banaba	Lagerstroemia speciosa	\N	1300	3500	0	800	18	35	silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
42	Katmon	Dillenia philippinensis	\N	1800	4000	0	1000	20	30	clay loam,silt loam	World Agroforestry Centre (ICRAF)	t	0
43	Toog	Petersianthus quadrialatus	\N	2500	5000	0	400	22	31	clay loam,silt loam	World Agroforestry Centre (ICRAF)	t	0
44	Supa	Sindora supa	\N	1500	2500	0	300	22	33	clay loam	World Agroforestry Centre (ICRAF)	t	0
45	Mangkono	Xanthostemon verdugonianus	\N	2000	4500	0	500	22	32	clay loam,sandy loam	World Agroforestry Centre (ICRAF)	t	0
46	Lanete	Wrightia pubescens	\N	1200	2800	0	600	20	34	sandy loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
47	Amugis	Koordersiodendron pinnatum	\N	2000	4000	0	800	21	32	clay loam,sandy loam	World Agroforestry Centre (ICRAF)	t	0
48	Dalingdingan	Hopea foxworthyi	\N	2200	3800	100	700	20	31	clay loam,sandy loam	World Agroforestry Centre (ICRAF)	t	0
49	Almaciga	Agathis philippinensis	\N	2000	5000	200	2000	12	25	sandy loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
31	Mayapis	Shorea palosapis	\N	2500	4500	0	1000	21	30	clay loam,silt loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
50	Benguet Pine	Pinus kesiya	\N	1500	3500	300	2700	10	24	sandy loam,sand	World Agroforestry Centre (ICRAF)	t	0
51	Mindoro Pine	Pinus merkusii	\N	1200	3000	50	1000	20	30	sandy loam,sand	World Agroforestry Centre (ICRAF)	t	0
52	Agoho del Monte	Gymnostoma rumphianum	\N	2000	4000	100	1200	18	28	sandy loam,sand	World Agroforestry Centre (ICRAF)	t	0
19	Alnus	Alnus nepalensis	\N	1500	4000	1000	3000	13	22	sand,sandy loam	World Agroforestry Centre (ICRAF)	t	0
53	Agoho	Casuarina equisetifolia	\N	700	3500	0	100	22	35	sand	World Agroforestry Centre (ICRAF)	t	2
54	Bitaog	Calophyllum inophyllum	\N	1200	4000	0	200	22	34	sand	World Agroforestry Centre (ICRAF)	t	2
68	Bakawan Babae	Rhizophora mucronata	\N	1500	4500	0	5	24	32	silt loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	3
69	Bakawan Lalake	Rhizophora apiculata	\N	1500	4500	0	5	24	32	silt loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	3
70	Api-api	Avicennia marina	\N	1000	4000	0	10	20	32	silt loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	3
71	Nypa	Nypa fruticans	\N	1500	4000	0	10	22	33	silt loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	3
55	Talisay	Terminalia catappa	\N	1000	3500	0	300	22	34	sand,sandy loam	World Agroforestry Centre (ICRAF)	t	1
56	Pili	Canarium ovatum	\N	2500	4500	0	500	24	32	clay loam,sandy loam	World Agroforestry Centre (ICRAF)	t	0
57	Mangga	Mangifera indica	\N	900	2500	0	1200	20	36	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
58	Lanka	Artocarpus heterophyllus	\N	1300	3000	0	1000	19	32	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
59	Santol	Sandoricum koetjape	\N	1500	3500	0	800	22	32	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
60	Duhat	Syzygium cumini	\N	900	3000	0	1000	18	35	silt loam,clay loam,sandy loam	World Agroforestry Centre (ICRAF)	t	0
61	Guyabano	Annona muricata	\N	1000	2500	0	1000	20	32	sandy loam,clay loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	0
62	Atis	Annona squamosa	\N	700	2000	0	800	22	34	sandy loam,sand,silt loam	World Agroforestry Centre (ICRAF)	t	0
14	Bignai	Antidesma bunius	\N	1200	3500	0	1200	18	32	sandy loam,silt loam,clay loam,sand,silty clay loam	World Agroforestry Centre (ICRAF)	t	0
63	Kasuy	Anacardium occidentale	\N	800	2000	0	800	22	38	sandy loam,sand	World Agroforestry Centre (ICRAF)	t	0
13	Ilang-ilang	Cananga odorata	\N	1500	3000	0	800	21	30	silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
64	Lumbang	Aleurites moluccanus	\N	1500	3000	0	1000	18	28	sandy loam,silt loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
6	Mahogany	Swietenia macrophylla	\N	1600	2500	0	1500	20	28	clay loam,silty clay loam	World Agroforestry Centre (ICRAF)	t	0
65	Gmelina	Gmelina arborea	\N	750	4500	0	1200	21	35	sandy loam,silt loam	World Agroforestry Centre (ICRAF)	t	0
32	Apitong	Dipterocarpus grandiflorus	\N	1500	3500	0	600	22	34	clay loam,silty clay loam	World Agroforestry Centre (ICRAF) / PROSEA	t	1
33	Panau	Dipterocarpus gracilis	\N	1800	3800	0	800	22	33	clay loam,sandy loam	World Agroforestry Centre (ICRAF) / PROSEA	t	0
3	Narra	Pterocarpus indicus	\N	900	4000	0	600	22	32	sandy loam,clay loam	World Agroforestry Centre (ICRAF)	t	0
66	Bagras	Eucalyptus ampullacea	\N	1500	3500	0	800	22	32	sandy loam,silt loam	World Agroforestry Centre (ICRAF)	t	0
8	Rain tree (Acacia)	Samanea saman	\N	600	3000	0	800	20	34	sandy loam,silt loam,clay loam,sand,silty clay loam	World Agroforestry Centre (ICRAF)	t	0
67	Kakawate	Gliricidia sepium	\N	900	2500	0	1200	22	32	sandy loam,silt loam,clay loam,sand,silty clay loam	World Agroforestry Centre (ICRAF)	t	0
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (user_id, organization_id, username, email_address, password_hash, role) FROM stdin;
1	\N	admin_prime	admin@puno.org	scrypt:32768:8:1$Qwreg4A4jedXweZi$9fa6476ba1fb8ea3975a98527fad12e0ff74498a0f1c2e8cc7040883fe0876d639dded885a2eb6d415cf674cf7bbecec88b6dcd01fd2ebefec5a1da7396a4860	admin
2	\N	officer_prime	officer1@puno.org	scrypt:32768:8:1$lPE3xnMjlKzo1ZeM$24d688bdd91217477dc2c2a20e4868982008125181e53fc7aba4fd5a323d2a0c1a59ce2c99f6ac9c2cf4c00c9207c3db44546c2d6e6e486a16d960ccdfabeb3a	field_officer
3	\N	user_prime	user@puno.org	scrypt:32768:8:1$nliz3uuWQ4QSLYCW$41d6aa3df756b7f33c6cca86fba6199abdab60f9201e69e6bb2e8a23251bc3d316d1381133d7301144d1e00b3bca24d8c2d531d3285ee82f0249d67aefee3650	normal_user
4	\N	ngo_user	ngo@gmail.com	scrypt:32768:8:1$iryLT3Fzro5TxrZf$d0f25061717a9598b5fa8209de7405c51691f92d14e6adcaf8e9726d0df67f94d89c3cd94a10ecc4aa61aa7acc0cdc3b87f682db10d74f56d6011e414ef3e924	normal_user
\.


--
-- Name: location_location_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.location_location_id_seq', 657, true);


--
-- Name: monitoring_photo_photo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.monitoring_photo_photo_id_seq', 9, true);


--
-- Name: monitoring_plot_plot_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.monitoring_plot_plot_id_seq', 24, true);


--
-- Name: monitoring_report_report_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.monitoring_report_report_id_seq', 5, true);


--
-- Name: notification_notification_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notification_notification_id_seq', 17, true);


--
-- Name: organization_organization_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.organization_organization_id_seq', 224, true);


--
-- Name: reforestation_record_record_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reforestation_record_record_id_seq', 73, true);


--
-- Name: request_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.request_request_id_seq', 6, true);


--
-- Name: site_site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.site_site_id_seq', 73, true);


--
-- Name: tree_specie_tree_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tree_specie_tree_id_seq', 71, true);


--
-- Name: users_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_user_id_seq', 4, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: location location_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.location
    ADD CONSTRAINT location_pkey PRIMARY KEY (location_id);


--
-- Name: location location_psgc_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.location
    ADD CONSTRAINT location_psgc_code_key UNIQUE (psgc_code);


--
-- Name: monitoring_photo monitoring_photo_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_photo
    ADD CONSTRAINT monitoring_photo_pkey PRIMARY KEY (photo_id);


--
-- Name: monitoring_plot monitoring_plot_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_plot
    ADD CONSTRAINT monitoring_plot_pkey PRIMARY KEY (plot_id);


--
-- Name: monitoring_report monitoring_report_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report
    ADD CONSTRAINT monitoring_report_pkey PRIMARY KEY (report_id);


--
-- Name: notification notification_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_pkey PRIMARY KEY (notification_id);


--
-- Name: organization organization_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.organization
    ADD CONSTRAINT organization_pkey PRIMARY KEY (organization_id);


--
-- Name: reforestation_record reforestation_record_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reforestation_record
    ADD CONSTRAINT reforestation_record_pkey PRIMARY KEY (record_id);


--
-- Name: request request_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.request
    ADD CONSTRAINT request_pkey PRIMARY KEY (request_id);


--
-- Name: site site_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_pkey PRIMARY KEY (site_id);


--
-- Name: site site_site_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_site_code_key UNIQUE (site_code);


--
-- Name: tree_specie tree_specie_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tree_specie
    ADD CONSTRAINT tree_specie_pkey PRIMARY KEY (tree_id);


--
-- Name: users users_email_address_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_address_key UNIQUE (email_address);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (user_id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: monitoring_photo monitoring_photo_plot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_photo
    ADD CONSTRAINT monitoring_photo_plot_id_fkey FOREIGN KEY (plot_id) REFERENCES public.monitoring_plot(plot_id);


--
-- Name: monitoring_photo monitoring_photo_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_photo
    ADD CONSTRAINT monitoring_photo_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.monitoring_report(report_id);


--
-- Name: monitoring_plot monitoring_plot_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_plot
    ADD CONSTRAINT monitoring_plot_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.monitoring_report(report_id);


--
-- Name: monitoring_report monitoring_report_record_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report
    ADD CONSTRAINT monitoring_report_record_id_fkey FOREIGN KEY (record_id) REFERENCES public.reforestation_record(record_id);


--
-- Name: monitoring_report monitoring_report_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report
    ADD CONSTRAINT monitoring_report_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(user_id);


--
-- Name: monitoring_report monitoring_report_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report
    ADD CONSTRAINT monitoring_report_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.site(site_id);


--
-- Name: monitoring_report monitoring_report_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.monitoring_report
    ADD CONSTRAINT monitoring_report_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: notification notification_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.monitoring_report(report_id);


--
-- Name: notification notification_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notification
    ADD CONSTRAINT notification_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: reforestation_record reforestation_record_site_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reforestation_record
    ADD CONSTRAINT reforestation_record_site_id_fkey FOREIGN KEY (site_id) REFERENCES public.site(site_id);


--
-- Name: reforestation_record reforestation_record_tree_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reforestation_record
    ADD CONSTRAINT reforestation_record_tree_id_fkey FOREIGN KEY (tree_id) REFERENCES public.tree_specie(tree_id);


--
-- Name: request request_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.request
    ADD CONSTRAINT request_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.location(location_id);


--
-- Name: request request_reviewed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.request
    ADD CONSTRAINT request_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.users(user_id);


--
-- Name: request request_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.request
    ADD CONSTRAINT request_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(user_id);


--
-- Name: site site_location_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_location_id_fkey FOREIGN KEY (location_id) REFERENCES public.location(location_id);


--
-- Name: site site_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id);


--
-- Name: users users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organization(organization_id);


--
-- PostgreSQL database dump complete
--


