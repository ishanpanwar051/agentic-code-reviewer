"""Root level runner for 'python -m agent' execution."""

import sys
from src.main import main


if __name__ == "__main__":
    sys.exit(main())
