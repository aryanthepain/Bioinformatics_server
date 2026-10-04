"""Core orchestration engine managing clients, caching, and stateful sessions."""

from __future__ import annotations

import hashlib
import time
from typing import Optional

from quaternary.cache import get_cache_backend
from quaternary.clients import (
    AlphaFoldClient,
    ComplexPortalClient,
    IntActClient,
    MultimerPredictorClient,
    PisaClient,
    RCSBSearchClient,
    SwissModelClient,
    UniProtClient,
)
from quaternary.config import QuaternaryConfig
from quaternary.models import QuaternaryStructureOutput
from quaternary.session import QuaternarySession


class QuaternaryEngine:
    """Central engine providing unified client pooling, session management, and analysis orchestration."""

    def __init__(self, config: Optional[QuaternaryConfig] = None) -> None:
        self.config = config or QuaternaryConfig()
        self.cache = get_cache_backend(self.config)

        # Initialize shared clients
        self.uniprot_client = UniProtClient(self.config, self.cache)
        self.complex_portal_client = ComplexPortalClient(self.config, self.cache)
        self.rcsb_client = RCSBSearchClient(self.config, self.cache)
        self.pisa_client = PisaClient(self.config, self.cache)
        self.swissmodel_client = SwissModelClient(self.config, self.cache)
        self.intact_client = IntActClient(self.config, self.cache)
        self.alphafold_client = AlphaFoldClient(self.config, self.cache)
        self.multimer_client = MultimerPredictorClient(self.config, self.cache)

    def _generate_session_id(self, target_input: str) -> str:
        """Generate a unique session identifier internally (enforcing D-04)."""
        ts = int(time.time() * 1000)
        h = hashlib.sha256(target_input.encode("utf-8")).hexdigest()[:8]
        return f"quat-session-{ts}-{h}"

    def create_session(self, target_input: str) -> QuaternarySession:
        """Create a new step-wise analysis session configured with engine clients."""
        session_id = self._generate_session_id(target_input)
        return QuaternarySession(
            session_id=session_id,
            target_input=target_input,
            config=self.config,
            uniprot_client=self.uniprot_client,
            complex_portal_client=self.complex_portal_client,
            rcsb_client=self.rcsb_client,
            pisa_client=self.pisa_client,
            swissmodel_client=self.swissmodel_client,
            intact_client=self.intact_client,
            alphafold_client=self.alphafold_client,
            multimer_client=self.multimer_client,
        )

    def analyze(
        self,
        target_input: str,
        enable_multimer: bool = True,
        hypothesis: Optional[str] = None,
    ) -> QuaternaryStructureOutput:
        """Execute full end-to-end analysis across all 6 stages and return final synthesis."""
        session = self.create_session(target_input)
        session.run_stage_1_sequence_and_accession()
        session.run_stage_2_experimental_assemblies()
        session.run_stage_3_thermodynamic_qualification()
        session.run_stage_4_homology_and_partners()
        session.run_stage_5_predictive_multimer(
            enable_multimer=enable_multimer,
            hypothesis=hypothesis,
        )
        return session.run_stage_6_synthesis()

    def clear_cache(self) -> None:
        """Purge all cached responses across the configured caching backend."""
        if self.cache is not None:
            self.cache.clear()
