# startgg-mcp

A read-only MCP server for competitive fighting game results, using the tournament
data the start.gg scraper stores in Postgres / Aurora.

## Tools

| Tool | Answers |
| --- | --- |
| `list_games` | Which games have data, how much, and when it was last updated |
| `search_players` | Players whose tag contains some text, with profile links and activity |
| `get_player_profile` | A player's set and game record, best placements and recent results |
| `get_player_characters` | Characters a player uses, with win rates |
| `get_head_to_head` | Two players' record against each other |
| `get_character_matchups` | Character vs character win rates in a game |
| `search_tournaments` | Tournaments by name, game and date, with their events |
| `get_event_results` | An event's standings and biggest upsets |

Gamertags are not unique. When a tag matches several players, the player tools
return the candidates (games, activity, profile link) instead of guessing, and the
model is told to ask the user which one they mean.

## Setup

```bash
uv sync
```

Settings come from environment variables (see `src/startgg_mcp/config.py`):

| Variable | Used for |
| --- | --- |
| `DB_DRIVER` | `pg` (local Postgres) or `data-api` (Aurora) |
| `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` | `pg` driver |
| `DB_CLUSTER_ARN`, `DB_SECRET_ARN`, `DB_NAME` | `data-api` driver, plus AWS credentials (`aws sso login`) |

## Running locally

```bash
# MCP Inspector
npx @modelcontextprotocol/inspector uv run --env-file .env startgg-mcp
```

To add it to Claude Code, pass the arguments as JSON so paths with spaces stay intact.
`--env-file` splits its value on spaces, so give it a path relative to `--directory`:

```bash
claude mcp add-json startgg --scope user '{
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "/path/to/startgg-mcp", "--env-file", ".env.aurora", "startgg-mcp"]
}'
```

## Tests

The tests create a database named `startgg_mcp_test` on the Postgres the `PG*`
variables point to, load `tests/schema.sql` and `tests/seed.sql`, and check each
tool against known answers.

```bash
podman run -d --name startgg-mcp-db -e POSTGRES_PASSWORD=postgres -p 5433:5432 docker.io/library/postgres:16
uv run --env-file .env pytest
```

## Read-only database user (Aurora)

The server connects as `mcp_reader`, a user that can only read the tables it needs.
Create it once as the master user (for example in the RDS query editor), with a
generated password:

```sql
CREATE ROLE mcp_reader LOGIN PASSWORD '<generated password>';
ALTER ROLE mcp_reader SET statement_timeout = '10s';
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON
    startgg_videogames,
    startgg_tournaments,
    startgg_events,
    startgg_players,
    startgg_entrants,
    startgg_entrant_players,
    startgg_sets,
    startgg_set_games,
    startgg_set_game_selections
TO mcp_reader;
```

Then store its credentials in a Secrets Manager secret
(`{"username": "mcp_reader", "password": "..."}`) and use that secret's ARN as
`DB_SECRET_ARN`.
