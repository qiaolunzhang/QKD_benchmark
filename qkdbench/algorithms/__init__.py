"""Bundled algorithms. Importing this package registers them all."""
from . import greedy_sp        # noqa: F401
from . import key_aware_sp     # noqa: F401
from . import fse_greedy       # noqa: F401
from . import local_search     # noqa: F401
from .exact import milp_p1     # noqa: F401
