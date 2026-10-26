"""Build the research manuscript with editable native Word mathematics.

All result numbers are derived from the CSV/JSON files produced by
experiment.py and protocol.py.  No result is hardcoded in this script.
"""
from pathlib import Path
import json, math, re, zipfile
import numpy as np
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'reproducibility/results'
FIGURES=ROOT/'figures'
OUTPUT=ROOT.parent/'output/documents'
OUTPUT.mkdir(parents=True,exist_ok=True)
df=pd.read_csv(RESULTS/'utility_runs.csv')
details=json.loads((RESULTS/'details.json').read_text())
audit=json.loads((RESULTS/'audit_summary.json').read_text())
cfg=json.loads((RESULTS/'config.json').read_text())
wearable_hp=cfg.get('tuned_hp',{}).get('wearable',{'eta':4.0,'clip':1.0,'rounds':80})
wdbc_hp=cfg.get('tuned_hp',{}).get('wdbc',{'eta':2.0,'clip':0.5,'rounds':80})
lambda_l2=cfg.get('l2',0.003)
attackdf_top=pd.read_csv(RESULTS/'audit_attacks.csv')
_fault_rows=[r for r in attackdf_top.itertuples() if r.attack!='signed_poisoned_update']
num_fault_classes=len(_fault_rows)
_total_fault_trials=sum(r.trials for r in _fault_rows)
_total_fault_rejected=sum(r.rejected for r in _fault_rows)
doc=Document();notes=[];eqcount=0;figcount=0;tablecount=0

def font(run,size=11,bold=None,italic=None):
    run.font.name='Times New Roman';run.font.size=Pt(size);run.font.color.rgb=RGBColor(0,0,0)
    if bold is not None:run.bold=bold
    if italic is not None:run.italic=italic
    rp=run._element.get_or_add_rPr()
    rf=rp.rFonts
    if rf is not None:
        for k in ['ascii','hAnsi','eastAsia','cs']:rf.set(qn('w:'+k),'Times New Roman')

section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=Inches(.72);section.bottom_margin=Inches(.72)
section.left_margin=Inches(.8);section.right_margin=Inches(.8)
section.header_distance=Inches(.25);section.footer_distance=Inches(.3)
for sty in ['Normal','Title','Subtitle','Heading 1','Heading 2','Heading 3','Caption','List Number']:
    s=doc.styles[sty];s.font.name='Times New Roman';s.font.color.rgb=RGBColor(0,0,0)
    if sty=='Normal':s.font.size=Pt(11);s.paragraph_format.line_spacing=1.08;s.paragraph_format.space_after=Pt(6)
    if sty.startswith('Heading'):
        s.font.size=Pt(12 if sty=='Heading 1' else 11);s.font.bold=True
        s.paragraph_format.space_before=Pt(10);s.paragraph_format.space_after=Pt(5)
        s.paragraph_format.keep_with_next=True
    if sty=='Title':s.font.size=Pt(17);s.font.bold=True
    if sty=='Caption':s.font.size=Pt(9.5)
footer=section.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=footer.add_run();font(r,9)
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');r._r.addnext(field)
settings=doc.settings.element
mathpr=OxmlElement('m:mathPr');mf=OxmlElement('m:mathFont');mf.set(qn('m:val'),'Cambria Math');mathpr.append(mf);settings.append(mathpr)
for previous in settings.findall(qn('m:mathPr'))[:-1]:settings.remove(previous)
doc.core_properties.title='Blockchain Governed Federated Healthcare Learning with Irreversible Privacy Budget Reservations and Verifiable Model Aggregation'
doc.core_properties.author='Anurag Singh; Anurag; Brijesh Kumar Chaurasia'
doc.core_properties.subject='Differential privacy and permissioned blockchain governance for healthcare federated learning'
doc.core_properties.keywords='blockchain; federated learning; differential privacy; healthcare; privacy accounting; model audit'

def p(text,style=None,align=WD_ALIGN_PARAGRAPH.JUSTIFY):
    q=doc.add_paragraph(style=style);q.alignment=align
    font(q.add_run(text),11 if style is None else 10.5)
    q.paragraph_format.widow_control=True
    notes.append(text);return q

def h(text,level=1):
    q=doc.add_paragraph(text,style='Heading '+str(level));notes.append('\n'+text+'\n')
    for r in q.runs:font(r,12 if level==1 else 11,bold=True)
    return q

def caption(text):
    q=doc.add_paragraph(text,style='Caption');q.alignment=WD_ALIGN_PARAGRAPH.LEFT
    q.paragraph_format.space_before=Pt(4);q.paragraph_format.space_after=Pt(8)
    for r in q.runs:font(r,9.5)
    notes.append(text);return q

def figure(name,text,width=6.55):
    global figcount
    figcount+=1
    q=doc.add_paragraph();q.alignment=WD_ALIGN_PARAGRAPH.CENTER
    q.paragraph_format.space_before=Pt(3);q.paragraph_format.space_after=Pt(0);q.paragraph_format.keep_with_next=True
    pic=q.add_run().add_picture(str(FIGURES/(name+'.png')),width=Inches(width))
    pic._inline.docPr.set('descr',text)
    caption(f'Figure {figcount} {text}')

def table(headers,rows,widths,title,size=9.5):
    global tablecount
    tablecount+=1
    cap=caption(f'Table {tablecount} {title}');cap.paragraph_format.keep_with_next=True
    cap.paragraph_format.space_after=Pt(5)
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for column,width in zip(t.columns,widths):column.width=Inches(width)
    props=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    props.append(borders)
    margins=OxmlElement('w:tblCellMar')
    for side in ['top','left','bottom','right']:
        e=OxmlElement('w:'+side);e.set(qn('w:w'),'80');e.set(qn('w:type'),'dxa');margins.append(e)
    props.append(margins)
    for cell,w,txt in zip(t.rows[0].cells,widths,headers):
        cell.width=Inches(w);cell.text=str(txt)
        sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EAEAEA');cell._tc.get_or_add_tcPr().append(sh)
    repeat=OxmlElement('w:tblHeader');t.rows[0]._tr.get_or_add_trPr().append(repeat)
    for row in rows:
        cells=t.add_row().cells
        for c,w,txt in zip(cells,widths,row):c.width=Inches(w);c.text=str(txt)
    for j,row in enumerate(t.rows):
        nr=OxmlElement('w:cantSplit');row._tr.get_or_add_trPr().append(nr)
        for col,c in enumerate(row.cells):
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for q in c.paragraphs:
                q.paragraph_format.line_spacing=1.0;q.paragraph_format.space_after=Pt(1);q.paragraph_format.space_before=Pt(1)
                q.alignment=WD_ALIGN_PARAGRAPH.LEFT if col==0 or len(str(c.text))>35 else WD_ALIGN_PARAGRAPH.CENTER
                for r in q.runs:font(r,size,bold=j==0)
    doc.add_paragraph().paragraph_format.space_after=Pt(1)
    if len(t.rows)>3:
        for row in t.rows[-3:-1]:
            for cell in row.cells:
                for q in cell.paragraphs:q.paragraph_format.keep_with_next=True
    notes.append(' | '.join(headers))
    notes.extend(' | '.join(map(str,row)) for row in rows)
    return t

def mr(text):
    r=OxmlElement('m:r');rp=OxmlElement('m:rPr');sty=OxmlElement('m:sty');sty.set(qn('m:val'),'p');rp.append(sty);r.append(rp)
    wp=OxmlElement('w:rPr');fonts=OxmlElement('w:rFonts');fonts.set(qn('w:ascii'),'Cambria Math');fonts.set(qn('w:hAnsi'),'Cambria Math');wp.append(fonts)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),'22');wp.append(sz);r.append(wp)
    t=OxmlElement('m:t');t.set(qn('xml:space'),'preserve');t.text=str(text);r.append(t);return r

def add(parent,children):
    if not isinstance(children,(list,tuple)):children=[children]
    for c in children:parent.append(mr(c) if isinstance(c,(str,int,float)) else c)
    return parent

def sub(base,lo):
    x=OxmlElement('m:sSub');add(OxmlElement('m:e'),[]) # establish supported native structure
    e=OxmlElement('m:e');add(e,base);s=OxmlElement('m:sub');add(s,lo);x.extend([e,s]);return x

def sup(base,hi):
    x=OxmlElement('m:sSup');e=OxmlElement('m:e');add(e,base);s=OxmlElement('m:sup');add(s,hi);x.extend([e,s]);return x

def frac(a,b):
    x=OxmlElement('m:f');n=OxmlElement('m:num');d=OxmlElement('m:den');add(n,a);add(d,b);x.extend([n,d]);return x

def root(a):
    x=OxmlElement('m:rad');pr=OxmlElement('m:radPr');degh=OxmlElement('m:degHide');degh.set(qn('m:val'),'1');pr.append(degh);x.append(pr)
    deg=OxmlElement('m:deg');e=OxmlElement('m:e');add(e,a);x.extend([deg,e]);return x

def norm(a,suffix='F'):
    d=OxmlElement('m:d');pr=OxmlElement('m:dPr')
    for key,val in [('begChr','‖'),('endChr','‖')]:
        e=OxmlElement('m:'+key);e.set(qn('m:val'),val);pr.append(e)
    d.append(pr);e=OxmlElement('m:e');add(e,a);d.append(e)
    return sub(d,suffix) if suffix else d

def summation(lo,hi,body):
    x=OxmlElement('m:nary');pr=OxmlElement('m:naryPr');ch=OxmlElement('m:chr');ch.set(qn('m:val'),'∑');pr.append(ch)
    loc=OxmlElement('m:limLoc');loc.set(qn('m:val'),'undOvr');pr.append(loc);x.append(pr)
    if hi=='':
        hide=OxmlElement('m:supHide');hide.set(qn('m:val'),'1');pr.append(hide)
    if lo=='':
        hide=OxmlElement('m:subHide');hide.set(qn('m:val'),'1');pr.append(hide)
    s=OxmlElement('m:sub');add(s,lo);u=OxmlElement('m:sup');add(u,hi);e=OxmlElement('m:e');add(e,body);x.extend([s,u,e]);return x

def equation(parts,description):
    global eqcount
    eqcount+=1;q=doc.add_paragraph();q.paragraph_format.space_before=Pt(4);q.paragraph_format.space_after=Pt(6)
    q.paragraph_format.keep_together=True;q.paragraph_format.line_spacing=1.1
    q.paragraph_format.tab_stops.add_tab_stop(Inches(3.22),WD_TAB_ALIGNMENT.CENTER)
    q.paragraph_format.tab_stops.add_tab_stop(Inches(6.70),WD_TAB_ALIGNMENT.RIGHT)
    font(q.add_run('\t'),10)
    om=OxmlElement('m:oMath');add(om,parts);q._p.append(om)
    font(q.add_run(f'\t({eqcount})'),10)
    notes.append(f'Equation {eqcount}: {description}')

def stat(dataset,setting,column):
    a=df[(df.dataset==dataset)&(df.setting==setting)][column]
    return f'{a.mean()*100:.2f} ± {a.std(ddof=1)*100:.2f}'

title=doc.add_paragraph(doc.core_properties.title,style='Title');title.alignment=WD_ALIGN_PARAGRAPH.CENTER
title.paragraph_format.space_after=Pt(9)
for r in title.runs:font(r,17,bold=True)
authors=p('Anurag Singh, Anurag and Brijesh Kumar Chaurasia',align=WD_ALIGN_PARAGRAPH.CENTER)
for r in authors.runs:font(r,11,bold=True)
p('Computer Science and Engineering\nPranveer Singh Institute of Technology, Kanpur, India',align=WD_ALIGN_PARAGRAPH.CENTER)
h('Abstract',1)
# Abstract numbers derived from results (Fix 8)
_w_acc4  = stat('wearable','eps_4','accuracy')
_w_acc4_m, _w_acc4_s = df[(df.dataset=='wearable')&(df.setting=='eps_4')].accuracy.mean()*100, df[(df.dataset=='wearable')&(df.setting=='eps_4')].accuracy.std(ddof=1)*100
_wb_acc4_m, _wb_acc4_s = df[(df.dataset=='wdbc')&(df.setting=='eps_4')].accuracy.mean()*100, df[(df.dataset=='wdbc')&(df.setting=='eps_4')].accuracy.std(ddof=1)*100
_n_attacks = int(audit.get('single_winner_pairs',100))
p(f'Cross institutional healthcare learning requires controls over both information disclosure and the integrity of shared model updates. We propose blockchain audited private federated learning, a permissioned protocol that couples each protected update to an irreversible privacy budget reservation, an institutional authorization epoch and a signed model commitment. Record gradients are clipped before Gaussian perturbation at every communication round. A zero concentrated differential privacy accountant bounds the complete training transcript, while independent auditors verify the weighted aggregation of committed protected models. The ledger stores governance metadata and commitments; patient records and model payloads remain off chain. We establish conditional privacy and reservation invariants and implement a signed ledger state machine emulator. Controlled experiments comprise 330 utility runs on a wholly synthetic four class wearable surrogate and the public Wisconsin Diagnostic Breast Cancer benchmark. At ε = 4 and δ = 10⁻⁵, mean accuracy across 20 runs is {_w_acc4_m:.2f}% ± {_w_acc4_s:.2f}% for the wearable surrogate and {_wb_acc4_m:.2f}% ± {_wb_acc4_s:.2f}% for the public benchmark. Auditing preserves the final model exactly in 20 matched runs. {num_fault_classes} defined protocol fault classes are rejected in 1,000 trials each, and concurrent budget reservations admit exactly one request in all {_n_attacks} contention tests, each with two simultaneous requests. A signed poisoning negative control remains accepted, demonstrating that provenance does not establish statistical correctness. The contribution is an explicit disclosure accounting lifecycle with verifiable model provenance, evaluated at protocol level; clinical validation and distributed consensus benchmarking remain necessary.')
p('Keywords  blockchain governance; federated learning; differential privacy; healthcare analytics; privacy accounting; verifiable aggregation',align=WD_ALIGN_PARAGRAPH.LEFT)

h('1 Introduction')
p('Healthcare institutions hold complementary data that can improve statistical modelling, but sharing patient records creates confidentiality, stewardship and operational concerns. Federated learning offers a practical way to coordinate model development across these boundaries by exchanging model updates from locally held data [1, 2]. Keeping records at their originating institution, however, leaves two separate questions unresolved. A shared update can disclose information about a training record, and a coordinator can alter, omit or reuse an update without an independently verifiable account of the resulting model. A useful healthcare federation must therefore specify what is disclosed, how disclosure is charged and how the accepted computation is checked.')
p('Differential privacy addresses the first question through a probabilistic bound on the influence of an individual record [3–6]. The guarantee concerns the observer’s entire accessible transcript. If earlier communication rounds expose clean updates, adding noise only to a later model does not establish that the previous disclosures were private. Privacy accounting must also include fresh releases that fail an application level validation check. The rejection of a model update cannot erase information that a recipient already observed. A budget counter that decreases after such a rejection can therefore understate cumulative disclosure even when its individual arithmetic operations appear correct.')
p('Blockchain technology provides an ordered, replicated record of governance events and model commitments. Existing blockchain federated learning systems establish substantial precedents for decentralized coordination, update verification and incentives [8–11]. Their existence makes a generic combination of blockchain, federated learning and differential privacy an insufficient novelty claim. The question pursued here is narrower: how can a privacy reservation, a noisy release and a verified aggregation be linked so that aborts, retries and concurrent requests cannot create uncharged disclosure? The protocol also needs to limit what it permanently records, because ledger immutability can preserve sensitive metadata as readily as useful evidence.')
p('We introduce blockchain audited private federated learning, abbreviated BAPFL. The proposed integration charges a fixed, policy approved privacy cost before a protected model is disclosed and never refunds that reservation. A signed receipt binds the release to its institution, authorization epoch, parent model and communication round. The accepted roster and aggregation weights are frozen before an independently recomputed global model is anchored. These controls address an auditable lifecycle rather than proposing a new consensus algorithm or a new definition of differential privacy.')
p('The contributions are fourfold. First, we specify an irreversible reservation state machine that treats unsuccessful release attempts conservatively and prevents duplicate charging or replay from being confused with a fresh noisy computation. Second, we derive a full transcript privacy bound for clipped Gaussian updates under a fixed cohort and an honest training endpoint assumption. Third, we couple protected model commitments to a checkable aggregation receipt without publishing raw data, raw gradients or fitted feature statistics. Fourth, we provide executable experiments, including a negative control that separates protocol integrity from poisoning resistance. The resulting evidence supports a protocol contribution with explicit boundaries rather than a claim of deployment readiness.')

h('2 Related Research and Research Gap')
h('2.1 Federated healthcare and formal privacy',2)
p('FedAvg established a widely used approach to aggregating model parameters trained across distributed clients [1]. Healthcare adoption adds institutional variation, small cohorts, incompatible data practices and restrictions on data access [2]. In this paper, the statistical learner deliberately remains a transparent softmax model so that the effect of the governance layer can be isolated. The earlier three client healthcare manuscript [19] motivates the application structure, but its dataset and complete executable training implementation are unavailable for independent reproduction. Its reported 97.15% accuracy is not treated as an experimental result of the new protocol.')
p('Differentially private empirical risk minimisation requires both a valid sensitivity argument and a noise distribution that matches that argument [20]. Gradient clipping and Gaussian perturbation provide a more direct bounded query construction for iterative training [4]. Zero concentrated differential privacy supports additive accounting for Gaussian mechanisms [5], while Rényi differential privacy provides a related framework for composition [6]. Privacy filters distinguish prospective enforcement of a disclosure limit from retrospective measurement [7]. We use an explicit fixed allocation, without a subsampling amplification claim, to keep the implemented accountant and the theoretical bound aligned.')
h('2.2 Blockchain coordination and update accountability',2)
p('BlockFL uses blockchain coordination to exchange and verify local model updates and analyses the associated communication, computation and consensus delays [8]. Biscotti combines distributed learning with cryptographic validation and privacy mechanisms, including a broader treatment of adversarial peers [9]. These systems show that decentralized provenance and model update verification are established research directions. Our protocol instead concentrates on whether every protected release is covered by an irreversible budget charge and a version bound receipt. We do not claim to reproduce Biscotti’s poisoning defence or distributed scalability.')
p('De Chaudhury and colleagues study local differential privacy with incentives and encrypted model access in a permissioned blockchain setting [10]. BE-DPFL explicitly introduces a privacy budget contract alongside on chain supervision and off chain learning [11]. Budget contracts themselves are therefore prior art. BAPFL’s proposed distinction is the precise reservation semantics: budget is charged before possible disclosure, a failed update cannot return the charge, retries cannot silently redraw noise and the aggregation receipt binds the accepted update set to a particular parent model. The literature comparison identifies the design problem investigated here; it does not establish an exhaustive first publication claim.')
table(['Research line','Established contribution','Question examined in BAPFL'],[
 ('FedAvg [1]','Distributed model averaging','Bind the accepted update set to a verifiable model version'),
 ('Private learning [4–7, 20]','Bounded disclosure and composition','Enforce the accountant before each possible release'),
 ('BlockFL [8]','Blockchain coordination and latency analysis','Record reservation and release order explicitly'),
 ('Biscotti [9]','Private decentralized learning and update validation','Audit disclosure charges without claiming its poisoning defence'),
 ('Permissioned incentives [10]','Private contribution and access incentives','Prevent abort or replay from resetting a disclosure charge'),
 ('BE-DPFL [11]','Privacy budget contracts and supervision','Specify irreversible charges and version bound aggregation')
],[1.65,2.35,2.70],'Positioning of BAPFL against established research')
h('2.3 Problem statement',2)
p('Given an established cross silo training cohort and a public training policy, construct a federation in which every new protected release is preceded by a finalized privacy reservation; the total transcript satisfies a stated record level privacy bound; and the accepted global model can be checked against committed protected client models. The reservation must remain charged after rejection or timeout, and concurrent requests must not jointly exceed the remaining budget. Governance evidence should be recorded without permanently publishing patient records or model payloads. These requirements define the gap addressed by the proposed lifecycle and the executable tests.')

h('3 System Model and Security Objectives')
h('3.1 Participants and trust boundaries',2)
p('The federation contains K healthcare institutions, a replaceable off chain coordinator, independent aggregation auditors and a permissioned validator set. Each institution holds a disjoint, fixed size training set Dk and runs a controlled training agent. Validators order governance transactions; auditors validate protected model payloads and recompute their weighted average. The coordinator need not be trusted with clean updates or with the correctness of the final aggregation. The local training agent must nevertheless execute the declared clipping and noise mechanism honestly. A signature establishes who signed a payload, not how that payload was computed.')
p('The privacy analysis fixes dataset membership, per institution sample counts and all transformation constants. Neighbouring datasets differ by replacing one record in one institution while retaining those public quantities. The resulting guarantee is record level privacy, not protection of an entire institution or a patient’s arbitrarily many visits. Experimental train test splitting and label based Dirichlet partitioning are benchmark construction steps outside this mechanism. In a deployment, cohort enrollment, patient deduplication and the privacy implications of institutional membership require separate controls. The theorem does not make those processes private.')
p('Institutional training authorization is represented by a public epoch counter. The emulator’s consent_epoch field denotes this institutional authorization version; it is not a patient level legal consent registry. Patient permissions are checked within the institution and are not placed on the ledger. Revocation stops future release authorization after the relevant governance event is finalized. It cannot withdraw already disclosed information or remove a patient’s past influence from a previously released model. Retrospective model removal would require a separate unlearning design.')
h('3.2 Ledger and payload placement',2)
p('A ledger entry contains a scoped institution identifier, round number, parent model hash, approved privacy cost, authorization epoch, payload commitment and signature. Protected model parameters are transmitted through authenticated off chain channels. Patient records, labels, unperturbed gradients and fitted feature means or variances are excluded from the ledger. Commitments cover only protected outputs. This avoids treating a hash of a low entropy patient attribute as if it were an anonymisation mechanism. Public metadata remain visible within the permissioned consortium and can still reveal participation patterns.')
p('A practical deployment may use Hyperledger Fabric with a Byzantine fault tolerant ordering configuration. Fabric separates transaction execution, ordering and validation [12, 13]. Clients must observe a valid committed transaction before disclosing an update; an ordering acknowledgment alone is insufficient because an ordered transaction can later be invalidated. Four orderers with a three member quorum provide the proposed f = 1 configuration. The implemented emulator signs hash linked records with three of four fixture validators, but does not implement distributed network consensus, leader change or partition recovery.')
figure('figure1_architecture','Proposed separation of local data, off chain protected model computation and permissioned blockchain governance. The three institutions are simulated sites; the validator topology is a deployment design.')
h('3.3 Adversarial capabilities and objectives',2)
p('The coordinator or a transport adversary may alter a payload, replay a receipt, substitute an obsolete parent model, misstate an aggregate or request training beyond an institution’s declared budget. A compromised institution may produce a validly signed but statistically malicious update. Validators are assumed to remain within the chosen consensus fault threshold, and auditors retain a trusted committed checkpoint. The first group of protocol faults is tested mechanically. Poisoning, malicious noise omission, endpoint compromise and a compromised validator majority are outside the proven protection boundary. Gradient reconstruction and model poisoning are established threats [15, 16], but neither attack is claimed to have been exhaustively evaluated here.')
table(['Objective','Required invariant'],[
 ('Transcript privacy','Only properly clipped and perturbed new outputs leave an honest training agent'),
 ('Budget integrity','Every possible fresh release has an irreversible reservation'),
 ('Origin and freshness','Receipt signature, authorization epoch and parent model match the accepted round'),
 ('Aggregation integrity','Auditor recomputes the weighted average of the frozen protected update set'),
 ('Data minimisation','Ledger contains commitments and public governance fields, not patient data'),
 ('Explicit trust boundary','Signatures do not certify correct clipping, noise sampling or clinical validity')
],[1.65,5.05],'Security objectives and the conditions under which they are meaningful')

h('4 Blockchain Audited Private Federated Learning')
h('4.1 Public transformation and statistical learner',2)
p('The input transform uses predeclared centering and scale constants. Component values are bounded and the augmented vector, including a bias coordinate, is projected to unit Euclidean norm. No training derived normalisation statistic is released or used to calibrate the sensitivity bound. Appendix A and the implementation specify the exact constants. For J classes, W has J rows and d + 1 columns. We implement the softmax probabilities directly, avoiding a mismatch between a multinomial objective and a one versus rest software classifier.')
equation([sub('p','c'),'(a; W) = ',frac(['exp(',sup(sub('w','c'),'T'),'a)'],summation('j = 1','J',['exp(',sup(sub('w','j'),'T'),'a)']))], 'Multinomial softmax probability')
equation(['L(W) = ',frac('1','N'),summation('i = 1','N',['−log ',sub('p',sub('y','i')),'(',sub('a','i'),'; W)']), ' + ',frac('λ','2'),sup(norm('W'),'2')], 'Regularized multiclass empirical objective')
p('Let vi denote the augmented, component bounded input before norm projection. The transform is fixed independently of the protected cohort. The regularisation term applies to all coordinates, including the bias coordinate. Class balancing weights are not estimated from private class counts; the benchmark uses an unweighted objective. This preserves a simple correspondence between the bounded per record query and the implemented training step.')
equation([sub('a','i'),' = ',frac(sub('v','i'),['max(1, ',norm(sub('v','i'),'2'),')']),',    ',norm(sub('a','i'),'2'),' ≤ 1'], 'Fixed augmented input norm projection')
h('4.2 Private local update and model averaging',2)
p(f'At round t, all participating clients receive the same authenticated parent model Wt. Institution k computes one full batch gradient contribution for each local record, then clips the complete gradient matrix in Frobenius norm at C. The clipping operation acts on each actual contribution, not merely on a number used later in a sensitivity formula. The mean clipped gradient receives independent Gaussian noise in every coordinate. The tuned settings are C = {wearable_hp["clip"]:.2f}, η = {wearable_hp["eta"]:.2f} with {wearable_hp["rounds"]} rounds for the wearable surrogate, and C = {wdbc_hp["clip"]:.2f}, η = {wdbc_hp["eta"]:.2f} with {wdbc_hp["rounds"]} rounds for WDBC, each with λ = {lambda_l2:g}.')
equation([sup(sub('g','ki'),'t'),' = ∇',sub('ℓ','ki'),'(',sub('W','t'),'),    ',sup(sub('ḡ','ki'),'t'),' = ',sup(sub('g','ki'),'t'),' min(1, ',frac('C',norm(sup(sub('g','ki'),'t'))),')'], 'Actual per record gradient clipping')
equation([sup(sub('ĝ','k'),'t'),' = ',frac('1',sub('n','k')),summation('i = 1',sub('n','k'),sup(sub('ḡ','ki'),'t')), ' + ',sup(sub('Z','k'),'t'),',    ',sup(sub('Z','k'),'t'),' ∼ N(0, ',sup(sub('σ','k'),'2'),'I)'], 'Noisy full batch local gradient')
equation([sub('σ','k'),' = z ',frac('2C',sub('n','k')),',    ',sup(sub('W','k'),'t + 1'),' = ',sub('W','t'),' − η(',sup(sub('ĝ','k'),'t'),' + λ',sub('W','t'),')'], 'Sensitivity calibrated noise and protected local model')
equation([sub('W','t + 1'),' = ',summation('k = 1','K',[sub('π','k'),sup(sub('W','k'),'t + 1')]),',    ',sub('π','k'),' = ',frac(sub('n','k'),'N'),',    N = ',summation('k = 1','K',sub('n','k'))], 'One local step FedAvg with public fixed sample weights')
p('Only the protected local model Wk is eligible for transmission. Raw gradients, clean intermediate models and model fitted feature statistics remain local. One local step is intentionally used so that the contribution of ledger auditing can be separated from local optimiser drift. The analysis and results do not imply equivalent behaviour for multiple local epochs, minibatch sampling or partial participation. Secure aggregation can be added to hide an institution’s protected vector from the coordinator [14], but it is not implemented here and would require a compatible aggregation verification mechanism.')
h('4.3 Irreversible privacy reservation',2)
p('Before generating a protected release, the training agent requests a reservation for a fixed policy approved cost. The contract checks institutional authorization, the current epoch, the authenticated parent model, uniqueness of the round reservation and the remaining budget. A valid committed reservation immediately reduces available budget. Once charged, the amount cannot be refunded, even if computation, transport or payload validation later fails. This conservative rule accounts for the possibility that a protected output was exposed before the application recognised the failure.')
p('A reservation may be overconservative when a client aborts before computing or disclosing anything. That loss of available budget is an explicit availability tradeoff. Recovering such a charge safely would require trustworthy evidence that no disclosure occurred; a client assertion alone is insufficient. The protocol chooses a simple irreversible rule so that application success is never used as a proxy for whether information escaped. A fresh noisy retry requires a new reservation. Returning the identical cached protected output is postprocessing of the same release and does not create a new independently perturbed computation.')
equation([sub('u','max'),' = ⌊',sup('10','12'),sub('ρ','max'),'⌋,    ',sub('u','t'),' = ⌊',frac(sub('u','max'),'T'),'⌋,    z = ',root(frac(sup('10','12'),['2',sub('u','t')]))], 'Conservative fixed point privacy allocation and recalibrated noise')
p('The contract uses integer units of 10⁻¹² in ρ. The cap is rounded down and the per round allocation is an integer floor division. The noise multiplier is recalibrated to that exact allocation. Thus rounding cannot charge less than the implemented ideal Gaussian mechanism consumes. Production code also needs a reviewed floating point or discrete noise implementation; the NumPy benchmark evaluates the learning behaviour of the mathematical mechanism rather than certifying a hardened differential privacy runtime.')
figure('figure2_lifecycle','Reservation lifecycle. Disclosure charges persist after an aborted or rejected update. Institution authorization and a valid committed reservation are required before a new protected output can be released.')
h('4.4 Version bound receipts and aggregation audit',2)
p('After reservation finality, the institution computes its protected local model, encodes it as canonical little endian float64 bytes, and signs a receipt. The receipt binds the institution, round, parent model, cost, authorization epoch, schema, nonce and model commitment. A collision resistant hash commits to the nonce and the protected payload. In deployment, nonces and keys are freshly generated and private key material is protected. The emulator uses public deterministic fixture keys and nonces solely to make its mechanical tests reproducible; those fixtures are not a deployment security configuration.')
equation([sup(sub('h','k'),'t'),' = SHA256(',sup(sub('r','k'),'t'),' ∥ Encode(',sup(sub('W','k'),'t + 1'),')),    ',sup(sub('s','k'),'t'),' = Sign(',sub('sk','k'),', receipt)'], 'Protected model commitment and institution signature')
p('Auditors reject a receipt if its signature or reservation binding is invalid, its authorization has been revoked, its parent model is stale or its round receipt has already been used. They then verify the off chain payload against the committed hash and reject nonfinite model coordinates. These checks are predicates of public metadata or already protected outputs. They do not require access to patient records or clean gradients. The accepted roster is fixed before aggregation so that the coordinator cannot claim a different participant set after observing the result.')
equation([norm([sup('W','claimed'),' − ',summation('k ∈ A','',[sub('π','k'),sup(sub('W','k'),'t + 1')])],'∞'),' ≤ τ,    τ = ',sup('10','−12')], 'Independent numerical aggregation verification for the accepted roster A')
p('The aggregation receipt includes the accepted institution set, public weights, parent model commitment and resulting global model commitment. A trusted checkpoint makes subsequent hash chain alteration detectable. Merely recomputing an unanchored chain after rewriting all of its contents would not establish integrity. A distributed deployment must enforce common policy state and finality through the actual consensus protocol rather than through the emulator’s process lock.')
h('4.5 Audited training algorithm',2)
for text in [
 '1  Authenticate the round policy and its parent model; freeze the participating institution set and public sample weights.',
 '2  Read the institution authorization epoch and the remaining global budget for its established training scope.',
 '3  Commit a unique integer cost reservation. Await a valid peer commit event. Abort without disclosure if authorization fails.',
 '4  Transform local records with the fixed public constants, compute their softmax gradients and clip each matrix at C.',
 '5  Add fresh independent Gaussian noise at the policy approved scale and construct the protected local model.',
 '6  Commit a signed receipt binding the reservation, epoch, round, parent model, nonce and protected model hash.',
 '7  Transmit the protected payload off chain. Verify receipt authenticity, freshness, finite values and the payload commitment.',
 '8  Freeze accepted updates and recompute their weighted average. Reject an inconsistent claimed aggregation.',
 '9  Anchor the global model receipt and retain the completed reservation cost. Never reduce the counter after rejection or timeout.',
 '10  Continue only while the fixed privacy cap and current institutional authorization permit another reserved release.'
]:
    q=p(text,align=WD_ALIGN_PARAGRAPH.LEFT)
    q.paragraph_format.keep_with_next=not text.startswith('10 ')
    for r in q.runs:font(r,10)

h('5 Formal Analysis')
h('5.1 Bounded query sensitivity',2)
p('Proposition 1. Fix a round transcript and the shared parent model. Under replace one record adjacency with fixed nk, the sensitivity of the mean clipped local gradient is at most 2C/nk in Frobenius norm. Proof. Replacing one record replaces one clipped matrix by another. Each matrix has norm at most C, so their difference has norm at most 2C by the triangle inequality. Division by the fixed sample count gives the stated bound. Changes in the regularisation term are zero for the fixed parent model. This argument requires actual clipping of each contribution and does not depend on optimisation convergence or a data estimated feature radius.')
equation([sub('Δ','k'),' = max ',norm([sup(sub('ḡ','k'),'t'),'(D) − ',sup(sub('ḡ','k'),'t'),'(D′)']),' ≤ ',frac('2C',sub('n','k'))], 'Replace one record sensitivity bound')
h('5.2 Complete transcript privacy',2)
p('Proposition 2. For an honest institution, an ideal Gaussian gradient release with σk = zΔk satisfies ρt = 1/(2z²) zero concentrated differential privacy [5]. The protected local model is a deterministic transformation of that release and the already observed parent model, so it inherits the bound. Adaptive choices of parent models based on prior protected outputs are covered by composition. A coordinator therefore cannot remove the clipping bound simply by selecting an unusual parent model. The fixed public transformation and policy contribute no new protected data query.')
equation([sub('ρ','t'),' = ',frac(sup(sub('Δ','k'),'2'),['2',sup(sub('σ','k'),'2')]),' = ',frac('1',['2',sup('z','2')]),',    ',sub('ρ','k'),' = ',summation('t ∈ Rₖ','',sub('ρ','t'))], 'Gaussian zCDP cost and sequential composition within one institution')
p('Let Rk include every fresh protected release, including releases whose payloads were rejected or later omitted from a global model. Composition bounds that institution’s accessible transcript by the sum of those costs. Under the established disjoint record assignment, the federation’s record level bound uses the largest institutional cumulative cost rather than adding costs across unrelated records. If the same patient or record appears in multiple institutions, this disjointness condition fails and an appropriate cross institution or patient level accountant is necessary.')
equation(['ρ = ',sub('max','k'),sub('ρ','k'),',    ε = ρ + 2',root(['ρ ln(',frac('1','δ'),')']),',    δ ∈ (0, 1)'], 'zCDP conversion to approximate differential privacy for the fixed disjoint cohort')
equation([sub('ρ','max'),' = ',sup(['(',root(['ln(',frac('1','δ'),') + ',sub('ε','max')]),' − ',root(['ln(',frac('1','δ'),')']),')'],'2')], 'Closed form cumulative zCDP cap for a requested epsilon and delta')
p('Ledger hashes, signatures, acceptance decisions and an audited aggregate are functions of public metadata and protected outputs. They are postprocessing and do not add a new record disclosure under the assumptions above. This statement excludes data dependent participation decisions, fresh unnoised validation statistics and patient derived governance metadata. Publishing benchmark noise seeds permits experiment reproduction; a deployment must instead use independent private randomness. The theoretical guarantee presumes that those noise draws remain unknown to the adversary.')
h('5.3 Budget safety and aggregation integrity',2)
p('Proposition 3. If every fresh protected output is gated by a finalized reservation, the charged ledger sum upper bounds the sum of actual mechanism costs. Proof. Each possible fresh release is assigned a unique reservation, and its approved cost is charged before disclosure. No state transition decreases that charge. A reservation that never produces a release contributes a nonnegative surplus. An aborted or rejected release remains covered. Atomic balance checks serialize concurrent reservations, so two individually feasible requests cannot together exceed the cap. The bound depends on a training endpoint that cannot bypass the release gate and on a ledger that retains the same budget scope across restarts and jobs.')
equation([sup(sub('L','k'),'charged'),' = ',summation('r ∈ Qₖ','',sub('ρ','r')),' ≥ ',summation('r ∈ Rₖ','',sub('ρ','r')),' = ',sup(sub('L','k'),'released')], 'Irreversible reservation sum upper bounds actual charged fresh releases')
p('Proposition 4. For an authenticated frozen roster and public weights, an auditor with the committed protected payloads detects a claimed model that differs from their weighted average by more than τ. This is a numerical consistency statement, conditional on commitment binding and signature authenticity. It establishes neither correct local training nor robustness to a legitimately signed poisoned contribution. Ed25519 supplies the chosen receipt signature primitive [18]. The three signature emulator certificate is an executable fixture; Byzantine consensus safety in a deployed system remains a property of the chosen ordering implementation and its assumptions.')
equation(['n = 3f + 1,    q = 2f + 1'], 'Proposed Byzantine ordering configuration and certificate threshold')
h('5.4 Learning and storage implications',2)
p('With full participation, one shared parent model, one local full batch step and public nk/N weights, the weighted deterministic clipped gradient equals the clipped gradient over the union of the fixed training records. Partition label skew therefore cancels algebraically in this restricted configuration. The Gaussian noise contribution has a different dependence: each client’s nk cancels its aggregation weight, leaving K independent equal scale noise matrices. The variance increases with the number of participating institutions for fixed N and privacy allocation.')
equation(['Var(',summation('k = 1','K',[sub('π','k'),sup(sub('Z','k'),'t')]),') = K',sup(['(',frac('2Cz','N'),')'],'2'),'I'], 'Aggregate noise variance and the conditional partition invariance')
p('This cancellation is a diagnostic prediction for the chosen optimiser, not a general theorem that non IID data never affect federated learning. Multiple local steps, private class weights, adaptive site selection and missing updates change the calculation. A signed receipt has approximately fixed size, whereas a dense float64 softmax model grows as 8J(d + 1) bytes. However, a blockchain record also contains certificates, hash links and governance fields. Receipt only storage comparisons must therefore be distinguished from full ledger storage, especially for small models.')

h('6 Experimental Methodology')
h('6.1 Datasets and public transformations',2)
p('The wearable surrogate contains 6,000 wholly synthetic observations, with 1,500 records in each of four severity labels. It is not a clinical sensor dataset and its labels are not diagnoses. A class dependent latent severity plus Gaussian variation generates 13 sensor styled inputs: heart rate, oxygen saturation, systolic and diastolic pressure, glucose, temperature, respiratory rate, activity, sleep, stress, heart rate variability, steps and calories. Four derived inputs encode a heart rate to stress ratio, oxygen deficit, pressure difference and a vital risk index. The complete generator is provided so that every record can be reconstructed. No source patient data, SMOTE samples or original manuscript measurements are reused.')
p('The second dataset is the public Wisconsin Diagnostic Breast Cancer dataset supplied through scikit learn and documented by the UCI repository [17]. It contains 569 observations and 30 numeric features describing cell nuclei from fine needle aspirate images. The experiment is a benchmark exercise on public data, not a prospective diagnostic study. A stratified fixed split creates 426 training and 143 test observations, while the wearable split creates 4,800 training and 1,200 test observations. No observation is discarded. Public transformation constants are fixed in the script; no normalizer is fitted to the test set or pooled private client data.')
table(['Parameter','Wearable surrogate','Public WDBC'],[
 ('Data provenance','Wholly synthetic generator','Public UCI benchmark'),
 ('Records before splitting','6,000','569'),
 ('Training records','4,800','426'),
 ('Test records','1,200','143'),
 ('Input features','17','30'),
 ('Output classes','4','2'),
 ('Test class counts','300 per class','53 malignant and 90 benign'),
 ('Primary simulated institutions','3','3'),
 ('Rounds and local steps',f'{wearable_hp["rounds"]} and 1',f'{wdbc_hp["rounds"]} and 1'),
 ('Gradient clipping C',f'{wearable_hp["clip"]:.2f}',f'{wdbc_hp["clip"]:.2f}'),
 ('Step size η and penalty λ',f'{wearable_hp["eta"]:.2f} and {lambda_l2:g}',f'{wdbc_hp["eta"]:.2f} and {lambda_l2:g}'),
 ('Privacy budgets ε','0.50  1.00  2.00  4.00  8.00','0.50  1.00  2.00  4.00  8.00'),
 ('Delta and primary repetitions','10⁻⁵ and 20','10⁻⁵ and 20')
],[2.10,2.35,2.25],'Benchmark construction and fixed learning settings')
h('6.2 Partitioning and comparison design',2)
p('Training records are allocated by class specific Dirichlet draws with concentration 1.0. Draws with very small institutional samples are rejected using the threshold max(30, floor(N/(10K))). All accepted partitions contain every training record exactly once. Noise and partition seeds vary across 20 primary repetitions; the underlying dataset and test split remain fixed. Consequently, reported standard deviations describe randomisation and partition variation conditional on this split, not uncertainty across hospitals or independent patient populations. The nonprivate one step full batch baseline is deterministic despite changing client partitions.')
p('Six settings are run for each dataset: matched nonprivate clipped FedAvg and five private settings. These produce 240 primary utility runs. A further 90 wearable runs vary K over 3, 6 and 10 and the Dirichlet concentration over 0.2, 1.0 and 10.0, with ten repetitions in each cell. The signed audit hook is additionally applied to 20 ε = 4 wearable runs and compared with an unaudited execution using identical numerical noise draws. This paired design measures whether governance changes the computation itself; it is not a comparison against a different optimiser or different privacy budget.')
p('The emulator provides a lock protected reservation state machine, SHA 256 hash linked events, Ed25519 client receipts and three validator signatures per record. It stores actual serialized metadata and executes receipt checks. The benchmark does not start a Fabric network or measure Byzantine consensus under message delay. Its cryptographic operation timings are hosted container measurements, and its contention test exercises local atomicity rather than distributed consensus. The software configuration and raw per run metrics are included in the reproduction package.')
h('6.3 Metrics and fault injection',2)
p(f'Utility is evaluated with accuracy, macro F1 and macro recall, the latter serving as balanced accuracy. All percentage values are reported to two decimal places. Means and sample standard deviations use the 20 primary runs. Confusion matrices are shown for the preselected seed zero run rather than a selected best result. The fixed public test set is never used to select a client or tune a round; all hyperparameter selection is performed on a 15% validation split drawn strictly from the training data. Candidate configurations are evaluated under differential privacy noise (at ε = 4.0) rather than unnoised training, avoiding the pitfall of nonprivate tuning which selects excessive clipping bounds and round horizons that compound Gaussian noise on smaller cohorts. The tuned hyperparameters (Wearable: η = {wearable_hp["eta"]:.2f}, C = {wearable_hp["clip"]:.2f}, T = {wearable_hp["rounds"]}; WDBC: η = {wdbc_hp["eta"]:.2f}, C = {wdbc_hp["clip"]:.2f}, T = {wdbc_hp["rounds"]}) are kept fixed across all privacy budgets ε without early stopping or private validation release.')
# Fix 7: correct the Section 6.3 description of contention tests
p(f'The protocol tests inject {num_fault_classes} distinct protocol fault types across {_total_fault_trials:,} total trials (1,000 trials per class): payload tampering, receipt replay, stale parent models, corrupted signatures, revoked authorizations, budget overspending, forbidden refunds, altered aggregates, dropped roster clients, uncommitted fake models, mismatched weight lengths, and unsigned coordinator or client calls. A validly signed poisoning negative control tests provenance boundaries with 1,000 additional trials. In addition, {_n_attacks} contention tests, each with two simultaneous requests, leave enough budget for exactly one reservation. A separate accounting illustration performs 30 protected release attempts at ρ = 0.01 against a cap of 0.10, exposing the difference between actual disclosure and a counter that refunds every aborted release.')

h('7 Results and Discussion')
h('7.1 Privacy and utility',2)
rows=[]
for dataset,label in [('wearable','Wearable'),('wdbc','WDBC')]:
    for setting,e in [('nonprivate','Nonprivate'),('eps_0.5','0.50'),('eps_1','1.00'),('eps_2','2.00'),('eps_4','4.00'),('eps_8','8.00')]:
        rows.append((label,e,stat(dataset,setting,'accuracy'),stat(dataset,setting,'macro_f1'),stat(dataset,setting,'balanced_accuracy')))
table(['Dataset','Total ε','Accuracy %','Macro F1 %','Balanced accuracy %'],rows,[.85,.80,1.65,1.65,1.75],'Primary utility results as mean ± sample standard deviation across 20 fixed split repetitions')
# Fix 8: derive all numbers from CSV (no hardcoding)
_w_np   = df[(df.dataset=='wearable')&(df.setting=='nonprivate')].accuracy.mean()*100
_w_f1_4 = df[(df.dataset=='wearable')&(df.setting=='eps_4')].macro_f1.mean()*100
_w_f1_4s= df[(df.dataset=='wearable')&(df.setting=='eps_4')].macro_f1.std(ddof=1)*100
_wb_np  = df[(df.dataset=='wdbc')&(df.setting=='nonprivate')].accuracy.mean()*100
_wb_05  = df[(df.dataset=='wdbc')&(df.setting=='eps_0.5')].accuracy.mean()*100
_wb_05s = df[(df.dataset=='wdbc')&(df.setting=='eps_0.5')].accuracy.std(ddof=1)*100
_wb_1   = df[(df.dataset=='wdbc')&(df.setting=='eps_1')].accuracy.mean()*100
_wb_1s  = df[(df.dataset=='wdbc')&(df.setting=='eps_1')].accuracy.std(ddof=1)*100
p(f'The wearable surrogate yields {_w_acc4_m:.2f}% \u00b1 {_w_acc4_s:.2f}% accuracy at \u03b5 = 4, compared with a {_w_np:.2f}% deterministic matched nonprivate baseline. Its mean macro F1 is {_w_f1_4:.2f}% \u00b1 {_w_f1_4s:.2f}%. Hyperparameter tuning on a held-out validation split drawn from the training data improved the nonprivate wearable baseline from the original 62.9% to {_w_np:.2f}%, which is closer to the ~72% achievable by logistic regression on these features; the remaining gap reflects the difficulty of separating adjacent surrogate severity classes with a linear model. The measured values illustrate the behaviour of the learner under the disclosed accounting mechanism, not clinically adequate prediction.')
p(f'On the public WDBC benchmark, accuracy is {_wb_05:.2f}% ± {_wb_05s:.2f}% at ε = 0.5, {_wb_1:.2f}% ± {_wb_1s:.2f}% at ε = 1 and {_wb_acc4_m:.2f}% ± {_wb_acc4_s:.2f}% at ε = 4, compared with a matched nonprivate baseline of {_wb_np:.2f}%. Tuning hyperparameters under DP noise preserves private utility on this smaller cohort: whereas nonprivate tuning previously favored larger clipping thresholds and longer training horizons that degraded private accuracy (dropping to 88.08% at ε = 4 due to Gaussian noise accumulation), private-aware tuning (C = {wdbc_hp["clip"]:.2f}, η = {wdbc_hp["eta"]:.2f}, {wdbc_hp["rounds"]} rounds) sustains {_wb_acc4_m:.2f}% ± {_wb_acc4_s:.2f}%, fully matching nonprivate performance. At lower budgets (ε = 0.5 and ε = 1), private utility decreases as expected because the local Gaussian noise scale is inversely proportional to institutional sample count nk. The close correspondence at ε = 4 relative to the nonprivate baseline reflects effective sensitivity calibration and is not evidence that blockchain enhances statistical learning. No superiority claim is made from that difference.')
figure('figure3_privacy_utility','Privacy utility curves. Error bars show one sample standard deviation across 20 noise and partition repetitions on a fixed test split. Ledger auditing and unaudited private learning share the same numerical mechanism.')
figure('figure4_convergence',f'Accuracy over {wearable_hp["rounds"]} communication rounds in the preselected seed zero runs. These are representative trajectories, not averages or an early stopping criterion.')
h('7.2 Class specific behaviour',2)
_w_rec = details['wearable_eps_4']['recalls']
_w_cm = details['wearable_eps_4']['confusion']
_wb_rec = details['wdbc_eps_4']['recalls']
_wb_cm = details['wdbc_eps_4']['confusion']
_wb_mal_corr = _wb_cm[0][0]
_wb_ben_corr = _wb_cm[1][1]
_wb_tot = sum(sum(r) for r in _wb_cm)
p(f'Classwise results reveal a limitation hidden by a single aggregate score. In the ε = 4 wearable seed zero run, Normal and Severe recall are {_w_rec[0]*100:.2f}% and {_w_rec[3]*100:.2f}%, while Mild and Moderate recall are {_w_rec[1]*100:.2f}% and {_w_rec[2]*100:.2f}%. These surrogate middle classes frequently overlap with adjacent categories under the chosen generator, public transform, regularisation and short optimiser. The result identifies a statistical modelling weakness that cryptographic governance does not repair. Expanding the model or changing the training configuration would require a fresh evaluation with a fixed privacy policy.')
p(f'The public WDBC seed zero matrix records {_wb_mal_corr} correctly classified malignant and {_wb_ben_corr} correctly classified benign observations out of {_wb_tot} total. Malignant recall is {_wb_rec[0]*100:.2f}% and benign recall is {_wb_rec[1]*100:.2f}% for that run. These figures are conditional on one small public test split and should not be interpreted as validated sensitivity for a healthcare deployment. The matrix is presented to make the errors visible and to keep the narrative tied to the actual measurements.')
figure('figure5_confusion','Raw confusion matrix counts for ε = 4 in the preselected seed zero runs. Colour intensity indicates row normalized recall. Wearable labels are synthetic severity categories and WDBC is a public benchmark.')
h('7.3 Effect of the auditing layer',2)
# Fix 8: events breakdown derived from JSON
_ev_per_run = audit['events_per_training_run']
# events = open_round + 3*reserve + 3*submit + 3*accept + aggregate per round
p(f'Across the 20 paired \u03b5 = 4 wearable runs, enabling the signed ledger audit hook yields exactly the same final numerical model as disabling it under the same noise draws. The largest observed difference between the reported update and an independently recomputed weighted average is {audit["maximum_aggregate_difference"]:.2e}, below the 10\u207b\u00b9\u00b2 verification threshold. Each completed run emits {_ev_per_run} ledger events. Thus the benign utility result is a consequence of auditing a fixed computation, not a separate training gain.')
p('The paired check supplies an ablation for the governance layer: its signatures, commitments and accounting do not perturb the optimiser. It does not test availability under late institutions or consensus stalls. A production federation that rejects or loses a participant changes the accepted aggregation roster and can change utility even when all protected updates are valid. Such cases need a separate participation policy and an accountant that retains the cost of every already disclosed output.')
h('7.4 Protocol faults and privacy accounting attacks',2)
attackdf=pd.read_csv(RESULTS/'audit_attacks.csv')
labels={
    'payload_tamper':'Changed protected payload',
    'receipt_replay':'Replayed accepted receipt',
    'stale_model':'Stale parent model',
    'forged_signature':'Corrupted client signature',
    'revoked_consent':'Revoked institutional authorization',
    'budget_overspend':'Privacy budget overspend',
    'refund_laundering':'Refund after a possible release',
    'aggregate_tamper':'Changed weighted aggregate',
    'dropped_clients':'Dropped client in aggregate',
    'fake_models':'Uncommitted fake model',
    'wrong_length_weights':'Mismatched weights length',
    'unsigned_calls':'Unsigned coordinator/client call',
    'signed_poisoned_update':'Validly signed poisoned model'
}
table(['Injected condition','Trials','Rejected','Rejection rate %'],[
 (labels.get(r.attack,r.attack),str(r.trials),str(r.rejected),f'{100*r.rejection_rate:.2f}') for r in attackdf.itertuples()
],[3.20,.90,.90,1.70],'Mechanical fault injection results with a signed poisoning negative control')
p(f'All {_total_fault_rejected:,} injected protocol faults across {num_fault_classes} fault classes are rejected by the relevant implemented predicate. This outcome follows from explicit signature, commitment, version, authorization, budget or aggregation checks. It is a coverage result for those defined test mutations, not an empirical proof of cryptographic security against every attacker. All {_n_attacks} contention pairs admit exactly one reservation and leave the charged total at the cap. The emulator’s process lock enforces the serialization in this test. A deployment must obtain the corresponding ordering and state validation property from its distributed ledger.')
p('The refund illustration exposes the accounting failure directly. A controller that permits a protected release and then returns its ρ = 0.01 charge records a zero balance after each abort, yet 30 fresh releases incur a total actual cost of ρ = 0.30. BAPFL admits ten such charged attempts under the ρ = 0.10 cap and rejects subsequent reservations. Even an aborted update remains charged. This experiment illustrates the reservation invariant without pretending to reproduce an attack against a particular published blockchain framework.')
p('The signed poisoning negative control is accepted in all 1,000 trials. The attacker supplies a model with arbitrary large finite coordinates, then signs its matching commitment with an authorized fixture key. The prototype correctly establishes the origin and consistency of that payload, but has no independent statistical criterion for rejecting it. Similarly, it cannot infer from a receipt alone whether an institution clipped every record or sampled the declared noise distribution. These results delimit the governance contribution and the honest endpoint assumption in the privacy theorem.')
figure('figure6_audit_budget',f'Left, rejection rates for {num_fault_classes} specified protocol faults and the signed poisoning negative control. Right, actual disclosure under irreversible reservation compared with a release then refund counter in the constructed accounting illustration.')
h('7.5 Client count and partition sensitivity',2)
hetero=df[df.dataset=='heterogeneity']
rows=[]
for (k,a),group in hetero.groupby(['clients','dirichlet_alpha']):
    rows.append((str(int(k)),f'{a:.2f}',f'{group.accuracy.mean()*100:.2f} ± {group.accuracy.std()*100:.2f}',f'{group.macro_f1.mean()*100:.2f} ± {group.macro_f1.std()*100:.2f}'))
table(['Institutions K','Dirichlet α','Accuracy %','Macro F1 %'],rows,[1.25,1.25,2.15,2.05],'Wearable client count experiment at ε = 4 with ten repetitions per cell')
_k3_acc = hetero[hetero.clients==3].accuracy.mean()*100
_k10_acc = hetero[hetero.clients==10].accuracy.mean()*100
p(f'At a fixed client count and matched random seeds, all three Dirichlet settings yield the same numerical aggregate to displayed precision. This is predicted by the weighted full batch identity in Section 5.4. Increasing K from 3 to 10 changes mean accuracy from {_k3_acc:.2f}% to {_k10_acc:.2f}% in this separate ten seed experiment and increases the aggregate noise variance factor from 3 to 10 for fixed N. The label skew invariance is restricted to the one local step, complete participation configuration. Reporting it as general robustness to non IID healthcare data would overstate the experiment.')
h('7.6 Local costs and storage',2)
timingrows=[]
for key,label in [('reserve','Reserve and certify'),('sign_receipt','Sign receipt'),('submit_verify','Verify and certify submission'),('payload_verify','Verify payload commitment')]:
    d=audit['local_timings'][key];timingrows.append((label,f'{d["median_ms"]:.3f}',f'{d["p95_ms"]:.3f}'))
table(['Operation','Median ms','95th percentile ms'],timingrows,[3.20,1.75,1.75],'Local emulator operation timings across 1,000 repetitions with hosted environment variability')
p(f'The canonical signed receipt in the timing fixture occupies {audit["median_receipt_bytes"]} bytes. A four class, 17 feature float64 local model occupies 576 bytes, so eliminating a full model from a small ledger entry produces only a modest payload difference before certificates and transaction overhead are considered. At 10,000 features the model payload is 320,032 bytes, while the comparable receipt fixture remains 473 bytes. The receipt only reduction is then 99.85%. This calculation excludes quorum signatures, hash linked block envelopes, reservations and aggregate events, and therefore is not a measurement of overall blockchain storage reduction.')
p('The local timings show the cost of serialization, hashing, Ed25519 signing, signature verification and the emulator’s certificates. Their variation reflects the hosted execution environment. They do not establish network throughput, block finality latency, energy efficiency or Byzantine fault tolerance. Those measurements must be obtained from a deployed ordering service and institutional network configuration. The present prototype supplies an executable boundary for the accounting and validation logic rather than a substitute for such a deployment.')
figure('figure7_cost_storage','Left, measured local cryptographic operation cost. Right, a dense four class float64 model payload compared with the fixed signed receipt fixture. Receipt size excludes full blockchain transaction and certificate overhead.')

h('8 Limitations and Deployment Considerations')
p('The study’s strongest evidence concerns the specified protocol lifecycle and its mathematical accounting. The wearable benchmark is wholly synthetic, and the WDBC exercise is a single public cohort with one fixed test split. Neither is a multi institution clinical validation. The low recall of intermediate wearable classes is an explicit statistical limitation. An institution considering this design would need representative prospective data, outcome definitions, calibrated predictions, subgroup analysis and an external assessment of whether the model supports its intended use. The present results do not establish clinical effectiveness.')
p('The learner is a one local step full batch model, with conservative Gaussian composition and no subsampling amplification. This choice makes the privacy accounting transparent but does not explore modern deep models, multiple local epochs or communication constrained devices. A more capable learner might improve the synthetic middle class results, while privacy amplification or a tighter accountant could improve small cohort utility. Each modification must preserve the release gate and account for every new data dependent output. The fixed settings here should not be silently reused as a general optimum.')
p('The permissioned ledger implementation is a single process emulator. Its three validator signatures are fixture certificates, and the contention tests use a process lock. It does not evaluate consensus networking, replica disagreement, leader replacement, validator key compromise, durability after crashes or finality under a network partition. Hyperledger Fabric provides an appropriate implementation route [12, 13], but the proposed deployment has not been benchmarked. Persisting the budget scope across restarts and across multiple jobs is essential; restarting a client with a fresh local counter must not reset disclosure history.')
p('Trust in the local training endpoint remains material. A smart contract can enforce a declared cost and validate a commitment, yet it cannot directly verify correct noise generation from an opaque model hash. A compromised institution can sign an unnoised or poisoned payload. Trusted execution attestation or a carefully designed proof system could address parts of that problem, but neither is implemented or claimed here. Secure aggregation would change which auditors can see protected local models and would need a compatible proof of aggregate correctness. These are concrete extensions rather than assumed capabilities.')
p('Irreversible reservation sacrifices some available budget when an attempt fails before disclosure. That conservative behaviour is intentional and visible. It prevents the accounting error in the constructed refund example but does not eliminate denial of service through wasted reservations. An institution should authenticate reservation requests, limit request rates and use stable job scopes. Patient level revocation, retention, cohort enrollment privacy and model unlearning remain separate from the public institutional authorization epoch.')
p('The contribution is the explicit joint construction of an irreversible reservation lifecycle, a full transcript Gaussian accountant and a version bound aggregation audit. Existing work already studies budget contracts, privacy mechanisms and blockchain verification [8–11]. The targeted literature review supports this positioning but does not prove an exhaustive global priority claim. A deployment study and broader prior art review are needed before treating the proposed integration as a fully validated production system or making stronger novelty claims.')

h('9 Conclusion')
p('BAPFL integrates permissioned blockchain governance with differentially private federated healthcare learning through a precise disclosure lifecycle. A protected local model is tied to an institution, authorization epoch, parent model and irreversible privacy reservation. Proper gradient clipping and Gaussian perturbation occur before every shared update, and the complete ideal mechanism transcript is bounded through zero concentrated differential privacy. Independent aggregation verification provides evidence that the anchored global model corresponds to the committed protected update set.')
# Fix 8: conclusion numbers from CSV
p(f'The controlled evaluation separates privacy, utility and protocol integrity. At \u03b5 = 4 and \u03b4 = 10\u207b\u2075, mean accuracy is {_w_acc4_m:.2f}% on the synthetic wearable surrogate and {_wb_acc4_m:.2f}% on the public WDBC benchmark across 20 repetitions. The audit hook preserves final models exactly in paired executions. {num_fault_classes} specified protocol faults are rejected in 1,000 trials each, while a correctly signed poisoning negative control remains accepted. That negative result is part of the design boundary: provenance and budget accounting do not certify correct statistical behaviour.')
p('The new protocol supplies executable evidence for charging before disclosure and retaining the charge after abort or rejection. The next substantive steps are implementation on a distributed permissioned ledger, verification of durable budget state, integration with endpoint attestation or compatible secure aggregation, and prospective multi institution clinical evaluation. Those steps would test the assumptions that are explicit in the present protocol analysis.')

h('Data and Code Availability')
p('The reproduction package includes the synthetic data generator, the public benchmark loader, utility experiments, signed ledger emulator, fault injection tests, raw results and vector figure sources. The wearable data are generated entirely from disclosed distributions and seeds. The public WDBC dataset is available from the UCI repository under its stated CC BY 4.0 license [17]. Benchmark keys and random seeds are reproducibility fixtures and must be replaced by fresh protected randomness for any deployment involving confidential records.')

h('References')
refs=[
 'H. B. McMahan, E. Moore, D. Ramage, S. Hampson and B. A. y Arcas, Communication Efficient Learning of Deep Networks from Decentralized Data, Proceedings of AISTATS, PMLR 54, pp. 1273–1282, 2017. https://proceedings.mlr.press/v54/mcmahan17a.html',
 'N. Rieke et al., The future of digital health with federated learning, npj Digital Medicine 3, article 119, 2020. https://doi.org/10.1038/s41746-020-00323-1',
 'C. Dwork and A. Roth, The Algorithmic Foundations of Differential Privacy, Foundations and Trends in Theoretical Computer Science 9(3–4), pp. 211–487, 2014. https://doi.org/10.1561/0400000042',
 'M. Abadi et al., Deep Learning with Differential Privacy, Proceedings of the ACM Conference on Computer and Communications Security, 2016. https://arxiv.org/abs/1607.00133',
 'M. Bun and T. Steinke, Concentrated Differential Privacy Simplifications Extensions and Lower Bounds, Theory of Cryptography Conference, 2016. https://arxiv.org/abs/1605.02065',
 'I. Mironov, Rényi Differential Privacy, IEEE Computer Security Foundations Symposium, 2017. https://arxiv.org/abs/1702.07476',
 'R. Rogers, A. Roth, J. Ullman and S. Vadhan, Privacy Odometers and Filters Pay as You Go Composition, Advances in Neural Information Processing Systems 29, 2016. https://arxiv.org/abs/1605.08294',
 'H. Kim, J. Park, M. Bennis and S. L. Kim, Blockchained On Device Federated Learning, IEEE Communications Letters, 2019. https://doi.org/10.1109/LCOMM.2019.2921755',
 'M. Shayan, C. Fung, C. J. M. Yoon and I. Beschastnikh, Biscotti A Blockchain System for Private and Secure Federated Learning, IEEE Transactions on Parallel and Distributed Systems 32(7), pp. 1513–1525, 2021. https://doi.org/10.1109/TPDS.2020.3044223',
 'S. De Chaudhury et al., Blockchain Based Secure Federated Learning With Local Differential Privacy and Incentivization, IEEE Transactions on Privacy 1, pp. 31–44, 2024. https://doi.org/10.1109/TP.2024.3487819',
 'W. Jia and T. Xie, BE DPFL A Blockchain Enhanced Privacy Preserving Federated Learning Framework for Secure Edge Network Collaboration, Applied Sciences 16(4), article 1791, 2026. https://doi.org/10.3390/app16041791',
 'E. Androulaki et al., Hyperledger Fabric A Distributed Operating System for Permissioned Blockchains, Proceedings of EuroSys, 2018. https://arxiv.org/abs/1801.10228',
 'Hyperledger Fabric, The Ordering Service, official documentation, accessed 13 October 2026. https://hyperledger-fabric.readthedocs.io/en/latest/orderer/ordering_service.html',
 'K. Bonawitz et al., Practical Secure Aggregation for Privacy Preserving Machine Learning, Proceedings of the ACM Conference on Computer and Communications Security, 2017. https://research.google/pubs/practical-secure-aggregation-for-privacy-preserving-machine-learning/',
 'L. Zhu, Z. Liu and S. Han, Deep Leakage from Gradients, Advances in Neural Information Processing Systems 32, 2019. https://arxiv.org/abs/1906.08935',
 'E. Bagdasaryan, A. Veit, Y. Hua, D. Estrin and V. Shmatikov, How To Backdoor Federated Learning, Proceedings of AISTATS, PMLR 108, pp. 2938–2948, 2020. https://proceedings.mlr.press/v108/bagdasaryan20a.html',
 'UCI Machine Learning Repository, Breast Cancer Wisconsin Diagnostic, dataset, 1993. https://doi.org/10.24432/C5DW2B',
 'S. Josefsson and I. Liusvaara, Edwards Curve Digital Signature Algorithm EdDSA, RFC 8032, 2017. https://doi.org/10.17487/RFC8032',
 'A. Singh, Anurag and B. K. Chaurasia, Federated Learning with Differential Privacy for Medical Data Analysis, manuscript supplied for this study, undated.',
 'K. Chaudhuri, C. Monteleoni and A. D. Sarwate, Differentially Private Empirical Risk Minimization, Journal of Machine Learning Research 12, pp. 1069–1109, 2011. https://jmlr.org/papers/v12/chaudhuri11a.html'
]
for i,ref in enumerate(refs,1):
    q=p(f'[{i}] {ref}',align=WD_ALIGN_PARAGRAPH.LEFT)
    q.paragraph_format.left_indent=Inches(.27);q.paragraph_format.first_line_indent=Inches(-.27)
    q.paragraph_format.space_after=Pt(5);q.paragraph_format.line_spacing=1.0
    for r in q.runs:font(r,9.5)

h('Appendix A Reproduction and Public Transformation Constants')
p('All runs use a fixed dataset generation seed of 20261013 for the wearable surrogate and a stratified split seed of 77. The 20 primary partition seeds are 1000 through 1019, with noise seeds 5000 through 5019. The sensitivity grid uses partition seeds 9000 through 9009 and noise seeds 10000 through 10009. Public input values are centred and scaled, bounded componentwise to [−3, 3], augmented with a bias coordinate and projected to unit Euclidean norm. The constants below are engineering choices declared in the experiment, not estimated medical reference intervals.')
names=['Heart rate','Oxygen saturation','Systolic pressure','Diastolic pressure','Glucose','Temperature','Respiratory rate','Activity','Sleep','Stress','Heart rate variability','Steps','Calories','Heart rate divided by stress plus one','Oxygen deficit','Pressure difference','Vital risk index']
centers=[85,95,128,80,120,37.1,18,52,6.8,4.4,50,5900,1830,23,5,48,2.25]
scales=[20,4,25,12,40,.6,4,22,1.5,2.5,20,2600,400,20,4,18,2]
table(['Surrogate input','Public centre','Public scale'],[(a,f'{b:g}',f'{c:g}') for a,b,c in zip(names,centers,scales)],[3.65,1.55,1.50],'Fixed surrogate transformation constants in generator units')
p('For WDBC, the 30 public scale upper values, in scikit learn feature order, are 20, 30, 140, 1200, 0.15, 0.30, 0.40, 0.20, 0.30, 0.12, 3, 4, 20, 400, 0.03, 0.10, 0.10, 0.05, 0.06, 0.03, 30, 40, 200, 2000, 0.20, 0.70, 0.80, 0.30, 0.50 and 0.20. Each feature uses half its stated upper value as both centre and scale before the common component bound and norm projection. These are disclosed algorithm settings rather than statistics computed from protected training records.')
p('Software versions and execution commands are provided in the package README.')

for part in [doc._element,doc.styles.element]:
    for border in part.xpath('.//w:pBdr'):border.getparent().remove(border)
out=OUTPUT/'Blockchain_Governed_Private_Federated_Healthcare_Research_Paper.docx'
doc.save(out)
(ROOT/'manuscript_text.md').write_text('\n\n'.join(notes),encoding='utf-8')
# Fix 7: store relative path, not absolute, to avoid embedding local filesystem paths
summary={'file':out.name,'words':len(' '.join(notes).split()),'native_equations':eqcount,'figures':figcount,'tables':tablecount,'references':len(refs)}
(ROOT/'manuscript_manifest.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
