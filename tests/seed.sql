-- Small world with known answers for the tool tests.
--
-- Two players share the tag "Kero": 3001 plays SF6 and has a start.gg profile,
-- 3002 plays Skullgirls and has none. "Kerosene" contains "kero" for search tests.
--
-- Expected results (SF6, DQ sets excluded):
--   Kero (3001):          8 sets, 6-2; games 16-8; events 2; best placement 1st of 8
--   Kero vs Blaze:        3-1 in sets, 9-4 in games
--   Kero's characters:    Juri 6 games / 3 wins, Cammy 2 games / 1 win
--   Juri vs Ken:          6 games, Juri wins 3
--   Evo Test 2026 upsets: Kero seeded 4th, placed 1st; Ash seeded 8th, placed 5th

INSERT INTO startgg_videogames (id, name) VALUES
    (43868, 'Street Fighter 6'),
    (32, 'Skullgirls'),
    (49783, 'Tekken 8');

INSERT INTO startgg_tournaments (tournamentid, tournamentname, slug, startdate) VALUES
    (1001, 'Evo Test 2026', 'tournament/evo-test-2026', '2026-08-01'),
    (1002, 'Local Weekly 12', 'tournament/local-weekly-12', '2026-09-20'),
    (1003, 'Skullgirls Showdown', 'tournament/sg-showdown', '2024-03-02');

INSERT INTO startgg_events (eventid, tournamentid, eventname, slug, videogameid, numentrants, startdate, synced_at) VALUES
    (2001, 1001, 'Street Fighter 6', 'tournament/evo-test-2026/event/street-fighter-6', 43868, 8, '2026-08-01', '2026-10-15 03:00+00'),
    (2002, 1002, 'SF6 Singles', 'tournament/local-weekly-12/event/sf6-singles', 43868, 4, '2026-09-20', '2026-10-16 03:00+00'),
    (2003, 1003, 'Skullgirls 2nd Encore', 'tournament/sg-showdown/event/skullgirls', 32, 2, '2024-03-02', '2026-10-12 03:00+00');

INSERT INTO startgg_players (playerid, gamertag, slug) VALUES
    (3001, 'Kero', 'user/a1b2c3d4'),
    (3002, 'Kero', NULL),
    (3003, 'Blaze', 'user/blaze001'),
    (3004, 'Nova', 'user/nova0001'),
    (3005, 'Raiden', 'user/raiden01'),
    (3006, 'Mochi', 'user/mochi001'),
    (3007, 'Vex', 'user/vex00001'),
    (3008, 'Kerosene', 'user/kerosene'),
    (3009, 'Ash', 'user/ash00001');

-- Evo Test 2026 (8 entrants): entrant 40xx
INSERT INTO startgg_entrants (entrantid, eventid, seed_placement, final_placement, is_disqualified) VALUES
    (4001, 2001, 4, 1, FALSE),  -- Kero
    (4002, 2001, 1, 2, FALSE),  -- Blaze
    (4003, 2001, 2, 3, FALSE),  -- Nova
    (4004, 2001, 3, 4, FALSE),  -- Raiden
    (4005, 2001, 5, 5, FALSE),  -- Mochi
    (4006, 2001, 6, 7, FALSE),  -- Vex
    (4007, 2001, 7, 7, FALSE),  -- Kerosene
    (4008, 2001, 8, 5, FALSE),  -- Ash
-- Local Weekly 12 (4 entrants): entrant 41xx
    (4101, 2002, 1, 2, FALSE),  -- Kero
    (4102, 2002, 2, 3, FALSE),  -- Blaze
    (4103, 2002, 3, 1, FALSE),  -- Nova
    (4104, 2002, 4, 3, FALSE),  -- Kerosene
-- Skullgirls Showdown (2 entrants): entrant 42xx
    (4201, 2003, 2, 1, FALSE),  -- Kero (3002)
    (4202, 2003, 1, 2, FALSE);  -- Ash

INSERT INTO startgg_entrant_players (entrantid, playerid) VALUES
    (4001, 3001), (4002, 3003), (4003, 3004), (4004, 3005),
    (4005, 3006), (4006, 3007), (4007, 3008), (4008, 3009),
    (4101, 3001), (4102, 3003), (4103, 3004), (4104, 3008),
    (4201, 3002), (4202, 3009);

INSERT INTO startgg_sets (setid, eventid, entrantoneid, entranttwoid, playeronewins, playertwowins, winnerid, hasdq, completedat) VALUES
    (5001, 2001, 4001, 4006, 2, 0, 4001, FALSE, '2026-08-01 10:00'),  -- Kero beats Vex
    (5002, 2001, 4003, 4001, 1, 2, 4001, FALSE, '2026-08-01 11:00'),  -- Kero beats Nova
    (5003, 2001, 4001, 4002, 1, 2, 4002, FALSE, '2026-08-01 12:00'),  -- Blaze beats Kero
    (5004, 2001, 4005, 4008, 0, 0, 4008, TRUE,  '2026-08-01 12:30'),  -- Mochi DQ, Ash advances
    (5005, 2001, 4002, 4008, 2, 0, 4002, FALSE, '2026-08-01 13:00'),  -- Blaze beats Ash
    (5006, 2001, 4004, 4001, 1, 3, 4001, FALSE, '2026-08-01 14:00'),  -- Kero beats Raiden
    (5007, 2001, 4002, 4001, 2, 3, 4001, FALSE, '2026-08-01 15:00'),  -- Grand final: Kero beats Blaze
    (5008, 2001, 4002, 4001, 0, 3, 4001, FALSE, '2026-08-01 15:30'),  -- Reset: Kero beats Blaze
    (5101, 2002, 4101, 4102, 2, 0, 4101, FALSE, '2026-09-20 19:00'),  -- Kero beats Blaze
    (5102, 2002, 4103, 4101, 2, 0, 4103, FALSE, '2026-09-20 20:00'),  -- Nova beats Kero
    (5201, 2003, 4201, 4202, 2, 1, 4201, FALSE, '2024-03-02 18:00');  -- Kero (3002) beats Ash

-- Character data for two Kero vs Blaze sets and the Skullgirls set
INSERT INTO startgg_set_games (id, setid, game_number, winnerid) VALUES
    (6001, 5003, 1, 4001), (6002, 5003, 2, 4002), (6003, 5003, 3, 4002),
    (6004, 5007, 1, 4001), (6005, 5007, 2, 4002), (6006, 5007, 3, 4001),
    (6007, 5007, 4, 4002), (6008, 5007, 5, 4001),
    (6009, 5201, 1, 4201), (6010, 5201, 2, 4201);

INSERT INTO startgg_set_game_selections (set_game_id, entrantid, character_name) VALUES
    (6001, 4001, 'Juri'),  (6001, 4002, 'Ken'),
    (6002, 4001, 'Juri'),  (6002, 4002, 'Ken'),
    (6003, 4001, 'Juri'),  (6003, 4002, 'Ken'),
    (6004, 4001, 'Juri'),  (6004, 4002, 'Ken'),
    (6005, 4001, 'Juri'),  (6005, 4002, 'Ken'),
    (6006, 4001, 'Juri'),  (6006, 4002, 'Ken'),
    (6007, 4001, 'Cammy'), (6007, 4002, 'Ken'),
    (6008, 4001, 'Cammy'), (6008, 4002, 'Ken'),
    (6009, 4201, 'Filia'), (6009, 4202, 'Valentine'),
    (6010, 4201, 'Filia'), (6010, 4202, 'Valentine');
