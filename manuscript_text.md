Anurag Singh, Anurag and Brijesh Kumar Chaurasia

Computer Science and Engineering
Pranveer Singh Institute of Technology, Kanpur, India


Abstract


Cross institutional healthcare learning requires controls over both information disclosure and the integrity of shared model updates. We propose blockchain audited private federated learning, a permissioned protocol that couples each protected update to an irreversible privacy budget reservation, an institutional authorization epoch and a signed model commitment. Record gradients are clipped before Gaussian perturbation at every communication round. A zero concentrated differential privacy accountant bounds the complete training transcript, while independent auditors verify the weighted aggregation of committed protected models. The ledger stores governance metadata and commitments; patient records and model payloads remain off chain. We establish conditional privacy and reservation invariants and implement a signed ledger state machine emulator. Controlled experiments comprise 330 utility runs on a wholly synthetic four class wearable surrogate and the public Wisconsin Diagnostic Breast Cancer benchmark. At ε = 4 and δ = 10⁻⁵, mean accuracy across 20 runs is 62.86% ± 0.29% for the wearable surrogate and 92.55% ± 1.21% for the public benchmark. Auditing preserves the final model exactly in 20 matched runs. Eight defined protocol fault classes are rejected in 1,000 trials each, and concurrent budget reservations admit exactly one request in all 100 contention tests. A signed poisoning negative control remains accepted, demonstrating that provenance does not establish statistical correctness. The contribution is an explicit disclosure accounting lifecycle with verifiable model provenance, evaluated at protocol level; clinical validation and distributed consensus benchmarking remain necessary.

Keywords  blockchain governance; federated learning; differential privacy; healthcare analytics; privacy accounting; verifiable aggregation


1 Introduction


Healthcare institutions hold complementary data that can improve statistical modelling, but sharing patient records creates confidentiality, stewardship and operational concerns. Federated learning offers a practical way to coordinate model development across these boundaries by exchanging model updates from locally held data [1, 2]. Keeping records at their originating institution, however, leaves two separate questions unresolved. A shared update can disclose information about a training record, and a coordinator can alter, omit or reuse an update without an independently verifiable account of the resulting model. A useful healthcare federation must therefore specify what is disclosed, how disclosure is charged and how the accepted computation is checked.

Differential privacy addresses the first question through a probabilistic bound on the influence of an individual record [3–6]. The guarantee concerns the observer’s entire accessible transcript. If earlier communication rounds expose clean updates, adding noise only to a later model does not establish that the previous disclosures were private. Privacy accounting must also include fresh releases that fail an application level validation check. The rejection of a model update cannot erase information that a recipient already observed. A budget counter that decreases after such a rejection can therefore understate cumulative disclosure even when its individual arithmetic operations appear correct.

Blockchain technology provides an ordered, replicated record of governance events and model commitments. Existing blockchain federated learning systems establish substantial precedents for decentralized coordination, update verification and incentives [8–11]. Their existence makes a generic combination of blockchain, federated learning and differential privacy an insufficient novelty claim. The question pursued here is narrower: how can a privacy reservation, a noisy release and a verified aggregation be linked so that aborts, retries and concurrent requests cannot create uncharged disclosure? The protocol also needs to limit what it permanently records, because ledger immutability can preserve sensitive metadata as readily as useful evidence.

We introduce blockchain audited private federated learning, abbreviated BAPFL. The proposed integration charges a fixed, policy approved privacy cost before a protected model is disclosed and never refunds that reservation. A signed receipt binds the release to its institution, authorization epoch, parent model and communication round. The accepted roster and aggregation weights are frozen before an independently recomputed global model is anchored. These controls address an auditable lifecycle rather than proposing a new consensus algorithm or a new definition of differential privacy.

The contributions are fourfold. First, we specify an irreversible reservation state machine that treats unsuccessful release attempts conservatively and prevents duplicate charging or replay from being confused with a fresh noisy computation. Second, we derive a full transcript privacy bound for clipped Gaussian updates under a fixed cohort and an honest training endpoint assumption. Third, we couple protected model commitments to a checkable aggregation receipt without publishing raw data, raw gradients or fitted feature statistics. Fourth, we provide executable experiments, including a negative control that separates protocol integrity from poisoning resistance. The resulting evidence supports a protocol contribution with explicit boundaries rather than a claim of deployment readiness.


2 Related Research and Research Gap



2.1 Federated healthcare and formal privacy


FedAvg established a widely used approach to aggregating model parameters trained across distributed clients [1]. Healthcare adoption adds institutional variation, small cohorts, incompatible data practices and restrictions on data access [2]. In this paper, the statistical learner deliberately remains a transparent softmax model so that the effect of the governance layer can be isolated. The earlier three client healthcare manuscript [19] motivates the application structure, but its dataset and complete executable training implementation are unavailable for independent reproduction. Its reported 97.15% accuracy is not treated as an experimental result of the new protocol.

Differentially private empirical risk minimisation requires both a valid sensitivity argument and a noise distribution that matches that argument [20]. Gradient clipping and Gaussian perturbation provide a more direct bounded query construction for iterative training [4]. Zero concentrated differential privacy supports additive accounting for Gaussian mechanisms [5], while Rényi differential privacy provides a related framework for composition [6]. Privacy filters distinguish prospective enforcement of a disclosure limit from retrospective measurement [7]. We use an explicit fixed allocation, without a subsampling amplification claim, to keep the implemented accountant and the theoretical bound aligned.


2.2 Blockchain coordination and update accountability


BlockFL uses blockchain coordination to exchange and verify local model updates and analyses the associated communication, computation and consensus delays [8]. Biscotti combines distributed learning with cryptographic validation and privacy mechanisms, including a broader treatment of adversarial peers [9]. These systems show that decentralized provenance and model update verification are established research directions. Our protocol instead concentrates on whether every protected release is covered by an irreversible budget charge and a version bound receipt. We do not claim to reproduce Biscotti’s poisoning defence or distributed scalability.

De Chaudhury and colleagues study local differential privacy with incentives and encrypted model access in a permissioned blockchain setting [10]. BE-DPFL explicitly introduces a privacy budget contract alongside on chain supervision and off chain learning [11]. Budget contracts themselves are therefore prior art. BAPFL’s proposed distinction is the precise reservation semantics: budget is charged before possible disclosure, a failed update cannot return the charge, retries cannot silently redraw noise and the aggregation receipt binds the accepted update set to a particular parent model. The literature comparison identifies the design problem investigated here; it does not establish an exhaustive first publication claim.

Table 1 Positioning of BAPFL against established research

Research line | Established contribution | Question examined in BAPFL

FedAvg [1] | Distributed model averaging | Bind the accepted update set to a verifiable model version

Private learning [4–7, 20] | Bounded disclosure and composition | Enforce the accountant before each possible release

BlockFL [8] | Blockchain coordination and latency analysis | Record reservation and release order explicitly

Biscotti [9] | Private decentralized learning and update validation | Audit disclosure charges without claiming its poisoning defence

Permissioned incentives [10] | Private contribution and access incentives | Prevent abort or replay from resetting a disclosure charge

BE-DPFL [11] | Privacy budget contracts and supervision | Specify irreversible charges and version bound aggregation


2.3 Problem statement


Given an established cross silo training cohort and a public training policy, construct a federation in which every new protected release is preceded by a finalized privacy reservation; the total transcript satisfies a stated record level privacy bound; and the accepted global model can be checked against committed protected client models. The reservation must remain charged after rejection or timeout, and concurrent requests must not jointly exceed the remaining budget. Governance evidence should be recorded without permanently publishing patient records or model payloads. These requirements define the gap addressed by the proposed lifecycle and the executable tests.


3 System Model and Security Objectives



3.1 Participants and trust boundaries


The federation contains K healthcare institutions, a replaceable off chain coordinator, independent aggregation auditors and a permissioned validator set. Each institution holds a disjoint, fixed size training set Dk and runs a controlled training agent. Validators order governance transactions; auditors validate protected model payloads and recompute their weighted average. The coordinator need not be trusted with clean updates or with the correctness of the final aggregation. The local training agent must nevertheless execute the declared clipping and noise mechanism honestly. A signature establishes who signed a payload, not how that payload was computed.

The privacy analysis fixes dataset membership, per institution sample counts and all transformation constants. Neighbouring datasets differ by replacing one record in one institution while retaining those public quantities. The resulting guarantee is record level privacy, not protection of an entire institution or a patient’s arbitrarily many visits. Experimental train test splitting and label based Dirichlet partitioning are benchmark construction steps outside this mechanism. In a deployment, cohort enrollment, patient deduplication and the privacy implications of institutional membership require separate controls. The theorem does not make those processes private.

Institutional training authorization is represented by a public epoch counter. The emulator’s consent_epoch field denotes this institutional authorization version; it is not a patient level legal consent registry. Patient permissions are checked within the institution and are not placed on the ledger. Revocation stops future release authorization after the relevant governance event is finalized. It cannot withdraw already disclosed information or remove a patient’s past influence from a previously released model. Retrospective model removal would require a separate unlearning design.


3.2 Ledger and payload placement


A ledger entry contains a scoped institution identifier, round number, parent model hash, approved privacy cost, authorization epoch, payload commitment and signature. Protected model parameters are transmitted through authenticated off chain channels. Patient records, labels, unperturbed gradients and fitted feature means or variances are excluded from the ledger. Commitments cover only protected outputs. This avoids treating a hash of a low entropy patient attribute as if it were an anonymisation mechanism. Public metadata remain visible within the permissioned consortium and can still reveal participation patterns.

A practical deployment may use Hyperledger Fabric with a Byzantine fault tolerant ordering configuration. Fabric separates transaction execution, ordering and validation [12, 13]. Clients must observe a valid committed transaction before disclosing an update; an ordering acknowledgment alone is insufficient because an ordered transaction can later be invalidated. Four orderers with a three member quorum provide the proposed f = 1 configuration. The implemented emulator signs hash linked records with three of four fixture validators, but does not implement distributed network consensus, leader change or partition recovery.

Figure 1 Proposed separation of local data, off chain protected model computation and permissioned blockchain governance. The three institutions are simulated sites; the validator topology is a deployment design.


3.3 Adversarial capabilities and objectives


The coordinator or a transport adversary may alter a payload, replay a receipt, substitute an obsolete parent model, misstate an aggregate or request training beyond an institution’s declared budget. A compromised institution may produce a validly signed but statistically malicious update. Validators are assumed to remain within the chosen consensus fault threshold, and auditors retain a trusted committed checkpoint. The first group of protocol faults is tested mechanically. Poisoning, malicious noise omission, endpoint compromise and a compromised validator majority are outside the proven protection boundary. Gradient reconstruction and model poisoning are established threats [15, 16], but neither attack is claimed to have been exhaustively evaluated here.

Table 2 Security objectives and the conditions under which they are meaningful

Objective | Required invariant

Transcript privacy | Only properly clipped and perturbed new outputs leave an honest training agent

Budget integrity | Every possible fresh release has an irreversible reservation

Origin and freshness | Receipt signature, authorization epoch and parent model match the accepted round

Aggregation integrity | Auditor recomputes the weighted average of the frozen protected update set

Data minimisation | Ledger contains commitments and public governance fields, not patient data

Explicit trust boundary | Signatures do not certify correct clipping, noise sampling or clinical validity


4 Blockchain Audited Private Federated Learning



4.1 Public transformation and statistical learner


The input transform uses predeclared centering and scale constants. Component values are bounded and the augmented vector, including a bias coordinate, is projected to unit Euclidean norm. No training derived normalisation statistic is released or used to calibrate the sensitivity bound. Appendix A and the implementation specify the exact constants. For J classes, W has J rows and d + 1 columns. We implement the softmax probabilities directly, avoiding a mismatch between a multinomial objective and a one versus rest software classifier.

Equation 1: Multinomial softmax probability

Equation 2: Regularized multiclass empirical objective

Let vi denote the augmented, component bounded input before norm projection. The transform is fixed independently of the protected cohort. The regularisation term applies to all coordinates, including the bias coordinate. Class balancing weights are not estimated from private class counts; the benchmark uses an unweighted objective. This preserves a simple correspondence between the bounded per record query and the implemented training step.

Equation 3: Fixed augmented input norm projection


4.2 Private local update and model averaging


At round t, all participating clients receive the same authenticated parent model Wt. Institution k computes one full batch gradient contribution for each local record, then clips the complete gradient matrix in Frobenius norm at C. The clipping operation acts on each actual contribution, not merely on a number used later in a sensitivity formula. The mean clipped gradient receives independent Gaussian noise in every coordinate. The implementation uses C = 0.5, η = 2.0 and λ = 0.003, with 80 rounds.

Equation 4: Actual per record gradient clipping

Equation 5: Noisy full batch local gradient

Equation 6: Sensitivity calibrated noise and protected local model

Equation 7: One local step FedAvg with public fixed sample weights

Only the protected local model Wk is eligible for transmission. Raw gradients, clean intermediate models and model fitted feature statistics remain local. One local step is intentionally used so that the contribution of ledger auditing can be separated from local optimiser drift. The analysis and results do not imply equivalent behaviour for multiple local epochs, minibatch sampling or partial participation. Secure aggregation can be added to hide an institution’s protected vector from the coordinator [14], but it is not implemented here and would require a compatible aggregation verification mechanism.


4.3 Irreversible privacy reservation


Before generating a protected release, the training agent requests a reservation for a fixed policy approved cost. The contract checks institutional authorization, the current epoch, the authenticated parent model, uniqueness of the round reservation and the remaining budget. A valid committed reservation immediately reduces available budget. Once charged, the amount cannot be refunded, even if computation, transport or payload validation later fails. This conservative rule accounts for the possibility that a protected output was exposed before the application recognised the failure.

A reservation may be overconservative when a client aborts before computing or disclosing anything. That loss of available budget is an explicit availability tradeoff. Recovering such a charge safely would require trustworthy evidence that no disclosure occurred; a client assertion alone is insufficient. The protocol chooses a simple irreversible rule so that application success is never used as a proxy for whether information escaped. A fresh noisy retry requires a new reservation. Returning the identical cached protected output is postprocessing of the same release and does not create a new independently perturbed computation.

Equation 8: Conservative fixed point privacy allocation and recalibrated noise

The contract uses integer units of 10⁻¹² in ρ. The cap is rounded down and the per round allocation is an integer floor division. The noise multiplier is recalibrated to that exact allocation. Thus rounding cannot charge less than the implemented ideal Gaussian mechanism consumes. Production code also needs a reviewed floating point or discrete noise implementation; the NumPy benchmark evaluates the learning behaviour of the mathematical mechanism rather than certifying a hardened differential privacy runtime.

Figure 2 Reservation lifecycle. Disclosure charges persist after an aborted or rejected update. Institution authorization and a valid committed reservation are required before a new protected output can be released.


4.4 Version bound receipts and aggregation audit


After reservation finality, the institution computes its protected local model, encodes it as canonical little endian float64 bytes, and signs a receipt. The receipt binds the institution, round, parent model, cost, authorization epoch, schema, nonce and model commitment. A collision resistant hash commits to the nonce and the protected payload. In deployment, nonces and keys are freshly generated and private key material is protected. The emulator uses public deterministic fixture keys and nonces solely to make its mechanical tests reproducible; those fixtures are not a deployment security configuration.

Equation 9: Protected model commitment and institution signature

Auditors reject a receipt if its signature or reservation binding is invalid, its authorization has been revoked, its parent model is stale or its round receipt has already been used. They then verify the off chain payload against the committed hash and reject nonfinite model coordinates. These checks are predicates of public metadata or already protected outputs. They do not require access to patient records or clean gradients. The accepted roster is fixed before aggregation so that the coordinator cannot claim a different participant set after observing the result.

Equation 10: Independent numerical aggregation verification for the accepted roster A

The aggregation receipt includes the accepted institution set, public weights, parent model commitment and resulting global model commitment. A trusted checkpoint makes subsequent hash chain alteration detectable. Merely recomputing an unanchored chain after rewriting all of its contents would not establish integrity. A distributed deployment must enforce common policy state and finality through the actual consensus protocol rather than through the emulator’s process lock.


4.5 Audited training algorithm


1  Authenticate the round policy and its parent model; freeze the participating institution set and public sample weights.

2  Read the institution authorization epoch and the remaining global budget for its established training scope.

3  Commit a unique integer cost reservation. Await a valid peer commit event. Abort without disclosure if authorization fails.

4  Transform local records with the fixed public constants, compute their softmax gradients and clip each matrix at C.

5  Add fresh independent Gaussian noise at the policy approved scale and construct the protected local model.

6  Commit a signed receipt binding the reservation, epoch, round, parent model, nonce and protected model hash.

7  Transmit the protected payload off chain. Verify receipt authenticity, freshness, finite values and the payload commitment.

8  Freeze accepted updates and recompute their weighted average. Reject an inconsistent claimed aggregation.

9  Anchor the global model receipt and retain the completed reservation cost. Never reduce the counter after rejection or timeout.

10  Continue only while the fixed privacy cap and current institutional authorization permit another reserved release.


5 Formal Analysis



5.1 Bounded query sensitivity


Proposition 1. Fix a round transcript and the shared parent model. Under replace one record adjacency with fixed nk, the sensitivity of the mean clipped local gradient is at most 2C/nk in Frobenius norm. Proof. Replacing one record replaces one clipped matrix by another. Each matrix has norm at most C, so their difference has norm at most 2C by the triangle inequality. Division by the fixed sample count gives the stated bound. Changes in the regularisation term are zero for the fixed parent model. This argument requires actual clipping of each contribution and does not depend on optimisation convergence or a data estimated feature radius.

Equation 11: Replace one record sensitivity bound


5.2 Complete transcript privacy


Proposition 2. For an honest institution, an ideal Gaussian gradient release with σk = zΔk satisfies ρt = 1/(2z²) zero concentrated differential privacy [5]. The protected local model is a deterministic transformation of that release and the already observed parent model, so it inherits the bound. Adaptive choices of parent models based on prior protected outputs are covered by composition. A coordinator therefore cannot remove the clipping bound simply by selecting an unusual parent model. The fixed public transformation and policy contribute no new protected data query.

Equation 12: Gaussian zCDP cost and sequential composition within one institution

Let Rk include every fresh protected release, including releases whose payloads were rejected or later omitted from a global model. Composition bounds that institution’s accessible transcript by the sum of those costs. Under the established disjoint record assignment, the federation’s record level bound uses the largest institutional cumulative cost rather than adding costs across unrelated records. If the same patient or record appears in multiple institutions, this disjointness condition fails and an appropriate cross institution or patient level accountant is necessary.

Equation 13: zCDP conversion to approximate differential privacy for the fixed disjoint cohort

Equation 14: Closed form cumulative zCDP cap for a requested epsilon and delta

Ledger hashes, signatures, acceptance decisions and an audited aggregate are functions of public metadata and protected outputs. They are postprocessing and do not add a new record disclosure under the assumptions above. This statement excludes data dependent participation decisions, fresh unnoised validation statistics and patient derived governance metadata. Publishing benchmark noise seeds permits experiment reproduction; a deployment must instead use independent private randomness. The theoretical guarantee presumes that those noise draws remain unknown to the adversary.


5.3 Budget safety and aggregation integrity


Proposition 3. If every fresh protected output is gated by a finalized reservation, the charged ledger sum upper bounds the sum of actual mechanism costs. Proof. Each possible fresh release is assigned a unique reservation, and its approved cost is charged before disclosure. No state transition decreases that charge. A reservation that never produces a release contributes a nonnegative surplus. An aborted or rejected release remains covered. Atomic balance checks serialize concurrent reservations, so two individually feasible requests cannot together exceed the cap. The bound depends on a training endpoint that cannot bypass the release gate and on a ledger that retains the same budget scope across restarts and jobs.

Equation 15: Irreversible reservation sum upper bounds actual charged fresh releases

Proposition 4. For an authenticated frozen roster and public weights, an auditor with the committed protected payloads detects a claimed model that differs from their weighted average by more than τ. This is a numerical consistency statement, conditional on commitment binding and signature authenticity. It establishes neither correct local training nor robustness to a legitimately signed poisoned contribution. Ed25519 supplies the chosen receipt signature primitive [18]. The three signature emulator certificate is an executable fixture; Byzantine consensus safety in a deployed system remains a property of the chosen ordering implementation and its assumptions.

Equation 16: Proposed Byzantine ordering configuration and certificate threshold


5.4 Learning and storage implications


With full participation, one shared parent model, one local full batch step and public nk/N weights, the weighted deterministic clipped gradient equals the clipped gradient over the union of the fixed training records. Partition label skew therefore cancels algebraically in this restricted configuration. The Gaussian noise contribution has a different dependence: each client’s nk cancels its aggregation weight, leaving K independent equal scale noise matrices. The variance increases with the number of participating institutions for fixed N and privacy allocation.

Equation 17: Aggregate noise variance and the conditional partition invariance

This cancellation is a diagnostic prediction for the chosen optimiser, not a general theorem that non IID data never affect federated learning. Multiple local steps, private class weights, adaptive site selection and missing updates change the calculation. A signed receipt has approximately fixed size, whereas a dense float64 softmax model grows as 8J(d + 1) bytes. However, a blockchain record also contains certificates, hash links and governance fields. Receipt only storage comparisons must therefore be distinguished from full ledger storage, especially for small models.


6 Experimental Methodology



6.1 Datasets and public transformations


The wearable surrogate contains 6,000 wholly synthetic observations, with 1,500 records in each of four severity labels. It is not a clinical sensor dataset and its labels are not diagnoses. A class dependent latent severity plus Gaussian variation generates 13 sensor styled inputs: heart rate, oxygen saturation, systolic and diastolic pressure, glucose, temperature, respiratory rate, activity, sleep, stress, heart rate variability, steps and calories. Four derived inputs encode a heart rate to stress ratio, oxygen deficit, pressure difference and a vital risk index. The complete generator is provided so that every record can be reconstructed. No source patient data, SMOTE samples or original manuscript measurements are reused.

The second dataset is the public Wisconsin Diagnostic Breast Cancer dataset supplied through scikit learn and documented by the UCI repository [17]. It contains 569 observations and 30 numeric features describing cell nuclei from fine needle aspirate images. The experiment is a benchmark exercise on public data, not a prospective diagnostic study. A stratified fixed split creates 426 training and 143 test observations, while the wearable split creates 4,800 training and 1,200 test observations. No observation is discarded. Public transformation constants are fixed in the script; no normalizer is fitted to the test set or pooled private client data.

Table 3 Benchmark construction and fixed learning settings

Parameter | Wearable surrogate | Public WDBC

Data provenance | Wholly synthetic generator | Public UCI benchmark

Records before splitting | 6,000 | 569

Training records | 4,800 | 426

Test records | 1,200 | 143

Input features | 17 | 30

Output classes | 4 | 2

Test class counts | 300 per class | 53 malignant and 90 benign

Primary simulated institutions | 3 | 3

Rounds and local steps | 80 and 1 | 80 and 1

Gradient clipping C | 0.50 | 0.50

Step size η and penalty λ | 2.00 and 0.003 | 2.00 and 0.003

Privacy budgets ε | 0.50  1.00  2.00  4.00  8.00 | 0.50  1.00  2.00  4.00  8.00

Delta and primary repetitions | 10⁻⁵ and 20 | 10⁻⁵ and 20


6.2 Partitioning and comparison design


Training records are allocated by class specific Dirichlet draws with concentration 1.0. Draws with very small institutional samples are rejected using the threshold max(30, floor(N/(10K))). All accepted partitions contain every training record exactly once. Noise and partition seeds vary across 20 primary repetitions; the underlying dataset and test split remain fixed. Consequently, reported standard deviations describe randomisation and partition variation conditional on this split, not uncertainty across hospitals or independent patient populations. The nonprivate one step full batch baseline is deterministic despite changing client partitions.

Six settings are run for each dataset: matched nonprivate clipped FedAvg and five private settings. These produce 240 primary utility runs. A further 90 wearable runs vary K over 3, 6 and 10 and the Dirichlet concentration over 0.2, 1.0 and 10.0, with ten repetitions in each cell. The signed audit hook is additionally applied to 20 ε = 4 wearable runs and compared with an unaudited execution using identical numerical noise draws. This paired design measures whether governance changes the computation itself; it is not a comparison against a different optimiser or different privacy budget.

The emulator provides a lock protected reservation state machine, SHA 256 hash linked events, Ed25519 client receipts and three validator signatures per record. It stores actual serialized metadata and executes receipt checks. The benchmark does not start a Fabric network or measure Byzantine consensus under message delay. Its cryptographic operation timings are hosted container measurements, and its contention test exercises local atomicity rather than distributed consensus. The software configuration and raw per run metrics are included in the reproduction package.


6.3 Metrics and fault injection


Utility is evaluated with accuracy, macro F1 and macro recall, the latter serving as balanced accuracy. All percentage values are reported to two decimal places. Means and sample standard deviations use the 20 primary runs. Confusion matrices are shown for the preselected seed zero run rather than a selected best result. The fixed public test set is not used to select a client or tune a round. Hyperparameters are fixed across privacy settings and neither early stopping nor private validation release is performed.

The protocol tests inject a payload change, a replay, a stale parent model, a corrupted signature, a revoked authorization, an overspending reservation, a forbidden refund and a changed aggregate. Each class has 1,000 trials. A ninth class signs an arbitrary poisoned model with valid institution credentials and a matching commitment; it is an intentional negative control. One hundred two request contention tests leave enough budget for exactly one reservation. A separate accounting illustration performs 30 protected release attempts at ρ = 0.01 against a cap of 0.10, exposing the difference between actual disclosure and a counter that refunds every aborted release.


7 Results and Discussion



7.1 Privacy and utility


Table 4 Primary utility results as mean ± sample standard deviation across 20 fixed split repetitions

Dataset | Total ε | Accuracy % | Macro F1 % | Balanced accuracy %

Wearable | Nonprivate | 62.92 ± 0.00 | 58.32 ± 0.00 | 62.92 ± 0.00

Wearable | 0.50 | 62.72 ± 1.29 | 58.28 ± 2.01 | 62.72 ± 1.29

Wearable | 1.00 | 62.72 ± 0.86 | 58.07 ± 1.25 | 62.72 ± 0.86

Wearable | 2.00 | 62.86 ± 0.48 | 58.26 ± 0.67 | 62.86 ± 0.48

Wearable | 4.00 | 62.86 ± 0.29 | 58.30 ± 0.37 | 62.86 ± 0.29

Wearable | 8.00 | 62.81 ± 0.24 | 58.22 ± 0.31 | 62.81 ± 0.24

WDBC | Nonprivate | 92.31 ± 0.00 | 91.58 ± 0.00 | 90.79 ± 0.00

WDBC | 0.50 | 82.34 ± 6.35 | 80.62 ± 7.75 | 80.95 ± 7.77

WDBC | 1.00 | 89.02 ± 3.49 | 88.03 ± 4.15 | 87.83 ± 4.39

WDBC | 2.00 | 91.54 ± 1.86 | 90.80 ± 2.02 | 90.29 ± 2.07

WDBC | 4.00 | 92.55 ± 1.21 | 91.86 ± 1.32 | 91.14 ± 1.39

WDBC | 8.00 | 92.59 ± 0.86 | 91.88 ± 0.94 | 91.03 ± 0.95

The wearable surrogate yields 62.86% ± 0.29% accuracy at ε = 4, compared with a 62.92% deterministic matched nonprivate baseline. Its mean macro F1 is 58.30% ± 0.37%. The small privacy induced difference occurs because the statistical learner already struggles to separate the adjacent surrogate severity classes. It must not be interpreted as clinically adequate prediction or as replication of the much higher result reported in the earlier manuscript. The measured value illustrates preservation of an existing learner’s behaviour under a disclosed accounting mechanism.

On the public WDBC benchmark, accuracy is 82.34% ± 6.35% at ε = 0.5, 89.02% ± 3.49% at ε = 1 and 92.55% ± 1.21% at ε = 4. The matched nonprivate baseline is 92.31%. The lower budget settings exhibit a larger utility cost on the smaller training cohort because local Gaussian scale is inversely proportional to institutional sample count. The small mean difference above the nonprivate baseline at ε = 4 is compatible with random perturbation variation and is not evidence that blockchain improves classification. No superiority claim is made from that difference.

Figure 3 Privacy utility curves. Error bars show one sample standard deviation across 20 noise and partition repetitions on a fixed test split. Ledger auditing and unaudited private learning share the same numerical mechanism.

Figure 4 Accuracy over 80 communication rounds in the preselected seed zero runs. These are representative trajectories, not averages or an early stopping criterion.


7.2 Class specific behaviour


Classwise results reveal a limitation hidden by a single aggregate score. In the ε = 4 wearable seed zero run, Normal and Severe recall are both 95.33%, while Mild and Moderate recall are 31.33% and 30.67%. These surrogate middle classes frequently overlap with the extremes under the chosen generator, public transform, regularisation and short optimiser. The result identifies a statistical modelling weakness that cryptographic governance does not repair. Expanding the model or changing the training configuration would require a fresh evaluation with a fixed privacy policy.

The public WDBC seed zero matrix records 47 correctly classified malignant and 87 correctly classified benign observations out of 143 total. Malignant recall is 88.68% and benign recall is 96.67% for that run. These figures are conditional on one small public test split and should not be interpreted as validated sensitivity for a healthcare deployment. The matrix is presented to make the errors visible and to keep the narrative tied to the actual measurements.

Figure 5 Raw confusion matrix counts for ε = 4 in the preselected seed zero runs. Colour intensity indicates row normalized recall. Wearable labels are synthetic severity categories and WDBC is a public benchmark.


7.3 Effect of the auditing layer


Across the 20 paired ε = 4 wearable runs, enabling the signed ledger audit hook yields exactly the same final numerical model as disabling it under the same noise draws. The largest observed difference between the reported update and an independently recomputed weighted average is 4.44e-16, below the 10⁻¹² verification threshold. Each completed run emits 560 ledger events: 240 reservations, 240 submissions and 80 aggregate receipts. Thus the benign utility result is a consequence of auditing a fixed computation, not a separate training gain.

The paired check supplies an ablation for the governance layer: its signatures, commitments and accounting do not perturb the optimiser. It does not test availability under late institutions or consensus stalls. A production federation that rejects or loses a participant changes the accepted aggregation roster and can change utility even when all protected updates are valid. Such cases need a separate participation policy and an accountant that retains the cost of every already disclosed output.


7.4 Protocol faults and privacy accounting attacks


Table 5 Mechanical fault injection results with a signed poisoning negative control

Injected condition | Trials | Rejected | Rejection rate %

Changed protected payload | 1000 | 1000 | 100.00

Replayed accepted receipt | 1000 | 1000 | 100.00

Stale parent model | 1000 | 1000 | 100.00

Corrupted client signature | 1000 | 1000 | 100.00

Revoked institutional authorization | 1000 | 1000 | 100.00

Privacy budget overspend | 1000 | 1000 | 100.00

Refund after a possible release | 1000 | 1000 | 100.00

Changed weighted aggregate | 1000 | 1000 | 100.00

Validly signed poisoned model | 1000 | 0 | 0.00

All 8,000 injected protocol faults are rejected by the relevant implemented predicate. This outcome follows from explicit signature, commitment, version, authorization, budget or aggregation checks. It is a coverage result for those defined test mutations, not an empirical proof of cryptographic security against every attacker. All 100 contention pairs admit exactly one reservation and leave the charged total at the cap. The emulator’s process lock enforces the serialization in this test. A deployment must obtain the corresponding ordering and state validation property from its distributed ledger.

The refund illustration exposes the accounting failure directly. A controller that permits a protected release and then returns its ρ = 0.01 charge records a zero balance after each abort, yet 30 fresh releases incur a total actual cost of ρ = 0.30. BAPFL admits ten such charged attempts under the ρ = 0.10 cap and rejects subsequent reservations. Even an aborted update remains charged. This experiment illustrates the reservation invariant without pretending to reproduce an attack against a particular published blockchain framework.

The signed poisoning negative control is accepted in all 1,000 trials. The attacker supplies a model with arbitrary large finite coordinates, then signs its matching commitment with an authorized fixture key. The prototype correctly establishes the origin and consistency of that payload, but has no independent statistical criterion for rejecting it. Similarly, it cannot infer from a receipt alone whether an institution clipped every record or sampled the declared noise distribution. These results delimit the governance contribution and the honest endpoint assumption in the privacy theorem.

Figure 6 Left, rejection rates for eight specified protocol faults and the signed poisoning negative control. Right, actual disclosure under irreversible reservation compared with a release then refund counter in the constructed accounting illustration.


7.5 Client count and partition sensitivity


Table 6 Wearable client count experiment at ε = 4 with ten repetitions per cell

Institutions K | Dirichlet α | Accuracy % | Macro F1 %

3 | 0.20 | 62.75 ± 0.33 | 58.11 ± 0.47

3 | 1.00 | 62.75 ± 0.33 | 58.11 ± 0.47

3 | 10.00 | 62.75 ± 0.33 | 58.11 ± 0.47

6 | 0.20 | 62.69 ± 0.34 | 58.12 ± 0.56

6 | 1.00 | 62.69 ± 0.34 | 58.12 ± 0.56

6 | 10.00 | 62.69 ± 0.34 | 58.12 ± 0.56

10 | 0.20 | 62.41 ± 0.40 | 57.66 ± 0.66

10 | 1.00 | 62.41 ± 0.40 | 57.66 ± 0.66

10 | 10.00 | 62.41 ± 0.40 | 57.66 ± 0.66

At a fixed client count and matched random seeds, all three Dirichlet settings yield the same numerical aggregate to displayed precision. This is predicted by the weighted full batch identity in Section 5.4. Increasing K from 3 to 10 changes mean accuracy from 62.75% to 62.41% in this separate ten seed experiment and increases the aggregate noise variance factor from 3 to 10 for fixed N. The label skew invariance is restricted to the one local step, complete participation configuration. Reporting it as general robustness to non IID healthcare data would overstate the experiment.


7.6 Local costs and storage


Table 7 Local emulator operation timings across 1,000 repetitions with hosted environment variability

Operation | Median ms | 95th percentile ms

Reserve and certify | 0.117 | 0.210

Sign receipt | 0.048 | 0.091

Verify and certify submission | 0.224 | 0.415

Verify payload commitment | 0.009 | 0.060

The canonical signed receipt in the timing fixture occupies 473 bytes. A four class, 17 feature float64 local model occupies 576 bytes, so eliminating a full model from a small ledger entry produces only a modest payload difference before certificates and transaction overhead are considered. At 10,000 features the model payload is 320,032 bytes, while the comparable receipt fixture remains 473 bytes. The receipt only reduction is then 99.85%. This calculation excludes quorum signatures, hash linked block envelopes, reservations and aggregate events, and therefore is not a measurement of overall blockchain storage reduction.

The local timings show the cost of serialization, hashing, Ed25519 signing, signature verification and the emulator’s certificates. Their variation reflects the hosted execution environment. They do not establish network throughput, block finality latency, energy efficiency or Byzantine fault tolerance. Those measurements must be obtained from a deployed ordering service and institutional network configuration. The present prototype supplies an executable boundary for the accounting and validation logic rather than a substitute for such a deployment.

Figure 7 Left, measured local cryptographic operation cost. Right, a dense four class float64 model payload compared with the fixed signed receipt fixture. Receipt size excludes full blockchain transaction and certificate overhead.


8 Limitations and Deployment Considerations


The study’s strongest evidence concerns the specified protocol lifecycle and its mathematical accounting. The wearable benchmark is wholly synthetic, and the WDBC exercise is a single public cohort with one fixed test split. Neither is a multi institution clinical validation. The low recall of intermediate wearable classes is an explicit statistical limitation. An institution considering this design would need representative prospective data, outcome definitions, calibrated predictions, subgroup analysis and an external assessment of whether the model supports its intended use. The present results do not establish clinical effectiveness.

The learner is a one local step full batch model, with conservative Gaussian composition and no subsampling amplification. This choice makes the privacy accounting transparent but does not explore modern deep models, multiple local epochs or communication constrained devices. A more capable learner might improve the synthetic middle class results, while privacy amplification or a tighter accountant could improve small cohort utility. Each modification must preserve the release gate and account for every new data dependent output. The fixed settings here should not be silently reused as a general optimum.

The permissioned ledger implementation is a single process emulator. Its three validator signatures are fixture certificates, and the contention tests use a process lock. It does not evaluate consensus networking, replica disagreement, leader replacement, validator key compromise, durability after crashes or finality under a network partition. Hyperledger Fabric provides an appropriate implementation route [12, 13], but the proposed deployment has not been benchmarked. Persisting the budget scope across restarts and across multiple jobs is essential; restarting a client with a fresh local counter must not reset disclosure history.

Trust in the local training endpoint remains material. A smart contract can enforce a declared cost and validate a commitment, yet it cannot directly verify correct noise generation from an opaque model hash. A compromised institution can sign an unnoised or poisoned payload. Trusted execution attestation or a carefully designed proof system could address parts of that problem, but neither is implemented or claimed here. Secure aggregation would change which auditors can see protected local models and would need a compatible proof of aggregate correctness. These are concrete extensions rather than assumed capabilities.

Irreversible reservation sacrifices some available budget when an attempt fails before disclosure. That conservative behaviour is intentional and visible. It prevents the accounting error in the constructed refund example but does not eliminate denial of service through wasted reservations. An institution should authenticate reservation requests, limit request rates and use stable job scopes. Patient level revocation, retention, cohort enrollment privacy and model unlearning remain separate from the public institutional authorization epoch.

The contribution is the explicit joint construction of an irreversible reservation lifecycle, a full transcript Gaussian accountant and a version bound aggregation audit. Existing work already studies budget contracts, privacy mechanisms and blockchain verification [8–11]. The targeted literature review supports this positioning but does not prove an exhaustive global priority claim. A deployment study and broader prior art review are needed before treating the proposed integration as a fully validated production system or making stronger novelty claims.


9 Conclusion


BAPFL integrates permissioned blockchain governance with differentially private federated healthcare learning through a precise disclosure lifecycle. A protected local model is tied to an institution, authorization epoch, parent model and irreversible privacy reservation. Proper gradient clipping and Gaussian perturbation occur before every shared update, and the complete ideal mechanism transcript is bounded through zero concentrated differential privacy. Independent aggregation verification provides evidence that the anchored global model corresponds to the committed protected update set.

The controlled evaluation separates privacy, utility and protocol integrity. At ε = 4 and δ = 10⁻⁵, mean accuracy is 62.86% on the synthetic wearable surrogate and 92.55% on the public WDBC benchmark across 20 repetitions. The audit hook preserves final models exactly in paired executions. Eight specified protocol faults are rejected in 1,000 trials each, while a correctly signed poisoning negative control remains accepted. That negative result is part of the design boundary: provenance and budget accounting do not certify correct statistical behaviour.

The new protocol supplies executable evidence for charging before disclosure and retaining the charge after abort or rejection. The next substantive steps are implementation on a distributed permissioned ledger, verification of durable budget state, integration with endpoint attestation or compatible secure aggregation, and prospective multi institution clinical evaluation. Those steps would test the assumptions that are explicit in the present protocol analysis.


Data and Code Availability


The reproduction package includes the synthetic data generator, the public benchmark loader, utility experiments, signed ledger emulator, fault injection tests, raw results and vector figure sources. The wearable data are generated entirely from disclosed distributions and seeds. The public WDBC dataset is available from the UCI repository under its stated CC BY 4.0 license [17]. Benchmark keys and random seeds are reproducibility fixtures and must be replaced by fresh protected randomness for any deployment involving confidential records.


References


[1] H. B. McMahan, E. Moore, D. Ramage, S. Hampson and B. A. y Arcas, Communication Efficient Learning of Deep Networks from Decentralized Data, Proceedings of AISTATS, PMLR 54, pp. 1273–1282, 2017. https://proceedings.mlr.press/v54/mcmahan17a.html

[2] N. Rieke et al., The future of digital health with federated learning, npj Digital Medicine 3, article 119, 2020. https://doi.org/10.1038/s41746-020-00323-1

[3] C. Dwork and A. Roth, The Algorithmic Foundations of Differential Privacy, Foundations and Trends in Theoretical Computer Science 9(3–4), pp. 211–487, 2014. https://doi.org/10.1561/0400000042

[4] M. Abadi et al., Deep Learning with Differential Privacy, Proceedings of the ACM Conference on Computer and Communications Security, 2016. https://arxiv.org/abs/1607.00133

[5] M. Bun and T. Steinke, Concentrated Differential Privacy Simplifications Extensions and Lower Bounds, Theory of Cryptography Conference, 2016. https://arxiv.org/abs/1605.02065

[6] I. Mironov, Rényi Differential Privacy, IEEE Computer Security Foundations Symposium, 2017. https://arxiv.org/abs/1702.07476

[7] R. Rogers, A. Roth, J. Ullman and S. Vadhan, Privacy Odometers and Filters Pay as You Go Composition, Advances in Neural Information Processing Systems 29, 2016. https://arxiv.org/abs/1605.08294

[8] H. Kim, J. Park, M. Bennis and S. L. Kim, Blockchained On Device Federated Learning, IEEE Communications Letters, 2019. https://doi.org/10.1109/LCOMM.2019.2921755

[9] M. Shayan, C. Fung, C. J. M. Yoon and I. Beschastnikh, Biscotti A Blockchain System for Private and Secure Federated Learning, IEEE Transactions on Parallel and Distributed Systems 32(7), pp. 1513–1525, 2021. https://doi.org/10.1109/TPDS.2020.3044223

[10] S. De Chaudhury et al., Blockchain Based Secure Federated Learning With Local Differential Privacy and Incentivization, IEEE Transactions on Privacy 1, pp. 31–44, 2024. https://doi.org/10.1109/TP.2024.3487819

[11] W. Jia and T. Xie, BE DPFL A Blockchain Enhanced Privacy Preserving Federated Learning Framework for Secure Edge Network Collaboration, Applied Sciences 16(4), article 1791, 2026. https://doi.org/10.3390/app16041791

[12] E. Androulaki et al., Hyperledger Fabric A Distributed Operating System for Permissioned Blockchains, Proceedings of EuroSys, 2018. https://arxiv.org/abs/1801.10228

[13] Hyperledger Fabric, The Ordering Service, official documentation, accessed 13 October 2026. https://hyperledger-fabric.readthedocs.io/en/latest/orderer/ordering_service.html

[14] K. Bonawitz et al., Practical Secure Aggregation for Privacy Preserving Machine Learning, Proceedings of the ACM Conference on Computer and Communications Security, 2017. https://research.google/pubs/practical-secure-aggregation-for-privacy-preserving-machine-learning/

[15] L. Zhu, Z. Liu and S. Han, Deep Leakage from Gradients, Advances in Neural Information Processing Systems 32, 2019. https://arxiv.org/abs/1906.08935

[16] E. Bagdasaryan, A. Veit, Y. Hua, D. Estrin and V. Shmatikov, How To Backdoor Federated Learning, Proceedings of AISTATS, PMLR 108, pp. 2938–2948, 2020. https://proceedings.mlr.press/v108/bagdasaryan20a.html

[17] UCI Machine Learning Repository, Breast Cancer Wisconsin Diagnostic, dataset, 1993. https://doi.org/10.24432/C5DW2B

[18] S. Josefsson and I. Liusvaara, Edwards Curve Digital Signature Algorithm EdDSA, RFC 8032, 2017. https://doi.org/10.17487/RFC8032

[19] A. Singh, Anurag and B. K. Chaurasia, Federated Learning with Differential Privacy for Medical Data Analysis, manuscript supplied for this study, undated.

[20] K. Chaudhuri, C. Monteleoni and A. D. Sarwate, Differentially Private Empirical Risk Minimization, Journal of Machine Learning Research 12, pp. 1069–1109, 2011. https://jmlr.org/papers/v12/chaudhuri11a.html


Appendix A Reproduction and Public Transformation Constants


All runs use a fixed dataset generation seed of 20261013 for the wearable surrogate and a stratified split seed of 77. The 20 primary partition seeds are 1000 through 1019, with noise seeds 5000 through 5019. The sensitivity grid uses partition seeds 9000 through 9009 and noise seeds 10000 through 10009. Public input values are centred and scaled, bounded componentwise to [−3, 3], augmented with a bias coordinate and projected to unit Euclidean norm. The constants below are engineering choices declared in the experiment, not estimated medical reference intervals.

Table 8 Fixed surrogate transformation constants in generator units

Surrogate input | Public centre | Public scale

Heart rate | 85 | 20

Oxygen saturation | 95 | 4

Systolic pressure | 128 | 25

Diastolic pressure | 80 | 12

Glucose | 120 | 40

Temperature | 37.1 | 0.6

Respiratory rate | 18 | 4

Activity | 52 | 22

Sleep | 6.8 | 1.5

Stress | 4.4 | 2.5

Heart rate variability | 50 | 20

Steps | 5900 | 2600

Calories | 1830 | 400

Heart rate divided by stress plus one | 23 | 20

Oxygen deficit | 5 | 4

Pressure difference | 48 | 18

Vital risk index | 2.25 | 2

For WDBC, the 30 public scale upper values, in scikit learn feature order, are 20, 30, 140, 1200, 0.15, 0.30, 0.40, 0.20, 0.30, 0.12, 3, 4, 20, 400, 0.03, 0.10, 0.10, 0.05, 0.06, 0.03, 30, 40, 200, 2000, 0.20, 0.70, 0.80, 0.30, 0.50 and 0.20. Each feature uses half its stated upper value as both centre and scale before the common component bound and norm projection. These are disclosed algorithm settings rather than statistics computed from protected training records.

Software versions and execution commands are provided in the package README.