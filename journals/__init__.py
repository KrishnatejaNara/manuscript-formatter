"""One settings file per journal. To add a journal, copy one of these files."""
from .jses import JSES
from .kssta import KSSTA

JOURNALS = {"jses": JSES, "kssta": KSSTA}
