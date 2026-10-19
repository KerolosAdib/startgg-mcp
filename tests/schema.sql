-- Tables the MCP server reads, as created by the scraper's migrations (000-004).

CREATE TABLE public.startgg_entrant_players (
    entrantid integer NOT NULL,
    playerid integer NOT NULL
);
CREATE TABLE public.startgg_entrants (
    entrantid integer NOT NULL,
    eventid integer,
    seed_placement integer,
    final_placement integer,
    is_disqualified boolean DEFAULT false
);
CREATE TABLE public.startgg_events (
    eventid integer NOT NULL,
    tournamentid integer,
    eventname character varying(255),
    slug character varying(255) NOT NULL,
    videogameid bigint NOT NULL,
    numentrants integer,
    startdate timestamp without time zone,
    latestupdate timestamp without time zone,
    synced_at timestamp with time zone
);
CREATE TABLE public.startgg_players (
    playerid integer NOT NULL,
    gamertag character varying(255) NOT NULL,
    slug character varying(255),
    profilepicture character varying(500)
);
CREATE TABLE public.startgg_set_game_selections (
    id integer NOT NULL,
    set_game_id integer NOT NULL,
    entrantid integer NOT NULL,
    character_name character varying(255) NOT NULL
);
CREATE SEQUENCE public.startgg_set_game_selections_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.startgg_set_game_selections_id_seq OWNED BY public.startgg_set_game_selections.id;
CREATE TABLE public.startgg_set_games (
    id integer NOT NULL,
    setid integer NOT NULL,
    game_number integer NOT NULL,
    winnerid integer
);
CREATE SEQUENCE public.startgg_set_games_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
ALTER SEQUENCE public.startgg_set_games_id_seq OWNED BY public.startgg_set_games.id;
CREATE TABLE public.startgg_sets (
    setid integer NOT NULL,
    eventid integer,
    playeronewins integer,
    playertwowins integer,
    hasdq boolean,
    latestupdate timestamp without time zone,
    completedat timestamp without time zone,
    entrantoneid integer,
    entranttwoid integer,
    winnerid integer
);
CREATE TABLE public.startgg_tournaments (
    tournamentid integer NOT NULL,
    tournamentname character varying(255),
    slug character varying(255) NOT NULL,
    startdate timestamp without time zone,
    createdat timestamp without time zone,
    latestupdate timestamp without time zone
);
CREATE TABLE public.startgg_videogames (
    id bigint NOT NULL,
    name character varying(255) NOT NULL
);
ALTER TABLE ONLY public.startgg_set_game_selections ALTER COLUMN id SET DEFAULT nextval('public.startgg_set_game_selections_id_seq'::regclass);
ALTER TABLE ONLY public.startgg_set_games ALTER COLUMN id SET DEFAULT nextval('public.startgg_set_games_id_seq'::regclass);
ALTER TABLE ONLY public.startgg_entrant_players
    ADD CONSTRAINT startgg_entrant_players_pkey PRIMARY KEY (entrantid, playerid);
ALTER TABLE ONLY public.startgg_entrants
    ADD CONSTRAINT startgg_entrants_pkey PRIMARY KEY (entrantid);
ALTER TABLE ONLY public.startgg_events
    ADD CONSTRAINT startgg_events_pkey PRIMARY KEY (eventid);
ALTER TABLE ONLY public.startgg_players
    ADD CONSTRAINT startgg_players_pkey PRIMARY KEY (playerid);
ALTER TABLE ONLY public.startgg_set_game_selections
    ADD CONSTRAINT startgg_set_game_selections_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.startgg_set_games
    ADD CONSTRAINT startgg_set_games_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.startgg_set_games
    ADD CONSTRAINT startgg_set_games_setid_game_number_key UNIQUE (setid, game_number);
ALTER TABLE ONLY public.startgg_sets
    ADD CONSTRAINT startgg_sets_pkey PRIMARY KEY (setid);
ALTER TABLE ONLY public.startgg_tournaments
    ADD CONSTRAINT startgg_tournaments_pkey PRIMARY KEY (tournamentid);
ALTER TABLE ONLY public.startgg_videogames
    ADD CONSTRAINT startgg_videogames_pkey PRIMARY KEY (id);
CREATE INDEX idx_entrant_players_playerid ON public.startgg_entrant_players USING btree (playerid);
CREATE INDEX idx_entrants_eventid ON public.startgg_entrants USING btree (eventid);
CREATE INDEX idx_events_latestupdate ON public.startgg_events USING btree (latestupdate);
CREATE INDEX idx_events_synced_at ON public.startgg_events USING btree (synced_at);
CREATE INDEX idx_events_tournamentid ON public.startgg_events USING btree (tournamentid);
CREATE INDEX idx_events_videogameid ON public.startgg_events USING btree (videogameid);
CREATE INDEX idx_set_game_selections_entrantid ON public.startgg_set_game_selections USING btree (entrantid);
CREATE INDEX idx_set_game_selections_set_game_id ON public.startgg_set_game_selections USING btree (set_game_id);
CREATE INDEX idx_set_games_setid ON public.startgg_set_games USING btree (setid);
CREATE INDEX idx_sets_entrantoneid ON public.startgg_sets USING btree (entrantoneid);
CREATE INDEX idx_sets_entranttwoid ON public.startgg_sets USING btree (entranttwoid);
CREATE INDEX idx_sets_eventid ON public.startgg_sets USING btree (eventid);
CREATE INDEX idx_sets_winnerid ON public.startgg_sets USING btree (winnerid);
CREATE INDEX idx_tournaments_latestupdate ON public.startgg_tournaments USING btree (latestupdate);
ALTER TABLE ONLY public.startgg_entrant_players
    ADD CONSTRAINT startgg_entrant_players_entrantid_fkey FOREIGN KEY (entrantid) REFERENCES public.startgg_entrants(entrantid);
ALTER TABLE ONLY public.startgg_entrant_players
    ADD CONSTRAINT startgg_entrant_players_playerid_fkey FOREIGN KEY (playerid) REFERENCES public.startgg_players(playerid);
ALTER TABLE ONLY public.startgg_entrants
    ADD CONSTRAINT startgg_entrants_eventid_fkey FOREIGN KEY (eventid) REFERENCES public.startgg_events(eventid);
ALTER TABLE ONLY public.startgg_events
    ADD CONSTRAINT startgg_events_tournamentid_fkey FOREIGN KEY (tournamentid) REFERENCES public.startgg_tournaments(tournamentid);
ALTER TABLE ONLY public.startgg_events
    ADD CONSTRAINT startgg_events_videogameid_fkey FOREIGN KEY (videogameid) REFERENCES public.startgg_videogames(id);
ALTER TABLE ONLY public.startgg_set_game_selections
    ADD CONSTRAINT startgg_set_game_selections_entrantid_fkey FOREIGN KEY (entrantid) REFERENCES public.startgg_entrants(entrantid);
ALTER TABLE ONLY public.startgg_set_game_selections
    ADD CONSTRAINT startgg_set_game_selections_set_game_id_fkey FOREIGN KEY (set_game_id) REFERENCES public.startgg_set_games(id) ON DELETE CASCADE;
ALTER TABLE ONLY public.startgg_set_games
    ADD CONSTRAINT startgg_set_games_setid_fkey FOREIGN KEY (setid) REFERENCES public.startgg_sets(setid);
ALTER TABLE ONLY public.startgg_set_games
    ADD CONSTRAINT startgg_set_games_winnerid_fkey FOREIGN KEY (winnerid) REFERENCES public.startgg_entrants(entrantid);
ALTER TABLE ONLY public.startgg_sets
    ADD CONSTRAINT startgg_sets_entrantoneid_fkey FOREIGN KEY (entrantoneid) REFERENCES public.startgg_entrants(entrantid);
ALTER TABLE ONLY public.startgg_sets
    ADD CONSTRAINT startgg_sets_entranttwoid_fkey FOREIGN KEY (entranttwoid) REFERENCES public.startgg_entrants(entrantid);
ALTER TABLE ONLY public.startgg_sets
    ADD CONSTRAINT startgg_sets_eventid_fkey FOREIGN KEY (eventid) REFERENCES public.startgg_events(eventid);
ALTER TABLE ONLY public.startgg_sets
    ADD CONSTRAINT startgg_sets_winnerid_fkey FOREIGN KEY (winnerid) REFERENCES public.startgg_entrants(entrantid);
