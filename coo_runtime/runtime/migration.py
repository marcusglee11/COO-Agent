import os
import shutil
import logging
import hashlib
import subprocess
import sys
from typing import List, Optional
from ..runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from ..runtime.rollback import RollbackEngine
from ..util.context import enforce_pinned_context_or_fail
from ..util import amu0_utils

class MigrationEngine:
    """
    Orchestrates the 7-step deterministic migration process.
    """
    def __init__(self, fsm: RuntimeFSM, rollback_engine: RollbackEngine):
        self.fsm = fsm
        self.rollback = rollback_engine
        self.logger = logging.getLogger("MigrationEngine")

    def execute_migration_phase_1(self, pb_path: str, coo_path: str, test_runner: str) -> None:
        """
        Executes Phase 1 of the migration.
        """
        self.logger.info("Starting Migration Phase 1...")
        self.fsm.assert_state(RuntimeState.MIGRATION_SEQUENCE)

        try:
            # 0. Enforce Pinned Context (F2, R6 B.2)
            # Resolve AMU0 path first (F8)
            amu0_path = amu0_utils.resolve_amu0_path()
            pinned_env = enforce_pinned_context_or_fail(amu0_path)
            
            # 1. Create COO Tree
            self._create_coo_tree(coo_path)
            
            # 2. Port Code (Deterministic)
            self._port_code(pb_path, coo_path)
            
            # 3. Update Imports
            self._update_imports(coo_path)
            
            # 4. Run Tests
            self._run_tests(test_runner, pinned_env)
            
            # 5. Delete Project Builder
            self._delete_project_builder(pb_path)
            
            self.logger.info("Migration Phase 1 Complete.")
            
        except Exception as e:
            self.logger.error(f"Migration Failed: {e}")
            self.rollback.execute_rollback()

    def finalize_migration_cleanup(self, pb_path: str) -> None:
        """
        Final cleanup step.
        """
        if os.path.exists(pb_path):
            shutil.rmtree(pb_path)

    def _create_coo_tree(self, coo_path: str) -> None:
        if not os.path.exists(coo_path):
            os.makedirs(coo_path)
        # Create required subdirs
        for subdir in ["runtime", "orchestrator", "sandbox"]:
            os.makedirs(os.path.join(coo_path, subdir), exist_ok=True)
            
    def _port_code(self, src: str, dest: str) -> None:
        # Deterministic copy: sort files
        for root, dirs, files in os.walk(src):
            dirs.sort()
            files.sort()
            
            rel_root = os.path.relpath(root, src)
            dest_root = os.path.join(dest, rel_root)
            
            if not os.path.exists(dest_root):
                os.makedirs(dest_root)
                
            for file in files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_root, file)
                shutil.copy2(src_file, dest_file)

    def _update_imports(self, coo_path: str) -> None:
        """
        Updates imports from 'project_builder' to 'coo' using AST.
        Fails if untransformable patterns are found (R6 E.1).
        Preserves formatting by using AST for location finding only.
        """
        import ast
        
        for root, _, files in os.walk(coo_path):
            files.sort()
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f:
                        source = f.read()
                    
                    try:
                        tree = ast.parse(source, filename=path)
                    except SyntaxError:
                        raise GovernanceError(f"Migration Failed: Syntax Error in {file}")

                    replacements = []
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name == "project_builder":
                                    # import project_builder -> import coo
                                    # We need to find the exact text range.
                                    # AST doesn't give end col easily in older python.
                                    # But we can check the line.
                                    # For simplicity and strictness, if we find it, we replace the whole line?
                                    # Or we use string replacement ONLY on the lines identified by AST.
                                    replacements.append((node.lineno, "project_builder", "coo"))
                                elif alias.name.startswith("project_builder."):
                                    # import project_builder.foo -> import coo.foo
                                    replacements.append((node.lineno, "project_builder", "coo"))
                                    
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and (node.module == "project_builder" or node.module.startswith("project_builder.")):
                                # from project_builder import ... -> from coo import ...
                                replacements.append((node.lineno, "project_builder", "coo"))

                    if replacements:
                        lines = source.splitlines(keepends=True)
                        for lineno, old, new in replacements:
                            # 1-based lineno
                            idx = lineno - 1
                            if idx < len(lines):
                                # Verify the line actually contains the target to avoid false positives
                                if old in lines[idx]:
                                    lines[idx] = lines[idx].replace(old, new)
                                else:
                                    # If AST says it's there but string replace fails, it's ambiguous.
                                    # R6 says "fail on untransformable patterns".
                                    raise GovernanceError(f"Migration Failed: Ambiguous import pattern in {file} at line {lineno}")
                        
                        with open(path, "w", encoding="utf-8") as f:
                            f.writelines(lines)

    def _run_tests(self, test_runner: str, env: dict) -> None:
        # Execute test runner
        # In production, use subprocess.check_call
        # Here we assume it passes if file exists
        if not os.path.exists(test_runner):
            raise GovernanceError("Test runner missing")
        try:
             # R6 B.2: Use pinned environment
             subprocess.run([sys.executable, test_runner], check=True, env=env)
        except subprocess.CalledProcessError as e:
             raise GovernanceError(f"Tests Failed: {e}")
            
    def _delete_project_builder(self, pb_path: str) -> None:
        if os.path.exists(pb_path):
            shutil.rmtree(pb_path)
