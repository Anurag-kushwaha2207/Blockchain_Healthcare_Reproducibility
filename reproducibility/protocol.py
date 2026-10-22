"""Signed ledger emulator and privacy reservation state machine.

This is a single-process emulator, not a deployed Fabric or PBFT network.
Three-of-four signatures emulate certificates, not network consensus.
"""
from pathlib import Path
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
import copy, hashlib, json, time, math
import numpy as np
import pandas as pd
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from experiment import (train,wearable_data,partition,rho_limit,ROUNDS,ETA,L2)
from sklearn.model_selection import train_test_split

SCALE=10**12

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def digest(data):return hashlib.sha256(data).hexdigest()

def array_bytes(a):return np.ascontiguousarray(a,dtype='<f8').tobytes()

def model_hash(a):return digest(array_bytes(a))

def fixture_key(tag):
    # Deterministic keys are intentionally insecure public benchmark fixtures.
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(tag.encode()).digest())

class Ledger:
    def __init__(self,budget_units=100_000_000_000,clients=('A','B','C'),expected_cost=10_000_000_000):
        self.lock=RLock()
        self.expected_cost=int(expected_cost)
        self.budget={c:int(budget_units) for c in clients}
        self.spent={c:0 for c in clients}
        self.active={c:True for c in clients}
        self.epoch={c:0 for c in clients}
        self.client_keys={c:fixture_key('client-'+c) for c in clients}
        self.validators=[fixture_key('validator-'+str(j)) for j in range(4)]
        self.records=[];self.head='0'*64;self.reservations={};self.submissions={};self.used=set()
        self.round_parent={};self.reason=None

    def _append(self,event):
        body={'height':len(self.records),'parent':self.head,'event':event}
        h=digest(canonical(body))
        cert=[{'validator':j,'signature':self.validators[j].sign(bytes.fromhex(h)).hex()} for j in range(3)]
        block={**body,'hash':h,'certificate':cert}
        self.records.append(block);self.head=h
        return h

    def open_round(self,t,parent):
        with self.lock:
            if t in self.round_parent: raise ValueError('round_already_open')
            self.round_parent[t]=parent

    def reserve(self,client,t,parent,cost):
        with self.lock:
            self.reason=None
            key=(client,int(t))
            if client not in self.active or not self.active[client]:self.reason='revoked';return None
            if self.round_parent.get(t)!=parent:self.reason='stale_parent';return None
            if key in self.reservations:self.reason='duplicate_reservation';return None
            if not isinstance(cost,int) or cost<=0:self.reason='invalid_cost';return None
            if cost!=self.expected_cost:self.reason='policy_cost_mismatch';return None
            if self.spent[client]+cost>self.budget[client]:self.reason='budget_exhausted';return None
            self.spent[client]+=cost
            record={'client':client,'round':t,'parent_model':parent,'cost_units':cost,
                    'consent_epoch':self.epoch[client],'state':'reserved'}
            self.reservations[key]=record
            self._append({'type':'reserve',**record})
            return copy.deepcopy(record)

    def receipt(self,client,t,local_model):
        r=self.reservations[(client,t)]
        nonce=digest(canonical({'client':client,'round':t,'nonce_fixture':2026}))
        # Commitments cover only already DP-protected model parameters.
        r={k:v for k,v in r.items() if k!='state'}
        r.update({'commitment':digest(bytes.fromhex(nonce)+array_bytes(local_model)),
                  'nonce':nonce,'schema':'softmax-f64-v1'})
        r['signature']=self.client_keys[client].sign(canonical(r)).hex()
        return r

    def submit(self,r):
        with self.lock:
            self.reason=None
            client=r.get('client');t=r.get('round');key=(client,t)
            reserved=self.reservations.get(key)
            if reserved is None:self.reason='no_reservation';return False
            if not self.active[client] or r.get('consent_epoch')!=self.epoch[client]:self.reason='revoked';return False
            if r.get('parent_model')!=self.round_parent.get(t):self.reason='stale_parent';return False
            for field in ['cost_units','consent_epoch','client','round','parent_model']:
                if r.get(field)!=reserved[field]:self.reason='reservation_mismatch';return False
            if key in self.submissions:self.reason='replay';return False
            unsigned={k:v for k,v in r.items() if k!='signature'}
            try:self.client_keys[client].public_key().verify(bytes.fromhex(r['signature']),canonical(unsigned))
            except (InvalidSignature,ValueError,KeyError):self.reason='signature';return False
            self.submissions[key]=copy.deepcopy(r)
            reserved['state']='submitted'
            self._append({'type':'submit',**r})
            return True

    def receive(self,r,a):
        with self.lock:
            key=(r.get('client'),r.get('round'));self.reason=None
            if key in self.used:self.reason='replay';return False
            if self.submissions.get(key)!=r:self.reason='uncommitted_receipt';return False
            if not self.active[key[0]] or r['consent_epoch']!=self.epoch[key[0]]:self.reason='revoked';return False
            if not np.isfinite(a).all():self.reason='nonfinite';return False
            if digest(bytes.fromhex(r['nonce'])+array_bytes(a))!=r['commitment']:self.reason='commitment';return False
            self.used.add(key);self.reservations[key]['state']='accepted'
            return True

    def revoke(self,c):
        with self.lock:
            self.active[c]=False;self.epoch[c]+=1
            self._append({'type':'revoke','client':c,'consent_epoch':self.epoch[c]})

    def refund(self,client,t):
        self.reason='refund_forbidden';return False

    def verify_chain(self,trusted_head=None):
        previous='0'*64
        for i,r in enumerate(self.records):
            body={k:r[k] for k in ['height','parent','event']}
            if r['height']!=i or r['parent']!=previous or digest(canonical(body))!=r['hash']:return False
            seen=set()
            for item in r['certificate']:
                j=item['validator']
                if j in seen or not 0<=j<4:return False
                try:self.validators[j].public_key().verify(bytes.fromhex(item['signature']),bytes.fromhex(r['hash']))
                except (InvalidSignature,ValueError):return False
                seen.add(j)
            if len(seen)<3:return False
            previous=r['hash']
        return trusted_head is None or previous==trusted_head

def verify_aggregate(models,weights,claimed,tol=1e-12):
    expected=np.sum(np.array(models)*np.asarray(weights)[:,None,None],axis=0)
    return bool(np.max(np.abs(expected-claimed))<=tol),expected

def fixture():
    a=np.arange(12,dtype=float).reshape(3,4)/10
    l=Ledger();parent=model_hash(np.zeros_like(a));l.open_round(0,parent)
    l.reserve('A',0,parent,10_000_000_000)
    r=l.receipt('A',0,a)
    return l,a,r

def attack_trials(n=1000):
    rows=[]
    attacks=['payload_tamper','receipt_replay','stale_model','forged_signature',
             'revoked_consent','budget_overspend','refund_laundering','aggregate_tamper',
             'signed_poisoned_update']
    rng=np.random.default_rng(440)
    for attack in attacks:
        rejected=0
        for _ in range(n):
            l,a,r=fixture()
            if attack=='payload_tamper':
                assert l.submit(r);a=a.copy();a.flat[rng.integers(a.size)]+=rng.uniform(.01,1)
                reject=not l.receive(r,a)
            elif attack=='receipt_replay':
                assert l.submit(r) and l.receive(r,a);reject=not l.receive(r,a)
            elif attack=='stale_model':
                r['parent_model']='f'*64;reject=not l.submit(r)
            elif attack=='forged_signature':
                sig=bytearray.fromhex(r['signature']);sig[rng.integers(len(sig))]^=1;r['signature']=sig.hex()
                reject=not l.submit(r)
            elif attack=='revoked_consent':
                l.revoke('A');reject=not l.submit(r)
            elif attack=='budget_overspend':
                l.budget['A']=10_000_000_000;l.open_round(1,r['parent_model'])
                reject=l.reserve('A',1,r['parent_model'],10_000_000_000) is None
            elif attack=='refund_laundering':
                before=l.spent['A'];reject=(not l.refund('A',0)) and l.spent['A']==before
            elif attack=='aggregate_tamper':
                ok,expected=verify_aggregate([a,a,a],[.3,.3,.4],a)
                assert ok;changed=expected.copy();changed.flat[rng.integers(changed.size)]+=.1
                reject=not verify_aggregate([a,a,a],[.3,.3,.4],changed)[0]
            else:
                # Honest credentials can sign arbitrary statistics. This is a
                # deliberate negative control; integrity is not poisoning detection.
                a=np.ones_like(a)*100;r=l.receipt('A',0,a)
                reject=not(l.submit(r) and l.receive(r,a))
            rejected+=int(reject)
        rows.append({'attack':attack,'trials':n,'rejected':rejected,'rejection_rate':rejected/n})
    # Verify concurrency at a nearly exhausted budget: exactly one wins.
    wins=[]
    for j in range(100):
        l=Ledger(budget_units=10_000_000_000);l.open_round(0,'a'*64);l.open_round(1,'b'*64)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(l.reserve,'A',t,p,10_000_000_000) for t,p in [(0,'a'*64),(1,'b'*64)]]
            wins.append(sum(f.result() is not None for f in futures))
        assert l.spent['A']==10_000_000_000
    # A refunded-account illustration separates actual exposure from entries.
    cap=.1;cost=.01;ledger_balance=0;exposure=0
    for _ in range(30):
        if ledger_balance+cost<=cap:
            ledger_balance+=cost;exposure+=cost;ledger_balance-=cost
    return rows,{'concurrent_pairs':len(wins),'single_winner_pairs':wins.count(1),
                 'naive_refund_recorded_rho':ledger_balance,'naive_refund_actual_rho':exposure,
                 'configured_rho_cap':cap}

def local_timings(n=1000):
    timings={'reserve':[],'sign_receipt':[],'submit_verify':[],'payload_verify':[]}
    byte_counts=[]
    for j in range(n):
        l,a,_=fixture();parent=model_hash(np.zeros_like(a));l.open_round(1,parent)
        t=time.perf_counter_ns();l.reserve('A',1,parent,10_000_000_000);timings['reserve'].append((time.perf_counter_ns()-t)/1e6)
        t=time.perf_counter_ns();r=l.receipt('A',1,a);timings['sign_receipt'].append((time.perf_counter_ns()-t)/1e6)
        byte_counts.append(len(canonical(r)))
        t=time.perf_counter_ns();assert l.submit(r);timings['submit_verify'].append((time.perf_counter_ns()-t)/1e6)
        t=time.perf_counter_ns();assert l.receive(r,a);timings['payload_verify'].append((time.perf_counter_ns()-t)/1e6)
    return {k:{'median_ms':float(np.median(v)),'p95_ms':float(np.quantile(v,.95))} for k,v in timings.items()},int(np.median(byte_counts))

def audit_reproduction():
    X,y=wearable_data();tr,te=train_test_split(np.arange(len(y)),test_size=.2,stratify=y,random_state=77)
    discrepancies=[];chains=[]
    for s in range(20):
        ids=partition(y[tr],3,1.,1000+s);weights=[len(a)/len(tr) for a in ids]
        cap_units=int(math.floor(rho_limit(4.)*SCALE))
        l=Ledger(budget_units=cap_units,expected_cost=cap_units//ROUNDS)
        maxdiff=[0.]
        def reserve_hook(t,parent,cost_units):
            ph=model_hash(parent);l.open_round(t,ph)
            for c in ['A','B','C']:
                assert l.reserve(c,t,ph,int(cost_units)) is not None
        def hook(t,parent,locals_,claimed,cost_units):
            ph=model_hash(parent)
            for c,a in zip(['A','B','C'],locals_):
                assert l.reservations[(c,t)]['parent_model']==ph
                r=l.receipt(c,t,a);assert l.submit(r) and l.receive(r,a)
            ok,expected=verify_aggregate(locals_,weights,claimed)
            assert ok;maxdiff[0]=max(maxdiff[0],float(np.max(np.abs(expected-claimed))))
            l._append({'type':'aggregate','round':t,'model_hash':model_hash(claimed),
                       'parent_model':ph,'client_set':['A','B','C'],'weights':weights})
        result=train(X[tr],y[tr],X[te],y[te],ids,4.,5000+s,
                     audit_hook=hook,audit_reserve_hook=reserve_hook)
        reference=train(X[tr],y[tr],X[te],y[te],ids,4.,5000+s)
        assert result['weights']==reference['weights']
        assert l.verify_chain(l.head)
        discrepancies.append(maxdiff[0]);chains.append(len(l.records))
        if s==0:
            example={'blocks':l.records,'trusted_head':l.head,'budgets':l.budget,'spent':l.spent}
    return {'matched_runs':20,'maximum_aggregate_difference':max(discrepancies),
            'identical_final_models':20,'events_per_training_run':chains[0]},example

def main():
    out=Path(__file__).resolve().parent/'results';out.mkdir(exist_ok=True)
    attacks,counters=attack_trials();pd.DataFrame(attacks).to_csv(out/'audit_attacks.csv',index=False)
    timings,receipt_bytes=local_timings()
    audit,example=audit_reproduction()
    result={**counters,'local_timings':timings,'median_receipt_bytes':receipt_bytes,**audit}
    (out/'audit_summary.json').write_text(json.dumps(result,indent=2))
    (out/'ledger_example.json').write_text(json.dumps(example,indent=2))
    print(pd.DataFrame(attacks).to_string(index=False));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
