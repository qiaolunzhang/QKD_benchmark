"""Bundled algorithms. Importing this package registers them all."""
from . import greedy_sp        # noqa: F401
from . import key_aware_sp     # noqa: F401
from . import fse_greedy       # noqa: F401
from . import local_search     # noqa: F401
from . import online           # noqa: F401  (OnlineAlgorithm + greedy_admission)
from . import placement        # noqa: F401  (greedy_placement + milp_placement)
from .exact import milp_p1     # noqa: F401
