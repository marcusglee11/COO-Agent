# Project Builder Configuration

# Planning & Budget
PLANNER_BUDGET_FRACTION = 0.8
MAX_TASKS_PER_MISSION = 5
MAX_PLAN_REVISIONS = 3
MAX_REPAIRS_PER_TASK = 1

# Execution
TASK_LOCK_TIMEOUT_SECONDS = 600

# Backpressure
BASE_PENDING_LIMIT = 50
MAX_PENDING_PER_TASK = 10

# Context Injection
MAX_FILE_TREE_TOKENS = 2000
MAX_ARTIFACT_TOKENS = 100000  # Default cap for all artifacts combined
MAX_CONTEXT_TOKENS = 100000  # Default max context budget
TRUNCATION_MARKER = "... [CONTEXT_TRUNCATED] ..."

# Sandbox & Security
SANDBOX_TIMEOUT_SECONDS = 300  # 5 minutes (Canonical enforcement)
SANDBOX_MEMORY_LIMIT = "1g"
SANDBOX_MEMORY_SWAP = "1g"  # Prevent swap usage
SANDBOX_PIDS_LIMIT = 100    # Prevent fork bombs
SANDBOX_USER_UID = "1000:1000"  # Non-root user for Docker
SANDBOX_CPU_LIMIT = "1"
SANDBOX_IMAGE_DIGEST = "sha256:f2c125a3328cd4dc8bbe2afee07e7870028e34fed6440f9c3d6ffaea2f8898477" # Canonical PROD digest
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB limit
MANIFEST_PATH_REGEX = r"^[A-Za-z0-9._ -]+(/[A-Za-z0-9._ -]+)*$"
CHECKSUM_FORMAT_REGEX = r"^sha256:[0-9a-f]{64}$"
