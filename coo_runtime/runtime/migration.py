import os
import shutil
import logging
import hashlib
import subprocess
import sys
from typing import List, Optional
from ..runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from ..runtime.rollback import RollbackEngine
from ..runtime.init import initialize_runtime
from ..util import amu0_utils
from ..util import amu0_utils
from ..util.subprocess import run_pinned_subprocess
from ..util.questions import raise_question, QuestionType

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
            # R6.4 E1: Initialize runtime instead of deprecated enforce_pinned_context_or_fail
            # Resolve AMU0 path first (F8)
            amu0_path = amu0_utils.resolve_amu0_path()
            initialize_runtime(amu0_path)
            
            # 1. Create COO Tree
            self._create_coo_tree(coo_path)
            
            # 2. Port Code (Deterministic)
            self._port_code(pb_path, coo_path)
            
            # 3. Update Imports
            self._update_imports(coo_path)
            
            # 4. Run Tests
            self._run_tests(test_runner)
            
            # 5. Delete Project Builder
            self._delete_project_builder(pb_path)
            
            # 6. Run Tests (Snapshot B) - R6.5 Hygiene Fix
            self._run_tests(test_runner)
            
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
        Updates imports from 'project_builder' to 'coo' using Pure AST transformation (A.6).
        - Parses code into AST.
        - Transforms AST nodes.
        - Unparses AST back to source code (No string replacement).
        - Fails on dynamic imports or forbidden patterns.
        """
        import ast

        class ImportTransformer(ast.NodeTransformer):
            def visit_Import(self, node):
                new_names = []
                for alias in node.names:
                    if alias.name == "project_builder":
                        new_names.append(ast.alias(name="coo", asname=alias.asname))
                    elif alias.name.startswith("project_builder."):
                        new_name = alias.name.replace("project_builder.", "coo.", 1)
                        new_names.append(ast.alias(name=new_name, asname=alias.asname))
                    else:
                        new_names.append(alias)
                node.names = new_names
                return node

            def visit_ImportFrom(self, node):
                if node.module:
                    if node.module == "project_builder":
                        node.module = "coo"
                    elif node.module.startswith("project_builder."):
                        node.module = node.module.replace("project_builder.", "coo.", 1)
                return node
                
            def visit_Call(self, node):
                # Detect dynamic imports/execution (A.6)
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["__import__", "eval", "exec"]:
                        raise_question(QuestionType.MIGRATION_FAILURE, f"Migration Failed: Forbidden dynamic execution '{node.func.id}' detected.")
                return node

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
                        raise_question(QuestionType.MIGRATION_FAILURE, f"Migration Failed: Syntax Error in {file}")

                    # 1. Check for forbidden patterns (importlib)
                    # We do this by walking before transform or during.
                    # Let's do a quick check for importlib usage which might be an attribute access
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name == "importlib" or alias.name.startswith("importlib."):
                                     raise_question(QuestionType.MIGRATION_FAILURE, f"Migration Failed: Forbidden 'importlib' usage in {file}")
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and (node.module == "importlib" or node.module.startswith("importlib.")):
                                 raise_question(QuestionType.MIGRATION_FAILURE, f"Migration Failed: Forbidden 'importlib' usage in {file}")

                    # 2. Transform
                    transformer = ImportTransformer()
                    try:
                        new_tree = transformer.visit(tree)
                        ast.fix_missing_locations(new_tree)
                    except GovernanceError as e:
                        raise_question(QuestionType.MIGRATION_FAILURE, f"Migration Failed in {file}: {e}")

                    # 3. Unparse (Pure AST)
                    # Requires Python 3.9+
                    if sys.version_info < (3, 9):
                        raise_question(QuestionType.MIGRATION_FAILURE, "COO Runtime requires Python 3.9+ for AST unparsing.")
                        
                    new_source = ast.unparse(new_tree)
                    
                    # Write back
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_source)

    def _run_tests(self, test_runner: str) -> None:
        # Execute test runner
        # In production, use subprocess.check_call
        # Here we assume it passes if file exists
        if not os.path.exists(test_runner):
            raise_question(QuestionType.MIGRATION_FAILURE, "Test runner missing")
        try:
             # R6.3 B5: Use pinned subprocess
             amu0_path = amu0_utils.resolve_amu0_path()
             run_pinned_subprocess([sys.executable, test_runner], amu0_path, check=True)
        except Exception as e:
             raise_question(QuestionType.MIGRATION_FAILURE, f"Tests Failed: {e}")
            
    def _delete_project_builder(self, pb_path: str) -> None:
        if os.path.exists(pb_path):
            shutil.rmtree(pb_path)
