"""Example proteins offered in the interface.

The sequences come from the primary- and secondary-structure notebooks.
The p53 sequence is the canonical 393-residue UniProt P04637 entry (the
notebook copy was missing Arg-181).

The function, Gene Ontology terms and assembly state below are established
facts about each protein. While the analysis modules are not connected, the
placeholder verdict uses them so that demos with these examples look right.
They are never used for sequences the user types in.
"""

from dataclasses import dataclass

from .schemas import ExampleSequence, GoTerm


@dataclass(frozen=True)
class ExampleProfile:
    key: str
    name: str
    organism: str
    reference: str
    sequence: str
    function: str
    description: str
    go_terms: tuple[GoTerm, ...]
    assembly: str

    def as_schema(self) -> ExampleSequence:
        return ExampleSequence(
            key=self.key,
            name=self.name,
            organism=self.organism,
            reference=self.reference,
            sequence=self.sequence,
            length=len(self.sequence),
        )


def _mf(go_id: str, term: str) -> GoTerm:
    return GoTerm(id=go_id, term=term, aspect="molecular_function")


EXAMPLES: tuple[ExampleProfile, ...] = (
    ExampleProfile(
        key="ubiquitin",
        name="Ubiquitin",
        organism="Homo sapiens",
        reference="PDB 1UBQ",
        sequence=(
            "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYN"
            "IQKESTLHLVLRLRGG"
        ),
        function="Protein modifier (ubiquitin)",
        description=(
            "Small, highly conserved protein that is attached to other proteins to tag them for degradation or to change their activity."
        ),
        go_terms=(
            _mf("GO:0031386", "protein tag activity"),
            _mf("GO:0031625", "ubiquitin protein ligase binding"),
        ),
        assembly="Monomer",
    ),
    ExampleProfile(
        key="hemoglobin-alpha",
        name="Hemoglobin α",
        organism="Homo sapiens",
        reference="UniProt P69905",
        sequence=(
            "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHG"
            "KKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTP"
            "AVHASLDKFLASVSTVLTSKYR"
        ),
        function="Oxygen transport protein (globin)",
        description=(
            "Alpha subunit of haemoglobin; binds heme and carries oxygen in red blood cells as part of an α2β2 tetramer."
        ),
        go_terms=(
            _mf("GO:0005344", "oxygen carrier activity"),
            _mf("GO:0020037", "heme binding"),
        ),
        assembly="Heterotetramer (α2β2)",
    ),
    ExampleProfile(
        key="bacteriorhodopsin",
        name="Bacteriorhodopsin",
        organism="Halobacterium salinarum",
        reference="UniProt P02945",
        sequence=(
            "MLELLPTAVEGVSQAQITGRPEWIWLALGTALMGLGTLYFLVKGMGVSDPDAKKFYAITT"
            "LVPAIAFTMYLSMLLGYGLTMVPFGGEQNPIYWARYADWLFTTPLLLLDLALLVDADQGT"
            "ILALVGADGIMIGTGLVGALTKVYSYRFVWWAISTAAMLYILYVLFFGFTSKAESMRPEV"
            "ASTFKVLRNVTVVLWSAYPVVWLIGSEGAGIVPLNIETLLFMVLDVSAKVGFGLILLRSR"
            "AIFGEAEAPEPSAGDGAAATSD"
        ),
        function="Light-driven proton pump",
        description=(
            "Seven-helix membrane protein that uses a bound retinal to pump protons across the cell membrane when illuminated."
        ),
        go_terms=(
            _mf("GO:0009881", "photoreceptor activity"),
            _mf("GO:0015078", "proton transmembrane transporter activity"),
        ),
        assembly="Homotrimer",
    ),
    ExampleProfile(
        key="p53",
        name="p53",
        organism="Homo sapiens",
        reference="UniProt P04637",
        sequence=(
            "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP"
            "DEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAK"
            "SVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHE"
            "RCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNS"
            "SCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELP"
            "PGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPG"
            "GSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD"
        ),
        function="DNA-binding transcription factor",
        description=(
            "Tumour suppressor that binds DNA as a tetramer and activates genes controlling cell-cycle arrest, DNA repair and apoptosis."
        ),
        go_terms=(
            _mf("GO:0003700", "DNA-binding transcription factor activity"),
            _mf("GO:0003677", "DNA binding"),
        ),
        assembly="Homotetramer",
    ),
    ExampleProfile(
        key="akt1",
        name="AKT1",
        organism="Homo sapiens",
        reference="UniProt P31749",
        sequence=(
            "MSDVAIVKEGWLHKRGEYIKTWRPRYFLLKNDGTFIGYKERPQDVDQREAPLNNFSVAQC"
            "QLMKTERPRPNTFIIRCLQWTTVIERTFHVETPEEREEWTTAIQTVADGLKKQEEEEMDF"
            "RSGSPSDNSGAEEMEVSLAKPKHRVTMNEFEYLKLLGKGTFGKVILVKEKATGRYYAMKI"
            "LKKEVIVAKDEVAHTLTENRVLQNSRHPFLTALKYSFQTHDRLCFVMEYANGGELFFHLS"
            "RERVFSEDRARFYGAEIVSALDYLHSEKNVVYRDLKLENLMLDKDGHIKITDFGLCKEGI"
            "KDGATMKTFCGTPEYLAPEVLEDNDYGRAVDWWGLGVVMYEMMCGRLPFYNQDHEKLFEL"
            "ILMEEIRFPRTLGPEAKSLLSGLLKKDPKQRLGGGSEDAKEIMQHRFFAGIVWQHVYEKK"
            "LSPPFKPQVTSETDTRYFDEEFTAQMITITPPDQDDSMECVDSERRPHFPQFSYSASGTA"
        ),
        function="Serine/threonine-protein kinase",
        description=(
            "AGC-family kinase with an N-terminal pleckstrin-homology domain; a lipid-activated regulator of cell survival and metabolism."
        ),
        go_terms=(
            _mf("GO:0004674", "protein serine/threonine kinase activity"),
            _mf("GO:0005524", "ATP binding"),
        ),
        assembly="Monomer",
    ),
)

_BY_SEQUENCE = {example.sequence: example for example in EXAMPLES}


def find_example(sequence: str) -> ExampleProfile | None:
    """Return the example profile whose sequence matches exactly, if any."""
    return _BY_SEQUENCE.get(sequence)
