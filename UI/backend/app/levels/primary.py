"""Primary structure: DIAMOND, HMMER/Pfam, ESM-2 and ProtParam.

Ported from the team notebook "Mapping_Protein_Function_from_Primary_Structure.ipynb"
(class EndToEndBioinformaticsPipeline). The class keeps its name and its methods
keep their names, thresholds, scoring and report texts:

  _run_diamond              best Swiss-Prot hit (DIAMOND blastp, top target)
  _run_hmmer                best Pfam domain by independent E-value (hmmscan)
  _extract_esm2_embedding   mean-pooled ESM-2 (esm2_t6_8M_UR50D) embedding
  _run_protparam_analysis   six ProtParam properties
  _calculate_consensus      evidence score out of 90 (DIAMOND 50 + HMMER 40)
  interpretation()          the three INTERPRETATION sentences of print_report

ONE CORRECTION (please tell the notebook's author): _run_diamond read the query
start, end and length from the wrong DIAMOND columns (6, 7 and 10 instead of
5, 6 and 9), so "query coverage" was really (qend - sstart + 1) / subject
length. The notebook's own p53 run shows it: a 392-residue query aligned end
to end was reported at 99.75% coverage (= 392/393). This port reads the
intended columns. Full-length self-matches give the same result either way.

Plumbing changes only:
  * results are returned instead of printed;
  * the four analyses still run at the same time, but in threads, so a
    running DIAMOND or hmmscan can be stopped when the user presses Cancel;
  * the ESM-2 model is loaded once and then reused;
  * tool and database locations come from configuration (setup_primary.sh).

Additions used only for display (they never change the score):
  * DIAMOND also writes the subject title (protein name, organism, gene);
  * every Pfam domain passing the notebook's threshold is listed with its
    position along the sequence.
"""

import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..config import DIAMOND_BIN, HMMSCAN_BIN, PRIMARY_DATA_DIR, PRIMARY_TOOL_TIMEOUT_SECONDS
from ..jobs import AnalysisCancelled, LevelSkipped, StageContext
from ..schemas import (
    EvidenceItem,
    Headline,
    LevelResult,
    Link,
    Metric,
    Note,
    Segment,
    Table,
    TableColumn,
    Track,
)

logger = logging.getLogger(__name__)

# Change this whenever the logic below changes, so cached results are not reused.
CACHE_VERSION = "primary-2"

ESM_MODEL_NAME = "facebook/esm2_t6_8M_UR50D"
DIAMOND_DB = PRIMARY_DATA_DIR / "swissprot.dmnd"
PFAM_HMM = PRIMARY_DATA_DIR / "Pfam-A.hmm"
PFAM_PRESSED = [Path(f"{PFAM_HMM}{suffix}") for suffix in (".h3m", ".h3i", ".h3f", ".h3p")]


# --- Setup checks and helpers ------------------------------------------------------


def missing_setup() -> list[str]:
    """What still needs installing before the module can run (empty = ready)."""
    missing: list[str] = []
    if shutil.which(DIAMOND_BIN) is None:
        missing.append("DIAMOND (brew install diamond)")
    if shutil.which(HMMSCAN_BIN) is None:
        missing.append("HMMER (brew install hmmer)")
    if not DIAMOND_DB.is_file():
        missing.append("the Swiss-Prot database")
    if not PFAM_HMM.is_file() or not all(path.is_file() for path in PFAM_PRESSED):
        missing.append("the pressed Pfam-A database")
    return missing


def _ml_libraries() -> tuple[Any, Any, Any]:
    try:
        import torch
        from transformers import AutoTokenizer, EsmModel
    except ImportError as error:
        raise RuntimeError(
            "PyTorch and Transformers are not installed. Run `uv sync` in UI/backend, then restart the backend."
        ) from error
    return torch, AutoTokenizer, EsmModel


def _protein_analysis() -> Any:
    try:
        from Bio.SeqUtils.ProtParam import ProteinAnalysis
    except ImportError as error:
        raise RuntimeError("Biopython is not installed. Run `uv sync` in UI/backend.") from error
    return ProteinAnalysis


def _run_command(cmd: list[str], ctx: StageContext, timeout: float) -> tuple[int, str]:
    """Run a command; stop it if the user cancels or it takes too long.

    Returns (exit code, standard error). FileNotFoundError is raised, as with
    asyncio.create_subprocess_exec in the notebook, if the program is missing.
    """
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.monotonic() + timeout
    while True:
        try:
            _, stderr = process.communicate(timeout=0.5)
            return process.returncode, stderr.decode(errors="replace").strip()
        except subprocess.TimeoutExpired:
            if ctx.cancelled or time.monotonic() > deadline:
                process.kill()
                process.communicate()
                if ctx.cancelled:
                    raise AnalysisCancelled() from None
                raise RuntimeError(
                    f"{Path(cmd[0]).name} did not finish within {timeout / 60:.0f} minutes."
                ) from None


# --- The notebook's pipeline ------------------------------------------------------------


class EndToEndBioinformaticsPipeline:
    def __init__(self) -> None:
        self.DIAMOND_IDENTITY_THRESHOLD = 30.0
        self.DIAMOND_QUERY_COVERAGE_THRESHOLD = 80.0
        self.HMMER_EVAL_THRESHOLD = 1e-10
        model_name = ESM_MODEL_NAME

        torch, AutoTokenizer, EsmModel = _ml_libraries()
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = EsmModel.from_pretrained(model_name)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        self.model.eval()

    def _run_diamond(self, fasta_path: str, ctx: StageContext) -> dict[str, Any]:
        out_path = f"{fasta_path}.tsv"

        try:
            cmd = [
                DIAMOND_BIN,
                "blastp",
                "-d", str(DIAMOND_DB),
                "-q", fasta_path,
                "-o", out_path,
                "--outfmt", "6",
                "qseqid", "sseqid", "pident", "evalue",
                "bitscore", "qstart", "qend", "sstart", "send",
                "qlen", "slen",
                "stitle",  # display only: protein name, organism and gene
                "--max-target-seqs", "1",
                "--quiet",
            ]

            returncode, stderr = _run_command(cmd, ctx, PRIMARY_TOOL_TIMEOUT_SECONDS)

            if returncode != 0:
                return {
                    "source": "DIAMOND",
                    "identity": 0.0,
                    "best_hit": "None",
                    "e_value": 1.0,
                    "query_coverage": 0.0,
                    "error": stderr,
                }

            if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                return {
                    "source": "DIAMOND",
                    "identity": 0.0,
                    "best_hit": "None",
                    "e_value": 1.0,
                    "query_coverage": 0.0,
                }

            with open(out_path, "r") as f:
                parts = f.readline().strip().split("\t")

            if len(parts) < 11:
                return {
                    "source": "DIAMOND",
                    "identity": 0.0,
                    "best_hit": "None",
                    "e_value": 1.0,
                    "query_coverage": 0.0,
                    "error": "Unexpected DIAMOND output format",
                }

            identity = float(parts[2])
            e_value = float(parts[3])

            # Corrected column indices (the notebook used 6, 7 and 10).
            qstart = int(parts[5])
            qend = int(parts[6])
            qlen = int(parts[9])

            query_coverage = (
                100.0 * (abs(qend - qstart) + 1) / qlen
                if qlen > 0 else 0.0
            )

            return {
                "source": "DIAMOND",
                "best_hit": parts[1],
                "identity": identity,
                "e_value": e_value,
                "query_coverage": query_coverage,
                # Display-only details from the same output line:
                "bitscore": float(parts[4]),
                "qstart": qstart,
                "qend": qend,
                "sstart": int(parts[7]),
                "send": int(parts[8]),
                "qlen": qlen,
                "slen": int(parts[10]),
                "title": parts[11] if len(parts) > 11 else "",
            }

        except FileNotFoundError as e:
            return {
                "source": "DIAMOND",
                "identity": 0.0,
                "best_hit": "None",
                "e_value": 1.0,
                "query_coverage": 0.0,
                "error": str(e),
            }

        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def _run_hmmer(self, fasta_path: str, ctx: StageContext) -> dict[str, Any]:
        out_path = f"{fasta_path}.domtblout"

        try:
            cmd = [
                HMMSCAN_BIN,
                "--noali",
                "--domtblout", out_path,
                str(PFAM_HMM),
                fasta_path,
            ]

            returncode, stderr = _run_command(cmd, ctx, PRIMARY_TOOL_TIMEOUT_SECONDS)

            if returncode != 0:
                return {
                    "source": "HMMER",
                    "domain": "None",
                    "accession": "None",
                    "e_value": 1.0,
                    "error": stderr,
                    "domains": [],
                }

            best_hit = None
            domains: list[dict[str, Any]] = []  # display only

            if os.path.exists(out_path):
                with open(out_path, "r") as f:
                    for line in f:
                        if line.startswith("#"):
                            continue

                        parts = line.split()
                        if len(parts) < 22:
                            continue

                        hit = {
                            "source": "HMMER",
                            "domain": parts[0],
                            "accession": parts[1],
                            "e_value": float(parts[12]),
                        }

                        if best_hit is None or hit["e_value"] < best_hit["e_value"]:
                            best_hit = hit

                        domains.append(
                            {
                                "domain": parts[0],
                                "accession": parts[1],
                                "e_value": float(parts[12]),
                                "score": float(parts[13]),
                                "env_from": int(parts[19]),
                                "env_to": int(parts[20]),
                                "description": " ".join(parts[22:]),
                            }
                        )

            if best_hit is not None:
                return {**best_hit, "domains": domains}

            return {
                "source": "HMMER",
                "domain": "None",
                "accession": "None",
                "e_value": 1.0,
                "domains": domains,
            }

        except FileNotFoundError as e:
            return {
                "source": "HMMER",
                "domain": "None",
                "accession": "None",
                "e_value": 1.0,
                "error": str(e),
                "domains": [],
            }

        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def _extract_esm2_embedding(self, sequence: str) -> dict[str, Any]:
        inputs = self.tokenizer(
            sequence,
            return_tensors="pt"
        ).to(self.device)

        with self.torch.no_grad():
            outputs = self.model(**inputs)
        token_embeddings = outputs.last_hidden_state[:, 1:-1, :]

        pooled = token_embeddings.mean(dim=1).squeeze(0)
        embedding = pooled.cpu().numpy()

        return {
            "source": "ESM-2",
            "embedding_dimensions": int(embedding.shape[0]),
            "embedding": embedding,
        }

    def _run_protparam_analysis(self, sequence: str) -> dict[str, float]:
        ProteinAnalysis = _protein_analysis()
        analyzer = ProteinAnalysis(sequence)
        sec_structure = analyzer.secondary_structure_fraction()

        return {
            "Molecular Weight (kDa)": round(
                analyzer.molecular_weight() / 1000, 2
            ),
            "Isoelectric Point (pI)": round(
                analyzer.isoelectric_point(), 2
            ),
            "Instability Index (heuristic)": round(
                analyzer.instability_index(), 2
            ),
            "GRAVY (mean hydropathy)": round(
                analyzer.gravy(), 3
            ),
            "Alpha Helix Propensity Fraction": round(
                sec_structure[0], 3
            ),
            "Beta Sheet Propensity Fraction": round(
                sec_structure[2], 3
            ),
        }

    def _calculate_consensus(
        self,
        diamond_res: dict[str, Any],
        hmmer_res: dict[str, Any],
        esm_res: dict[str, Any],
    ) -> dict[str, Any]:
        score = 0
        summary = []

        identity = diamond_res.get("identity", 0.0)
        coverage = diamond_res.get("query_coverage", 0.0)

        if (
            identity > self.DIAMOND_IDENTITY_THRESHOLD
            and coverage >= self.DIAMOND_QUERY_COVERAGE_THRESHOLD
        ):
            score += 50
            summary.append(
                f"[+] DIAMOND: {identity:.2f}% identity and "
                f"{coverage:.2f}% query coverage to "
                f"{diamond_res.get('best_hit', 'Unknown')}."
            )
        else:
            summary.append(
                f"[-] DIAMOND: identity={identity:.2f}%, "
                f"query coverage={coverage:.2f}%; "
                "the configured thresholds were not both met."
            )

        hmm_evalue = hmmer_res.get("e_value", 1.0)

        if hmm_evalue < self.HMMER_EVAL_THRESHOLD:
            score += 40
            summary.append(
                f"[+] HMMER: detected {hmmer_res.get('domain')} "
                f"(independent domain E-value: {hmm_evalue:.2e})."
            )
        else:
            summary.append(
                "[-] HMMER: no domain passed the configured E-value threshold."
            )

        if esm_res.get("embedding_dimensions") == 320:
            summary.append(
                "[+] ESM-2: successfully extracted a 320-dimensional "
                "sequence embedding."
            )

        return {
            "evidence_score": score,
            "maximum_score": 90,
            "summary": summary,
        }

    def interpretation(self, physio: dict[str, float]) -> list[tuple[str, str]]:
        """The INTERPRETATION part of the notebook's print_report, as (title, text)."""
        lines: list[tuple[str, str]] = []

        instability = physio["Instability Index (heuristic)"]
        if instability > 40:
            lines.append((
                "Stability",
                "Instability index is above 40. This is a sequence-based "
                "heuristic, not a direct measurement of protein stability.",
            ))
        else:
            lines.append((
                "Stability",
                "Instability index is at or below 40. This heuristic alone "
                "does not establish experimental stability.",
            ))

        gravy = physio["GRAVY (mean hydropathy)"]
        if gravy > 0:
            lines.append((
                "Hydropathy",
                "Positive GRAVY indicates a hydrophobic sequence on average. "
                "It does not by itself establish membrane localization.",
            ))
        else:
            lines.append((
                "Hydropathy",
                "Negative GRAVY indicates a hydrophilic sequence on average. "
                "It does not by itself establish cellular localization or solubility.",
            ))

        pI = physio["Isoelectric Point (pI)"]
        if pI < 7.4:
            lines.append((
                "Charge at pH 7.4",
                "At pH 7.4, the protein is expected to have a net negative "
                "charge based on its theoretical pI. Anion-exchange binding "
                "is possible, but must be tested experimentally.",
            ))
        elif pI > 7.4:
            lines.append((
                "Charge at pH 7.4",
                "At pH 7.4, the protein is expected to have a net positive "
                "charge based on its theoretical pI. Cation-exchange binding "
                "is possible, but must be tested experimentally.",
            ))
        else:
            lines.append((
                "Charge at pH 7.4",
                "The theoretical pI is approximately 7.4, so the net charge "
                "may be close to zero at that pH.",
            ))

        return lines

    def execute(self, sequence: str, ctx: StageContext) -> dict[str, Any]:
        """Run the four analyses at the same time and return everything (the
        notebook's commented-out return value, plus the interpretation)."""
        sequence = sequence.strip().upper()

        if not sequence:
            raise ValueError("Protein sequence cannot be empty.")

        valid_amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
        invalid = set(sequence) - valid_amino_acids
        if invalid:
            raise ValueError(
                f"Invalid amino-acid characters found: {sorted(invalid)}"
            )

        with tempfile.TemporaryDirectory(prefix="pfp-primary-") as directory:
            fasta_path = os.path.join(directory, "query.fasta")
            with open(fasta_path, "w") as tmp:
                tmp.write(f">query\n{sequence}\n")

            ctx.report("Running DIAMOND, HMMER, ESM-2 and ProtParam…")
            started = time.monotonic()
            with ThreadPoolExecutor(max_workers=4, thread_name_prefix="primary") as pool:
                futures = {
                    "DIAMOND": pool.submit(self._run_diamond, fasta_path, ctx),
                    "HMMER": pool.submit(self._run_hmmer, fasta_path, ctx),
                    "ESM-2": pool.submit(self._extract_esm2_embedding, sequence),
                    "ProtParam": pool.submit(self._run_protparam_analysis, sequence),
                }
                while not all(future.done() for future in futures.values()):
                    waiting = [name for name, future in futures.items() if not future.done()]
                    elapsed = int(time.monotonic() - started)
                    ctx.report(f"Waiting for {', '.join(waiting)} · {elapsed // 60}:{elapsed % 60:02d} elapsed")
                    time.sleep(0.5)
                diamond_res = futures["DIAMOND"].result()
                hmmer_res = futures["HMMER"].result()
                esm_res = futures["ESM-2"].result()
                physio_res = futures["ProtParam"].result()

        consensus = self._calculate_consensus(diamond_res, hmmer_res, esm_res)

        return {
            "diamond": diamond_res,
            "hmmer": hmmer_res,
            "esm": esm_res,
            "physicochemical": physio_res,
            "consensus": consensus,
            "interpretation": self.interpretation(physio_res),
        }


# One pipeline (and one loaded ESM-2 model) for the whole server.
_pipeline: EndToEndBioinformaticsPipeline | None = None
_pipeline_lock = threading.Lock()


def get_pipeline(ctx: StageContext) -> EndToEndBioinformaticsPipeline:
    global _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            ctx.report("Loading the ESM-2 model (first analysis only)…")
            _pipeline = EndToEndBioinformaticsPipeline()
        return _pipeline


# --- Translating the results for the interface -----------------------------------------


def _hit_details(diamond: dict[str, Any]) -> dict[str, str]:
    """Split 'sp|P31749|AKT1_HUMAN' and its title into readable parts."""
    best_hit = str(diamond.get("best_hit", "None"))
    accession, entry = best_hit, best_hit
    pieces = best_hit.split("|")
    if len(pieces) >= 3:
        accession, entry = pieces[1], pieces[2]

    title = str(diamond.get("title", ""))
    if title.startswith(best_hit):
        title = title[len(best_hit):].strip()
    protein = title.split(" OS=", 1)[0].strip()
    organism_match = re.search(r"OS=(.+?)(?= OX=| GN=| PE=| SV=|$)", title)
    gene_match = re.search(r" GN=(\S+)", title)
    return {
        "accession": accession,
        "entry": entry,
        "protein": protein,
        "organism": organism_match.group(1).strip() if organism_match else "",
        "gene": gene_match.group(1) if gene_match else "",
    }


def _significant_domains(hmmer: dict[str, Any], threshold: float, length: int) -> list[dict[str, Any]]:
    """Domains below the notebook's E-value threshold, without overlaps, in sequence order."""
    candidates = sorted(
        (domain for domain in hmmer.get("domains", []) if domain["e_value"] < threshold),
        key=lambda domain: domain["e_value"],
    )
    kept: list[dict[str, Any]] = []
    for domain in candidates:
        start, end = max(1, domain["env_from"]), min(length, domain["env_to"])
        if start > end:
            continue
        if all(end < other["start"] or start > other["end"] for other in kept):
            kept.append({**domain, "start": start, "end": end})
    return sorted(kept, key=lambda domain: domain["start"])


def _to_level_result(sequence: str, results: dict[str, Any], pipeline: EndToEndBioinformaticsPipeline) -> LevelResult:
    length = len(sequence)
    diamond = results["diamond"]
    hmmer = results["hmmer"]
    esm = results["esm"]
    physio = results["physicochemical"]
    consensus = results["consensus"]

    has_hit = diamond.get("best_hit", "None") != "None"
    hit = _hit_details(diamond) if has_hit else None
    identity = float(diamond.get("identity", 0.0))
    coverage = float(diamond.get("query_coverage", 0.0))
    diamond_passed = (
        identity > pipeline.DIAMOND_IDENTITY_THRESHOLD
        and coverage >= pipeline.DIAMOND_QUERY_COVERAGE_THRESHOLD
    )
    hmmer_evalue = float(hmmer.get("e_value", 1.0))
    hmmer_passed = hmmer_evalue < pipeline.HMMER_EVAL_THRESHOLD
    domains = _significant_domains(hmmer, pipeline.HMMER_EVAL_THRESHOLD, length)

    # --- Summary sentence
    if hit is not None and diamond_passed:
        name = hit["protein"] or hit["entry"]
        where = f", {hit['organism']}" if hit["organism"] else ""
        summary = (
            f"Closest Swiss-Prot entry: {name} ({hit['accession']}{where}), "
            f"{identity:.2f}% identity over {coverage:.2f}% of the query."
        )
    elif hit is not None:
        summary = (
            f"No Swiss-Prot hit met both thresholds (best: {hit['entry']}, "
            f"{identity:.2f}% identity, {coverage:.2f}% coverage)."
        )
    else:
        summary = "No Swiss-Prot hit was found."
    if hmmer_passed:
        summary += f" Pfam domain {hmmer.get('domain')} detected (E-value {hmmer_evalue:.2e})."
    else:
        summary += " No Pfam domain passed the E-value threshold."

    # --- Key figures and grouped properties
    metrics = [
        Metric(label="Query coverage", value=f"{coverage:.2f}%" if has_hit else "—"),
        Metric(label="Best Pfam domain", value=str(hmmer.get("domain")) if hmmer_passed else "None"),
        Metric(label="Domain E-value", value=f"{hmmer_evalue:.2e}" if hmmer_passed else "—"),
    ]
    protparam = "Physicochemical profile · ProtParam"
    metrics += [Metric(label=key, value=str(value), group=protparam) for key, value in physio.items()]
    embedding_group = "Sequence embedding · ESM-2"
    metrics += [
        Metric(label="Model", value=ESM_MODEL_NAME, group=embedding_group),
        Metric(label="Dimensions", value=str(esm.get("embedding_dimensions")), group=embedding_group),
        Metric(label="Device", value=str(pipeline.device), group=embedding_group),
    ]
    thresholds = "Scoring thresholds (from the notebook)"
    metrics += [
        Metric(label="DIAMOND identity", value=f"> {pipeline.DIAMOND_IDENTITY_THRESHOLD:g}%", group=thresholds),
        Metric(label="DIAMOND query coverage", value=f"≥ {pipeline.DIAMOND_QUERY_COVERAGE_THRESHOLD:g}%", group=thresholds),
        Metric(label="HMMER independent E-value", value=f"< {pipeline.HMMER_EVAL_THRESHOLD:.0e}", group=thresholds),
    ]

    # --- Evidence: the notebook's own summary lines
    evidence = []
    for line in consensus["summary"]:
        if line.startswith("[+] "):
            evidence.append(EvidenceItem(polarity="positive", text=line[4:]))
        elif line.startswith("[-] "):
            evidence.append(EvidenceItem(polarity="negative", text=line[4:]))
        else:
            evidence.append(EvidenceItem(polarity="neutral", text=line))

    # --- Notes: the notebook's interpretation, plus any tool errors
    notes = [Note(kind="observation", title=title, text=text) for title, text in results["interpretation"]]
    for tool, result in (("DIAMOND", diamond), ("HMMER", hmmer)):
        if result.get("error"):
            notes.append(Note(kind="caution", title=f"{tool} reported a problem", text=str(result["error"])[:400]))

    # --- Tables
    hit_rows: list[dict[str, str]] = []
    if hit is not None:
        hit_rows.append(
            {
                "entry": f"{hit['accession']} ({hit['entry']})",
                "protein": hit["protein"] or "—",
                "organism": hit["organism"] or "—",
                "identity": f"{identity:.2f}%",
                "coverage": f"{coverage:.2f}%",
                "evalue": f"{float(diamond['e_value']):.2e}" if float(diamond["e_value"]) else "0.0",
                "bits": f"{float(diamond.get('bitscore', 0.0)):g}",
                "query": f"{diamond.get('qstart', '?')}–{diamond.get('qend', '?')}",
                "subject": f"{diamond.get('sstart', '?')}–{diamond.get('send', '?')} of {diamond.get('slen', '?')}",
            }
        )
    tables = [
        Table(
            key="swissprot-hit",
            title="Best Swiss-Prot hit",
            caption="DIAMOND blastp against UniProtKB/Swiss-Prot (top target, as in the notebook)",
            columns=[
                TableColumn(key="entry", label="Entry", mono=True),
                TableColumn(key="protein", label="Protein"),
                TableColumn(key="organism", label="Organism"),
                TableColumn(key="identity", label="Identity", align="right"),
                TableColumn(key="coverage", label="Coverage", align="right"),
                TableColumn(key="evalue", label="E-value", align="right", mono=True),
                TableColumn(key="bits", label="Bit score", align="right"),
                TableColumn(key="query", label="Query", align="right", mono=True),
                TableColumn(key="subject", label="Subject", align="right", mono=True),
            ],
            rows=hit_rows,
        ),
        Table(
            key="pfam-domains",
            title="Pfam domains",
            caption=f"hmmscan against Pfam-A; domains with independent E-value < {pipeline.HMMER_EVAL_THRESHOLD:.0e}",
            columns=[
                TableColumn(key="family", label="Family"),
                TableColumn(key="accession", label="Accession", mono=True),
                TableColumn(key="description", label="Description"),
                TableColumn(key="residues", label="Residues", align="right", mono=True),
                TableColumn(key="evalue", label="E-value", align="right", mono=True),
            ],
            rows=[
                {
                    "family": domain["domain"],
                    "accession": domain["accession"],
                    "description": domain["description"] or "—",
                    "residues": f"{domain['start']}–{domain['end']}",
                    "evalue": f"{domain['e_value']:.2e}",
                }
                for domain in domains
            ],
        ),
    ]

    # --- Tracks: domains on the combined map; the homology region in this section
    tracks: list[Track] = []
    if domains:
        best_domain = min(domains, key=lambda domain: domain["e_value"])
        tracks.append(
            Track(
                key="domains",
                label="Domains",
                caption="Primary · Pfam",
                style="blocks",
                segments=[
                    Segment(
                        start=domain["start"],
                        end=domain["end"],
                        tone="accent" if domain is best_domain else "ink",
                        label=domain["domain"],
                    )
                    for domain in domains
                ],
            )
        )
    if hit is not None:
        qstart, qend = sorted((int(diamond["qstart"]), int(diamond["qend"])))
        qstart, qend = max(1, qstart), min(length, qend)
        if qstart <= qend:
            tracks.append(
                Track(
                    key="swissprot-hit",
                    label="Swiss-Prot hit",
                    caption="Primary · DIAMOND",
                    style="blocks",
                    segments=[Segment(start=qstart, end=qend, tone="neutral", label=hit["entry"])],
                    overview=not domains,
                )
            )

    # --- Links
    links: list[Link] = []
    if hit is not None:
        links.append(Link(label=f"UniProt {hit['accession']}", url=f"https://www.uniprot.org/uniprotkb/{hit['accession']}/entry"))
    seen: set[str] = set()
    for domain in domains:
        pfam_id = str(domain["accession"]).split(".", 1)[0]
        if pfam_id.startswith("PF") and pfam_id not in seen:
            seen.add(pfam_id)
            links.append(Link(label=f"Pfam {pfam_id} ({domain['domain']})", url=f"https://www.ebi.ac.uk/interpro/entry/pfam/{pfam_id}/"))

    embedding = esm.get("embedding")
    raw = {
        "diamond": {key: value for key, value in diamond.items()},
        "hmmer": {key: value for key, value in hmmer.items()},
        "esm": {
            "source": esm.get("source"),
            "embedding_dimensions": esm.get("embedding_dimensions"),
            "embedding": [round(float(value), 6) for value in embedding.tolist()] if embedding is not None else None,
        },
        "physicochemical": physio,
        "consensus": {"summary": consensus["summary"]},
        "interpretation": [{"title": title, "text": text} for title, text in results["interpretation"]],
    }

    return LevelResult(
        source="live",
        headline=(
            Headline(value=f"{identity:.2f}%", label="best Swiss-Prot hit identity")
            if has_hit
            else Headline(value="No hit", label="Swiss-Prot homology search")
        ),
        summary=summary,
        metrics=metrics,
        evidence=evidence,
        tracks=tracks,
        tables=tables,
        notes=notes,
        links=links,
        raw=raw,
    )


# --- The entry point used by the app ---------------------------------------------------


def analyze(sequence: str, ctx: StageContext) -> LevelResult:
    """Run the notebook's pipeline and return the result for the interface."""
    missing = missing_setup()
    if missing:
        raise LevelSkipped(
            "Primary-structure analysis is not set up yet (missing: "
            + ", ".join(missing)
            + "). Run scripts/setup_primary.sh once, then restart the backend."
        )
    pipeline = get_pipeline(ctx)
    results = pipeline.execute(sequence, ctx)
    return _to_level_result(sequence, results, pipeline)
