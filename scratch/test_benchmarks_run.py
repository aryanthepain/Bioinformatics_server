import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from quaternary.config import QuaternaryConfig
from quaternary_pipeline import analyze_quaternary

cfg = QuaternaryConfig(offline_mode=False, timeout=20.0, cache_enabled=True)

targets = {
    'ubiquitin_seq': 'MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG',
    'ubiquitin_p62988': 'P62988',
    'hemoglobin_alpha': 'P69905',
    'bacteriorhodopsin': 'P02945',
    'p53': 'P04637',
    'akt1': 'P31749',
}

for name, target in targets.items():
    try:
        out = analyze_quaternary(target, config=cfg)
        formula = getattr(out.stoichiometry, "formula", None)
        subunits = out.stoichiometry.total_subunits
        ifaces = len(out.interfaces)
        print(f"{name}: status={out.quaternary_status}, formula={formula}, subunits={subunits}, interfaces={ifaces}")
    except Exception as e:
        print(f"{name}: ERROR: {e}")
