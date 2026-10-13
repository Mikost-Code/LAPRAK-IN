import json
import os
import sys
from pathlib import Path

from laprak.desktop import main

if __name__ == "__main__":
    if "--verify-bundle" in sys.argv:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from laprak.react_verify import verify
        verify(Path.cwd() / ".local/bundle-qa")
    else:
        main()
