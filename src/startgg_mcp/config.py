import os

# Environment
DB_DRIVER = os.environ.get("DB_DRIVER", "pg")
DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN")
DB_NAME = os.environ.get("DB_NAME", "postgres")

# Results
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_CANDIDATES = 10
SMALL_SAMPLE_SETS = 10
SMALL_SAMPLE_GAMES = 20
# Best placements and latest results shown in a player profile
TOP_PLACEMENTS = 5
RECENT_RESULTS = 10

# Database
STATEMENT_TIMEOUT_SECONDS = 10
# How long to keep retrying while Aurora wakes up
RESUME_WAIT_SECONDS = 45
# How long list_games reuses its counts
GAMES_CACHE_SECONDS = 600

# Links
STARTGG_BASE_URL = "https://www.start.gg/"