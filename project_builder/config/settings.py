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
