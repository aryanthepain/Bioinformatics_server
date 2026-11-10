"""One lock for importing and loading the machine-learning libraries and models.

The levels run in parallel threads, and the primary (ESM-2), secondary (S4PRED,
ESM-2 SS3) and tertiary (pydssp) levels each import PyTorch or Transformers the
first time they need them. Transformers creates its classes lazily, and two threads
doing that at the same moment can make one of them fail with "cannot import name
'AutoModelForTokenClassification' from 'transformers'". Holding this lock while
importing and loading makes them take turns; after the first analysis everything is
loaded and the lock is only held for an instant.
"""

import threading

ML_LOCK = threading.RLock()
