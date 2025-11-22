import os

# Configuration
TARGET_ROOTS = ["project_builder", "tests", "docs", "config"]
INCLUDE_EXTENSIONS = {".py", ".sql", ".yaml", ".md"}
IGNORE_DIRS = {"__pycache__", ".pytest_cache", "venv", ".git", "site-packages", "coo_core"}

def should_include(filename):
    return any(filename.endswith(ext) for ext in INCLUDE_EXTENSIONS)

def generate_review_packet():
    output = []
    output.append("<<< START_REVIEW_PACKET >>>")
    output.append("*** COUNCIL REVIEW REQUEST ***")
    output.append("\n## 1. Directory Structure")
    
    # Walk the entire tree for structure
    for root, dirs, filenames in os.walk(".", topdown=True):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(".", "").count(os.sep)
        indent = " " * 4 * level
        output.append(f"{indent}{os.path.basename(root)}/")
        subindent = " " * 4 * (level + 1)
        for f in filenames:
            output.append(f"{subindent}{f}")
    
    output.append("\n## 2. File Contents")
    
    # Walk specific roots for content
    for target_root in TARGET_ROOTS:
        if not os.path.exists(target_root):
            continue
            
        for root, dirs, filenames in os.walk(target_root, topdown=True):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            
            for filename in filenames:
                if should_include(filename):
                    filepath = os.path.join(root, filename)
                    output.append(f"\n--- START FILE: {filepath} ---")
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            output.append(f.read())
                    except Exception as e:
                        output.append(f"!! ERROR READING FILE: {str(e)} !!")
                    output.append(f"--- END FILE: {filepath} ---\n")

    output.append("<<< END_REVIEW_PACKET >>>")
    print("\n".join(output))

if __name__ == "__main__":
    generate_review_packet()
