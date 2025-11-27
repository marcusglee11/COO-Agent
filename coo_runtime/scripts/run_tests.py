import sys
import os
import unittest
import logging

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("RunTests")
    
    test_dir = os.path.abspath("coo_runtime/tests")
    logger.info(f"Running tests in {test_dir}")

    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    main()
