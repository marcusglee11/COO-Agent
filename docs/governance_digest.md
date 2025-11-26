# Governance Digest Update Process

## Overview
The `coo-sandbox` image is pinned by its SHA256 digest in `project_builder/config/governance.py` and `project_builder/config/settings.py`. This ensures that only the authorized, canonical image is used in production.

## Update Procedure

1. **Build the Image**
   Build the production sandbox image:
   ```bash
   docker build -t coo-sandbox:prod -f docker/Dockerfile.sandbox docker
   ```

2. **Get the Digest**
   Retrieve the image digest:
   ```bash
   docker inspect coo-sandbox:prod --format='{{.Id}}'
   ```
   Example output: `sha256:f2c125a3328cd4dc8bbe2afee07e7870028e34fed6440f9c3d6ffaea2f8898477`

3. **Update Configuration**
   
   **`project_builder/config/governance.py`**:
   Add the new digest to `ALLOWED_PROD_DIGESTS`:
   ```python
   ALLOWED_PROD_DIGESTS = {
       "sha256:OLD_DIGEST",
       "sha256:NEW_DIGEST",
   }
   ```
   
   **`project_builder/config/settings.py`**:
   Update `SANDBOX_IMAGE_DIGEST`:
   ```python
   SANDBOX_IMAGE_DIGEST = "sha256:NEW_DIGEST"
   ```

4. **Verify**
   Run the governance tests:
   ```bash
   pytest tests/test_enforce_governance.py
   ```

## CI Guardrails
The system is designed to fail if:
- The configured digest is the placeholder digest (in PROD).
- The configured digest is not in `ALLOWED_PROD_DIGESTS`.
- The platform is Windows (in PROD).
