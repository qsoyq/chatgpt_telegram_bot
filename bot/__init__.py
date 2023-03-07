import pathlib
import sys

__version__ = '0.0.1'

# The current file structure does not follow the import method for package, so it is necessary to add the current directory to sys.path.
sys.path.append(str(pathlib.Path(__file__).parent))
