"""Reproduce controlled utility experiments for blockchain audited private FL.

No private source dataset is used. The wearable benchmark is wholly synthetic.
The ledger does not alter numerical training; DP and audited DP use identical
random draws. Public seeds are for benchmark reproduction only, not deployment.
"""
from pathlib import Path
import argparse, json, time, platform
import numpy as np
import pandas as pd
from scipy.special import softmax
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, recall_score, confusion_matrix

ROUNDS=80
DELTA=1e-5
CLIP=0.5
ETA=2.0
L2=0.003
EPSILONS=[0.5,1.0,2.0,4.0,8.0]

# ---------- per-dataset hyperparameters tuned on a val split (Fix 1) ----------
# Tuned via grid search on a validation split taken from training data ONLY.
# The test set is never touched during tuning.  Chosen settings are then frozen
# across all epsilon values and seeds.
DATASET_HP = {
    'wearable': {'eta': 4.0, 'clip': 1.0, 'rounds': 80},
    'wdbc':     {'eta': 2.0, 'clip': 0.5, 'rounds': 80},
}

def rho_limit(epsilon,delta=DELTA):
    L=np.log(1.0/delta)
    return float((np.sqrt(L+epsilon)-np.sqrt(L))**2)

def epsilon_from_rho(rho,delta=DELTA):
    return float(rho+2*np.sqrt(rho*np.log(1/delta)))

def public_transform(X,centers,scales):
    Z=np.clip((X-np.asarray(centers))/np.asarray(scales),-3,3)
    Z=np.column_stack([np.ones(len(Z)),Z])
    return Z/np.maximum(1,np.linalg.norm(Z,axis=1))[:,None]

def wearable_data():
    rng=np.random.default_rng(20261013)
    y=np.repeat(np.arange(4),1500)
    rng.shuffle(y)
    s=y+rng.normal(0,0.45,len(y))
    hr=70+10*s+rng.normal(0,9,len(y))
    spo2=np.clip(98-2*s+rng.normal(0,1.4,len(y)),75,100)
    sbp=110+12*s+rng.normal(0,12,len(y))
    dbp=72+5*s+rng.normal(0,8,len(y))
    glucose=90+20*s+rng.normal(0,24,len(y))
    temp=36.6+0.35*s+rng.normal(0,0.35,len(y))
    resp=15+2*s+rng.normal(0,2,len(y))
    activity=np.clip(70-12*s+rng.normal(0,13,len(y)),0,100)
    sleep=np.clip(8-0.8*s+rng.normal(0,1,len(y)),1,12)
    stress=np.clip(2+1.6*s+rng.normal(0,1.2,len(y)),0,10)
    hrv=np.clip(65-10*s+rng.normal(0,11,len(y)),5,160)
    steps=np.maximum(100,8000-1400*s+rng.normal(0,1700,len(y)))
    calories=np.maximum(300,2100-180*s+rng.normal(0,250,len(y)))
    interactions=np.column_stack([hr/(stress+1),100-spo2,sbp-dbp,
                                 (hr-70)/20+(98-spo2)/4+(resp-15)/4])
    X=np.column_stack([hr,spo2,sbp,dbp,glucose,temp,resp,activity,sleep,
                       stress,hrv,steps,calories,interactions])
    centers=[85,95,128,80,120,37.1,18,52,6.8,4.4,50,5900,1830,
             23,5,48,2.25]
    scales=[20,4,25,12,40,0.6,4,22,1.5,2.5,20,2600,400,
            20,4,18,2]
    return public_transform(X,centers,scales),y

def cancer_data():
    d=load_breast_cancer()
    # Fixed engineering scales, declared in advance; no fitted normalizer.
    upper=[20,30,140,1200,.15,.3,.4,.2,.3,.12,
           3,4,20,400,.03,.1,.1,.05,.06,.03,
           30,40,200,2000,.2,.7,.8,.3,.5,.2]
    return public_transform(d.data,np.asarray(upper)/2,np.asarray(upper)/2),d.target

def partition(y,k,alpha,seed):
    """Dirichlet class allocation, rejecting partitions with small sites."""
    rng=np.random.default_rng(seed)
    minimum=max(30,int(len(y)/(10*k)))
    for attempt in range(1000):
        ids=[[] for _ in range(k)]
        for label in np.unique(y):
            a=np.flatnonzero(y==label)
            rng.shuffle(a)
            counts=rng.multinomial(len(a),rng.dirichlet(np.repeat(alpha,k)))
            offset=0
            for j,c in enumerate(counts):
                ids[j].extend(a[offset:offset+c].tolist());offset+=c
        if min(map(len,ids))>=minimum:
            return [np.asarray(a,dtype=int) for a in ids]
    raise RuntimeError('Cannot obtain a valid partition')

def tune_hp(name, X, y, tr_idx, val_size=0.15, eps_tune=4.0, seed=42):
    """Grid-search eta/clip/rounds on a validation split carved from training UNDER DP noise (eps=4).

    The test set is never seen during tuning.
    Tuning under DP noise (eps=4.0) prevents picking over-optimistic high clips / rounds
    that severely degrade private utility.
    Returns (best_hp, grid_report).
    """
    rng = np.random.default_rng(seed)
    n_tr = len(tr_idx)
    val_n = max(1, int(n_tr * val_size))
    perm = rng.permutation(n_tr)
    val_local  = tr_idx[perm[:val_n]]
    tune_local = tr_idx[perm[val_n:]]

    local_parts = partition(y[tune_local], 3, 1.0, seed=1000)
    tune_ids = [tune_local[p] for p in local_parts]

    eta_grid   = [0.5, 1.0, 2.0, 4.0, 8.0]   # 100 diverges — excluded
    clip_grid  = [0.3, 0.5, 1.0, 2.0]
    round_grid = [60, 80, 100, 120]

    grid_report = []
    best_acc, best_hp = -1.0, DATASET_HP[name]

    print(f"--- Tuning {name} on val split under DP noise (eps={eps_tune}) ---", flush=True)
    for eta in eta_grid:
        for clip in clip_grid:
            for rounds in round_grid:
                res = train(X, y, X[val_local], y[val_local], tune_ids,
                            epsilon=eps_tune, seed=5000,
                            eta=eta, clip=clip, rounds=rounds)
                acc = res['accuracy']
                grid_report.append({'eta': eta, 'clip': clip, 'rounds': rounds, 'val_accuracy': acc})
                if acc > best_acc:
                    best_acc = acc
                    best_hp  = {'eta': eta, 'clip': clip, 'rounds': rounds}

    print(f"Chosen {name} HP under DP (eps={eps_tune}): {best_hp} (val_acc={best_acc:.4f})", flush=True)
    return best_hp, grid_report


def train(X,y,Xtest,ytest,ids,epsilon,seed,audit_hook=None,audit_reserve_hook=None,
          eta=None,clip=None,rounds=None):
    """Train federated softmax.  eta/clip/rounds default to module constants
    and are overridden by the per-dataset tuned values when called from main().
    """
    if eta    is None: eta    = ETA
    if clip   is None: clip   = CLIP
    if rounds is None: rounds = ROUNDS

    classes=int(y.max()+1)
    W=np.zeros((classes,X.shape[1]))
    rng=np.random.default_rng(seed)
    # A conservative fixed-point budget: round the cap down, allocate whole
    # units, and calibrate noise to that exact allocation, not vice versa.
    cost_units=0 if epsilon is None else int(np.floor(rho_limit(epsilon)*1e12))//rounds
    z=0 if epsilon is None else np.sqrt(1/(2*cost_units/1e12))
    Y=np.eye(classes)[y]
    history=[]; clipping=[]
    for t in range(rounds):
        if audit_reserve_hook is not None:
            audit_reserve_hook(t,W.copy(),cost_units)
        mean_gradient=np.zeros_like(W)
        parent=W.copy() if audit_hook is not None else None
        local_models=[]
        clipped_count=0
        for a in ids:
            p=softmax(X[a]@W.T,axis=1)
            G=(p-Y[a])[:,:,None]*X[a,None,:]
            norms=np.linalg.norm(G.reshape(len(a),-1),axis=1)
            factors=np.minimum(1,clip/np.maximum(norms,1e-15))
            clipped_count+=int((norms>clip).sum())
            g=(G*factors[:,None,None]).mean(axis=0)
            if epsilon is not None:
                g+=rng.normal(0,z*2*clip/len(a),W.shape)
            if audit_hook is not None:
                local_models.append(W-eta*(g+L2*W))
            mean_gradient+=len(a)/len(y)*g
        W-=eta*(mean_gradient+L2*W)
        if audit_hook is not None:
            audit_hook(t,parent,local_models,W.copy(),cost_units)
        pred=np.argmax(Xtest@W.T,axis=1)
        history.append(accuracy_score(ytest,pred))
        clipping.append(clipped_count/len(y))
    pred=np.argmax(Xtest@W.T,axis=1)
    per_class_recall = recall_score(ytest, pred, average=None).tolist()
    return {'accuracy':accuracy_score(ytest,pred),
            'macro_f1':f1_score(ytest,pred,average='macro'),
            'balanced_accuracy':recall_score(ytest,pred,average='macro'),
            'recalls':per_class_recall,
            'confusion':confusion_matrix(ytest,pred).tolist(),
            'history':history,'clipping':float(np.mean(clipping)),
            'noise_multiplier':float(z),'weights':W.tolist()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',type=int,default=20)
    ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    rows=[];details={};start=time.perf_counter()

    before_after=[]  # collect before/after accuracy for reporting

    for name,factory,test_size in [('wearable',wearable_data,.2),('wdbc',cancer_data,.25)]:
        X,y=factory()
        tr,te=train_test_split(np.arange(len(y)),test_size=test_size,
                              stratify=y,random_state=77)
        Xtr,ytr,Xte,yte=X[tr],y[tr],X[te],y[te]

        # ---- Fix 1: tune on val split under DP noise, never touching test set -
        hp, grid_report = tune_hp(name, X, y, tr, val_size=0.15, eps_tune=4.0, seed=42)
        print(f'{name}: chosen hp under DP = {hp}', flush=True)

        # Before accuracy (original defaults, nonprivate, seed 0)
        ids0 = partition(ytr, 3, 1.0, 1000)
        before_r = train(Xtr, ytr, Xte, yte, ids0, None, 5000,
                         eta=ETA, clip=CLIP, rounds=ROUNDS)
        before_acc = before_r['accuracy']
        before_recalls = before_r['recalls']

        # After accuracy (tuned, nonprivate, seed 0)
        after_r = train(Xtr, ytr, Xte, yte, ids0, None, 5000, **hp)
        after_acc = after_r['accuracy']
        after_recalls = after_r['recalls']

        before_after.append({
            'dataset': name,
            'before_acc': before_acc,
            'after_acc':  after_acc,
            'before_recalls': before_recalls,
            'after_recalls':  after_recalls,
            'tuned_hp': hp,
            'tuning_grid': grid_report,
        })
        print(f'{name}: before={before_acc*100:.2f}%  after={after_acc*100:.2f}%', flush=True)
        print(f'  before recalls: {[f"{r*100:.1f}%" for r in before_recalls]}', flush=True)
        print(f'  after  recalls: {[f"{r*100:.1f}%" for r in after_recalls]}', flush=True)
        # ----------------------------------------------------------------------

        for s in range(args.seeds):
            ids=partition(ytr,3,1.0,1000+s)
            for epsilon in [None]+EPSILONS:
                result=train(Xtr,ytr,Xte,yte,ids,epsilon,5000+s,**hp)
                setting='nonprivate' if epsilon is None else f'eps_{epsilon:g}'
                rows.append({'dataset':name,'seed':s,'setting':setting,
                             'epsilon':epsilon,'accuracy':result['accuracy'],
                             'macro_f1':result['macro_f1'],
                             'balanced_accuracy':result['balanced_accuracy'],
                             'clipping':result['clipping'],
                             'minimum_client_n':min(map(len,ids)),
                             'maximum_client_n':max(map(len,ids))})
                if s==0:
                    details[f'{name}_{setting}']={**result,
                         'client_sizes':[len(a) for a in ids],
                         'client_classes':[np.bincount(ytr[a],minlength=int(y.max()+1)).tolist() for a in ids],
                         'train_n':len(tr),'test_n':len(te),'test_classes':np.bincount(yte).tolist()}
            if (s+1)%5==0:
                print(f'{name}: {s+1}/{args.seeds} seeds complete',flush=True)
        if name=='wearable':
            for alpha in [.2,1.0,10.0]:
                for k in [3,6,10]:
                    for s in range(10):
                        ids=partition(ytr,k,alpha,9000+s)
                        result=train(Xtr,ytr,Xte,yte,ids,4.0,10000+s,**hp)
                        rows.append({'dataset':'heterogeneity','seed':s,'setting':f'K{k}_a{alpha:g}',
                                     'epsilon':4.0,'clients':k,'dirichlet_alpha':alpha,
                                     'accuracy':result['accuracy'],'macro_f1':result['macro_f1'],
                                     'balanced_accuracy':result['balanced_accuracy'],
                                     'minimum_client_n':min(map(len,ids)),
                                     'maximum_client_n':max(map(len,ids))})
                    print(f'heterogeneity K={k}, alpha={alpha}: complete',flush=True)
    df=pd.DataFrame(rows);df.to_csv(args.output/'utility_runs.csv',index=False)
    summary=df.groupby(['dataset','setting'],sort=False)[['accuracy','macro_f1','balanced_accuracy']].agg(['mean','std','count'])
    summary.to_csv(args.output/'utility_summary.csv')
    metadata={'rounds':ROUNDS,'delta':DELTA,'gradient_clip':CLIP,'learning_rate':ETA,
              'l2':L2,'seeds':args.seeds,'epsilon_grid':EPSILONS,'python':platform.python_version(),
              'platform':platform.platform(),'elapsed_seconds':time.perf_counter()-start,
              'tuned_hp':{ba['dataset']:ba['tuned_hp'] for ba in before_after},
              'tuning_grids':{ba['dataset']:ba.get('tuning_grid') for ba in before_after},
              'before_after':[{k:v for k,v in ba.items() if k not in ('tuned_hp','tuning_grid')} for ba in before_after]}
    (args.output/'details.json').write_text(json.dumps(details,indent=2))
    (args.output/'config.json').write_text(json.dumps(metadata,indent=2))
    print(summary.to_string(),flush=True)
    print(json.dumps(metadata),flush=True)

if __name__=='__main__':main()
