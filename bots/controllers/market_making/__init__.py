# Explicit re-exports for dynamic discovery
from importlib import import_module as _im

# Ensure pmm_netting module is importable when this package is imported.
try:
    _im("bots.controllers.market_making.pmm_netting")
except Exception:  # pragma: no cover
    # Silently ignore if dependencies missing during partial installs
    pass



