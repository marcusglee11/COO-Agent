import re
import os
import logging
from typing import List, Dict, Tuple
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError

class AmendmentEngine:
    """
    Mechanically applies amendments from `amendment_protocol_v1.0.md`.
    Enforces strict determinism: numeric order, exact anchor matching.
    Halts on any ambiguity or missing anchor.
    """

    def __init__(self, fsm: RuntimeFSM):
        self.fsm = fsm
        self.logger = logging.getLogger("AmendmentEngine")

    def apply_amendments(self, protocol_path: str, target_root: str) -> None:
        """
        Main entrypoint to apply amendments.
        1. Validates FSM state (AMENDMENT_EXEC).
        2. Parses the protocol file.
        3. Applies each amendment in order.
        """
        self.fsm.assert_state(RuntimeState.AMENDMENT_EXEC)
        self.logger.info(f"Starting Amendment Execution from {protocol_path}")

        if not os.path.exists(protocol_path):
            # If no protocol file, we assume no amendments (or it's an error depending on context)
            # Spec says "CEO provides amendment instructions". If missing, maybe just log and return?
            # "Reject missing anchors or ambiguous anchors" implies if we try to apply.
            # If the file is missing, is it a halt?
            # "4.1 Pre-conditions: amendment_protocol_v1.0.md available and CEO-signed"
            # So it MUST be available.
            raise GovernanceError(f"Missing Amendment Protocol: {protocol_path}")

        amendments = self._parse_protocol(protocol_path)
        
        for idx, (file_path, search_anchor, replacement_text) in enumerate(amendments, 1):
            self.logger.info(f"Applying Amendment #{idx} to {file_path}")
            self._apply_single_amendment(target_root, file_path, search_anchor, replacement_text)

        self.logger.info("All amendments applied successfully.")

    def _parse_protocol(self, protocol_path: str) -> List[Tuple[str, str, str]]:
        """
        Parses the markdown protocol file.
        Expected format (conceptual):
        # Amendment 1
        Target: path/to/file
        <<SEARCH
        exact content
        SEARCH
        <<REPLACE
        new content
        REPLACE
        
        Returns a list of (file_path, search_anchor, replacement_text).
        """
        # TODO: Implement the actual parsing logic based on the exact markdown format spec.
        # For now, returning an empty list or raising NotImplementedError if called.
        # This is a placeholder for the parsing logic.
        return []

    def _apply_single_amendment(self, root: str, rel_path: str, anchor: str, replacement: str) -> None:
        """
        Applies a single replacement.
        Strictly checks for:
        - File existence
        - Anchor existence (exactly once)
        """
        full_path = os.path.join(root, rel_path)
        
        if not os.path.exists(full_path):
            raise GovernanceError(f"Amendment Target Missing: {rel_path}")

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Strict Anchor Check
        count = content.count(anchor)
        if count == 0:
            raise GovernanceError(f"Amendment Anchor Not Found in {rel_path}. Anchor:\n{anchor}")
        if count > 1:
            raise GovernanceError(f"Amendment Anchor Ambiguous ({count} matches) in {rel_path}. Anchor:\n{anchor}")

        # Apply Replacement
        new_content = content.replace(anchor, replacement)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
