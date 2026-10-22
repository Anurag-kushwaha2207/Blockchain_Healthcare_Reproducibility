# Blockchain audited private healthcare federated learning

This package accompanies the manuscript on irreversible privacy reservations
and verifiable model aggregation. It contains runnable experiments and the
complete measured outputs. It is a research prototype, not clinical software.

## Evidence included

- 240 primary utility runs: two datasets, six settings, twenty random seeds.
- 90 additional client-count and Dirichlet-allocation sensitivity runs.
- Twenty paired audited and unaudited runs, with identical final models.
- One thousand trials for each of eight defined protocol fault types.
- A signed-poisoning negative control that is accepted, demonstrating the limit
  of provenance checks rather than disguising it as a successful defence.
- One hundred pairs of concurrent reservations, each with a single winner.
- A signed, hash-linked example trace with 560 governance events.

The wearable surrogate is wholly synthetic. No patient records from the source
manuscript are included, reused or reconstructed. WDBC is the public Wisconsin
Diagnostic Breast Cancer dataset, loaded from the copy distributed with
scikit-learn. Its UCI source is https://doi.org/10.24432/C5DW2B and its repository
license is CC BY 4.0. The public benchmark is not a clinical validation.

## Reproduce

Use Python 3.12 or a compatible Python 3 environment. Install the versions in
requirements.txt in an isolated environment. From this package directory run:

```bash
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reproducibility/experiment.py --seeds 20
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reproducibility/protocol.py
python reproducibility/figures.py
python build_manuscript.py
```

On Windows, set the two thread environment variables before executing Python.
All paths are resolved relative to the scripts. The first command regenerates
utility_runs.csv, utility_summary.csv, details.json and config.json. The second
regenerates audit_attacks.csv, audit_summary.json and ledger_example.json.
The third generates seven PNG figures and corresponding editable SVG files.
The manuscript builder creates a Word document in the parent output/documents
directory, including seventeen native editable OMML equations.

Test accuracy is measured on one fixed stratified split. Means and standard
deviations describe variation over the stated partition and noise seeds; they
do not estimate cross-hospital or population-level uncertainty. Seed zero was
chosen in advance for the confusion and convergence figures. Ledger auditing
does not alter the numerical learning mechanism. One local full-batch step
with complete participation creates the partition-invariance discussed in the
paper. Do not generalize that identity to multiple local epochs or dropouts.

The experiment uses a fixed-point conservative zCDP accountant, a replace-one
record adjacency relation, fixed public sample counts and public transformation
constants. Clipping is applied to each actual gradient matrix. Gaussian noise
is generated every round. No privacy amplification from sampling is claimed.

## Security boundary

protocol.py is a single-process signed ledger emulator, not a running Fabric or
PBFT deployment. Three-of-four signatures emulate certificates but do not
implement a distributed consensus network. Its concurrency check exercises a
process lock. Timings are local cryptographic microbenchmarks, not network
finality latency or blockchain throughput. Their exact values vary by machine
and load and are not expected to reproduce bit for bit.

Benchmark keys, nonces and random seeds are deliberately public fixtures. They
must never be reused with confidential records. Real deployments require fresh
protected randomness, secure signing keys, durable budget scopes, actual
consensus finality and authenticated institutional endpoints. A valid signature
and payload commitment cannot certify that a malicious endpoint used the
correct clipping or noise mechanism. The conditional privacy theorem assumes
honest local computation and private noise randomness. Authorization epochs
represent institutional training permission, not patient-level legal consent.

The controller never refunds a reserved cost. A failed or rejected release
attempt may have already exposed information and remains charged. This rule
can waste budget when no disclosure happened; that availability tradeoff is
disclosed rather than hidden. Patient-level privacy, private cohort selection,
overlapping institutional records, poisoning robustness and model unlearning
require separate analysis.

## Layout

- build_manuscript.py: Word authoring with native equations and result tables.
- reproducibility/experiment.py: data generation and privacy-utility runs.
- reproducibility/protocol.py: signed reservations, checks and fault tests.
- reproducibility/figures.py: all scientific diagrams and result plots.
- reproducibility/results/: raw per-run measurements and an example ledger.
- figures/: high-resolution PNG and editable SVG figures.
- manuscript_text.md: searchable manuscript text for content review.
- manuscript_manifest.json: counts and file metadata.

The existing literature already includes blockchain federated learning and
privacy-budget contracts. The paper proposes a specifically defined lifecycle
and its integration, not a guaranteed first-ever combination of those ideas.
