import glob
import re
import sys
from pathlib import Path
from typing import Optional, List

import yaml
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent.parent






if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/create_update_progress_file.py <state>")
        sys.exit(1)
    state = sys.argv[1]
    updated_ocdids = create_update_progress_file(state)
    # Print the updated OCDIDs as a comma-separated string
    print(",".join(updated_ocdids))
