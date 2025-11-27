"""
multi_task_demo.py

This script demonstrates five non-trivial tasks:

1. Random walk simulation
2. Text frequency analysis
3. CSV summary statistics
4. Maze solving (pathfinding on a grid)
5. Run-Length Encoding (RLE) compression/decompression

Each task is implemented as a separate function and invoked from main().
The script is fully self-contained (no external dependencies beyond the
Python standard library).
"""

import random
import math
import re
import csv
import io
from collections import Counter, deque
from statistics import mean


# ---------------------------------------------------------------------------
# 1. Random Walk Simulation
# ---------------------------------------------------------------------------

def random_walk_1d(num_steps: int) -> int:
    """
    Perform a 1D random walk with steps of +1 or -1.

    Args:
        num_steps: Number of steps to take.

    Returns:
        Final position after num_steps.
    """
    position = 0
    for _ in range(num_steps):
        step = random.choice([-1, 1])
        position += step
    return position


def run_random_walks(num_walks: int = 5, num_steps: int = 10_000):
    """
    Run several 1D random walks and print their final positions.

    Args:
        num_walks: How many independent walks to simulate.
        num_steps: Steps per walk.
    """
    print("=== 1. Random Walk Simulation ===")
    final_positions = []
    for i in range(num_walks):
        final_pos = random_walk_1d(num_steps)
        final_positions.append(final_pos)
        print(f"Walk {i+1}: final position = {final_pos}")
    avg_position = sum(final_positions) / len(final_positions)
    print(f"Average final position over {num_walks} walks: {avg_position:.2f}")
    print()


# ---------------------------------------------------------------------------
# 2. Text Frequency Analysis
# ---------------------------------------------------------------------------

def tokenize(text: str):
    """
    Simple tokenizer: lowercases and splits on non-alphabetic characters.

    Args:
        text: Input text.

    Returns:
        List of word tokens.
    """
    # Replace non-letters with spaces, then split
    text = text.lower()
    text = re.sub(r"[^a-z]+", " ", text)
    tokens = text.split()
    return tokens


def text_frequency_analysis():
    """
    Compute word frequency on a sample text and print top 20 words.
    """
    print("=== 2. Text Frequency Analysis ===")
    sample_text = (
        "In the beginning the Universe was created. "
        "This has made a lot of people very angry and been widely regarded as a bad move. "
        "Many people have tried to prove that this is not so, but in the end the truth "
        "has a way of making itself known."
    )

    tokens = tokenize(sample_text)

    # Very small stopword list for demo purposes
    stopwords = {
        "the", "and", "a", "of", "in", "to", "that", "has", "is", "it", "this", "as"
    }

    filtered_tokens = [t for t in tokens if t not in stopwords]
    counter = Counter(filtered_tokens)
    top_20 = counter.most_common(20)

    print("Top words (excluding simple stopwords):")
    for word, count in top_20:
        print(f"{word:>12} : {count}")
    print()


# ---------------------------------------------------------------------------
# 3. CSV Summary Statistics
# ---------------------------------------------------------------------------

def generate_csv_data(num_rows: int = 1000):
    """
    Generate CSV data with three numeric columns: col_a, col_b, col_c.

    Values:
        col_a ~ Uniform(0, 1)
        col_b ~ Uniform(10, 20)
        col_c ~ Uniform(-5, 5)

    Returns:
        String containing CSV-formatted data (including header).
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["col_a", "col_b", "col_c"])
    for _ in range(num_rows):
        row = [
            random.random(),               # 0 to 1
            10 + 10 * random.random(),     # 10 to 20
            -5 + 10 * random.random(),     # -5 to 5
        ]
        writer.writerow(row)
    return output.getvalue()


def compute_csv_statistics(csv_text: str):
    """
    Compute mean, min, and max for each numeric column in a CSV string.

    Args:
        csv_text: CSV string with header and numeric values.

    Returns:
        Dict mapping column name -> dict(mean, min, max).
    """
    input_io = io.StringIO(csv_text)
    reader = csv.DictReader(input_io)

    # Collect values per column
    columns = {}
    for row in reader:
        for field, value in row.items():
            columns.setdefault(field, []).append(float(value))

    stats = {}
    for field, values in columns.items():
        stats[field] = {
            "mean": mean(values),
            "min": min(values),
            "max": max(values),
        }
    return stats


def csv_summary_statistics():
    """
    Generate random CSV data, compute summary statistics, and print them.
    """
    print("=== 3. CSV Summary Statistics ===")
    csv_text = generate_csv_data(num_rows=1000)
    stats = compute_csv_statistics(csv_text)
    for col, s in stats.items():
        print(
            f"{col}: mean={s['mean']:.4f}, "
            f"min={s['min']:.4f}, max={s['max']:.4f}"
        )
    print()


# ---------------------------------------------------------------------------
# 4. Maze Solver (BFS on a grid)
# ---------------------------------------------------------------------------

def find_in_grid(grid, target):
    """
    Find the first occurrence of a target character in a 2D grid.

    Args:
        grid: List of strings representing maze rows.
        target: Character to find.

    Returns:
        (row, col) if found, else None.
    """
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == target:
                return r, c
    return None


def neighbors(r, c, rows, cols):
    """
    Generate valid 4-connected neighbors for cell (r, c).
    """
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield nr, nc


def solve_maze(grid):
    """
    Solve a maze using BFS.

    Maze representation:
        - '#' = wall
        - '.' = open path
        - 'S' = start
        - 'E' = exit

    Args:
        grid: List of strings.

    Returns:
        (path, solved_grid):
            path is a list of (r, c) coordinates from S to E (inclusive),
            solved_grid is a list of strings with the path marked by '*'.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0

    start = find_in_grid(grid, 'S')
    end = find_in_grid(grid, 'E')

    if not start or not end:
        return [], grid

    sr, sc = start
    er, ec = end

    # BFS
    queue = deque()
    queue.append(start)
    came_from = {start: None}

    while queue:
        r, c = queue.popleft()
        if (r, c) == (er, ec):
            break  # Reached the exit

        for nr, nc in neighbors(r, c, rows, cols):
            if (nr, nc) in came_from:
                continue  # Already visited
            if grid[nr][nc] == '#':
                continue  # Wall
            came_from[(nr, nc)] = (r, c)
            queue.append((nr, nc))

    # Reconstruct path if we reached the end
    if (er, ec) not in came_from:
        # No path found
        return [], grid

    path = []
    current = (er, ec)
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()

    # Build a new grid with the path highlighted using '*'
    grid_chars = [list(row) for row in grid]
    for (r, c) in path:
        if grid_chars[r][c] not in ('S', 'E'):
            grid_chars[r][c] = '*'
    solved_grid = ["".join(row) for row in grid_chars]

    return path, solved_grid


def maze_solver_demo():
    """
    Define a small maze, solve it, and print the solution.
    """
    print("=== 4. Maze Solver ===")

    # A small demonstration maze
    # S = start, E = exit, # = wall, . = open
    maze = [
        "##########",
        "#S.......#",
        "#.######.#",
        "#.#....#.#",
        "#.#.##.#.#",
        "#...##...#",
        "###.##.###",
        "#....#..E#",
        "##########",
    ]

    path, solved_grid = solve_maze(maze)
    if not path:
        print("No path found from S to E.")
    else:
        print(f"Path length from S to E: {len(path)}")
        print("Solved maze:")
        for row in solved_grid:
            print(row)
    print()


# ---------------------------------------------------------------------------
# 5. Run-Length Encoding (RLE)
# ---------------------------------------------------------------------------

def rle_encode(s: str) -> str:
    """
    Simple run-length encoding.

    Example:
        "aaabbc" -> "a3b2c1"

    Args:
        s: Input string.

    Returns:
        RLE-encoded string.
    """
    if not s:
        return ""

    encoded_parts = []
    current_char = s[0]
    count = 1

    for ch in s[1:]:
        if ch == current_char:
            count += 1
        else:
            encoded_parts.append(f"{current_char}{count}")
            current_char = ch
            count = 1

    # Append the final run
    encoded_parts.append(f"{current_char}{count}")
    return "".join(encoded_parts)


def rle_decode(encoded: str) -> str:
    """
    Decode a run-length encoded string of the form "a3b2c1".

    Args:
        encoded: RLE-encoded string.

    Returns:
        Decoded string.
    """
    if not encoded:
        return ""

    decoded_chars = []
    i = 0
    while i < len(encoded):
        ch = encoded[i]
        i += 1
        # Collect digits (count) following the character
        count_str = []
        while i < len(encoded) and encoded[i].isdigit():
            count_str.append(encoded[i])
            i += 1
        count = int("".join(count_str)) if count_str else 1
        decoded_chars.append(ch * count)

    return "".join(decoded_chars)


def rle_demo():
    """
    Demonstrate RLE encoding and decoding on a sample string.
    """
    print("=== 5. Run-Length Encoding Demo ===")
    original = "aaabbbccccccdddaa"
    encoded = rle_encode(original)
    decoded = rle_decode(encoded)

    print(f"Original: {original}")
    print(f"Encoded : {encoded}")
    print(f"Decoded : {decoded}")
    print(f"Round-trip success: {decoded == original}")
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    # Seed RNG for reproducibility in demos (optional)
    random.seed(42)

    run_random_walks()
    text_frequency_analysis()
    csv_summary_statistics()
    maze_solver_demo()
    rle_demo()


if __name__ == "__main__":
    main()
