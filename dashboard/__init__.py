import sys as _sys, pathlib as _pl
# Make project root discoverable when a page script is run directly by Streamlit.
_root = _pl.Path(__file__).resolve().parent.parent
if str(_root) not in _sys.path:
    _sys.path.insert(0, str(_root)) 