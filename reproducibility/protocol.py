"""Signed ledger emulator and privacy reservation state machine.

This is a single-process emulator, not a deployed Fabric or PBFT network.
Three-of-four signatures emulate certificates, not network consensus.

Ledger hash values are deterministic within one Python/platform combination
but may differ across platforms due to float byte-order and library versions.
"""
from pathlib import Path
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
import copy, hashlib, json, time, math
import numpy as np
import pandas as pd
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.exceptions import InvalidSignature
from experiment import (train,wearable_data,partition,rho_limit,ROUNDS,ETA,L2,DATASET_HP)
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

# Coordinator key for open_round authentication (Fix 5)
COORDINATOR_KEY = fixture_key('coordinator')

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
        # Fix 2: roster and weights anchored per round
        self.round_roster={}    # round -> [client, ...]
        self.round_sample_n={}  # round -> {client: n_k}
        self.accept_hashes={}   # (client, round) -> model_hash (Fix 3)

    def _append(self,event):
        body={'height':len(self.records),'parent':self.head,'event':event}
        h=digest(canonical(body))
        cert=[{'validator':j,'signature':self.validators[j].sign(bytes.fromhex(h)).hex()} for j in range(3)]
        block={**body,'hash':h,'certificate':cert}
        self.records.append(block);self.head=h
        return h

    def open_round(self, t, parent, roster, sample_counts, coordinator_sig):
        """Open a training round.  roster and per-client sample counts are
        written to the ledger so weights can be derived inside the verifier.
        coordinator_sig is MANDATORY (no default None) and must verify against COORDINATOR_KEY.
        """
        t = int(t)
        with self.lock:
            if t in self.round_parent: raise ValueError('round_already_open')
            if coordinator_sig is None:
                raise ValueError('missing_coordinator_sig')
            payload = canonical({'round': t, 'parent': parent,
                                 'roster': list(roster),
                                 'sample_counts': {c: int(n) for c, n in sample_counts.items()}})
            try:
                COORDINATOR_KEY.public_key().verify(coordinator_sig, payload)
            except (InvalidSignature, ValueError) as exc:
                raise ValueError('invalid_coordinator_sig') from exc
            self.round_parent[t] = parent
            self.round_roster[t] = list(roster)
            self.round_sample_n[t] = {c: int(n) for c, n in sample_counts.items()}
            self._append({'type': 'open_round', 'round': t, 'parent': parent,
                          'roster': list(roster),
                          'sample_counts': self.round_sample_n[t]})

    def reserve(self, client, t, parent, cost, client_sig):
        """Reserve budget for one round.  Validates argument types and atomically
        appends before updating spent (roll back on exception).
        client_sig is MANDATORY (no default None) and verifies the reservation request.
        """
        t = int(t)
        with self.lock:
            self.reason=None
            if not isinstance(cost, int) or cost <= 0:
                self.reason = 'invalid_cost'; return None
            key=(client, t)
            if client not in self.active or not self.active[client]:
                self.reason='revoked'; return None
            if self.round_parent.get(t)!=parent:
                self.reason='stale_parent'; return None
            if client_sig is None:
                self.reason = 'signature'; return None
            req_payload = canonical({'client': client, 'round': t,
                                     'parent': parent, 'cost': cost})
            try:
                self.client_keys[client].public_key().verify(client_sig, req_payload)
            except (InvalidSignature, ValueError):
                self.reason = 'signature'; return None
            if key in self.reservations:
                self.reason='duplicate_reservation'; return None
            if cost!=self.expected_cost:
                self.reason='policy_cost_mismatch'; return None
            if self.spent[client]+cost>self.budget[client]:
                self.reason='budget_exhausted'; return None
            record={'client':client,'round':t,'parent_model':parent,'cost_units':cost,
                    'consent_epoch':self.epoch[client],'state':'reserved'}
            # Fix 4: append event BEFORE updating spent; roll back on exception
            try:
                self._append({'type':'reserve',**record})
                self.reservations[key]=record
                self.spent[client]+=cost   # only after successful append
            except Exception:
                # roll back: remove record if it was inserted
                self.reservations.pop(key, None)
                raise
            return copy.deepcopy(record)

    def receipt(self,client,t,local_model):
        t = int(t)  # Fix 4
        r=self.reservations[(client,t)]
        nonce=digest(canonical({'client':client,'round':t,'nonce_fixture':2026}))
        # Commitments cover only already DP-protected model parameters.
        r={k:v for k,v in r.items() if k!='state'}
        r.update({'commitment':digest(bytes.fromhex(nonce)+array_bytes(local_model)),
                  'nonce':nonce,'schema':'softmax-f64-v1'})
        r['signature']=self.client_keys[client].sign(canonical(r)).hex()
        return r

    def submit(self, r):
        with self.lock:
            self.reason = None
            if not isinstance(r, dict):
                self.reason = 'malformed_receipt'; return False
            client = r.get('client')
            round_val = r.get('round')
            if not isinstance(client, str) or round_val is None:
                self.reason = 'malformed_receipt'; return False
            try:
                t = int(round_val)
            except (ValueError, TypeError):
                self.reason = 'malformed_receipt'; return False
            key = (client, t)
            reserved = self.reservations.get(key)
            if reserved is None: self.reason = 'no_reservation'; return False
            if client not in self.active or not self.active[client] or r.get('consent_epoch') != self.epoch.get(client):
                self.reason = 'revoked'; return False
            if r.get('parent_model') != self.round_parent.get(t):
                self.reason = 'stale_parent'; return False
            for field in ['cost_units', 'consent_epoch', 'client', 'round', 'parent_model']:
                if r.get(field) != reserved.get(field):
                    self.reason = 'reservation_mismatch'; return False
            if key in self.submissions:
                self.reason = 'replay'; return False
            sig_hex = r.get('signature')
            if not isinstance(sig_hex, str):
                self.reason = 'signature'; return False
            unsigned = {k: v for k, v in r.items() if k != 'signature'}
            try:
                sig_bytes = bytes.fromhex(sig_hex)
                self.client_keys[client].public_key().verify(sig_bytes, canonical(unsigned))
            except (InvalidSignature, ValueError, KeyError):
                self.reason = 'signature'; return False
            self.submissions[key] = copy.deepcopy(r)
            reserved['state'] = 'submitted'
            self._append({'type': 'submit', **r})
            return True

    def receive(self, r, a):
        """Verify the off-chain payload and accept the update.
        Item 6: append the accept event first, then update state, with rollback.
        submit()/receive(): return False with a reason on malformed input instead of raising.
        """
        with self.lock:
            self.reason = None
            if not isinstance(r, dict):
                self.reason = 'malformed_receipt'; return False
            if not isinstance(a, np.ndarray):
                self.reason = 'malformed_payload'; return False
            client = r.get('client')
            round_val = r.get('round')
            if not isinstance(client, str) or round_val is None:
                self.reason = 'malformed_receipt'; return False
            try:
                t = int(round_val)
            except (ValueError, TypeError):
                self.reason = 'malformed_receipt'; return False
            key = (client, t)
            if key in self.used:
                self.reason = 'replay'; return False
            if self.submissions.get(key) != r:
                self.reason = 'uncommitted_receipt'; return False
            if client not in self.active or not self.active[client] or r.get('consent_epoch') != self.epoch.get(client):
                self.reason = 'revoked'; return False
            if not np.isfinite(a).all():
                self.reason = 'nonfinite'; return False
            nonce_hex = r.get('nonce')
            commitment = r.get('commitment')
            if not isinstance(nonce_hex, str) or not isinstance(commitment, str):
                self.reason = 'malformed_receipt'; return False
            try:
                nonce_bytes = bytes.fromhex(nonce_hex)
            except (ValueError, TypeError):
                self.reason = 'malformed_receipt'; return False
            if digest(nonce_bytes + array_bytes(a)) != commitment:
                self.reason = 'commitment'; return False

            # Item 6: append the accept event first, then update state, with rollback on exception
            mh = model_hash(a)
            accept_event = {'type': 'accept',
                            'client': key[0],
                            'round': key[1],
                            'model_hash': mh,
                            'commitment': commitment}
            try:
                self._append(accept_event)
                # Only update state after successful append:
                self.used.add(key)
                self.accept_hashes[key] = mh
                if key in self.reservations:
                    self.reservations[key]['state'] = 'accepted'
            except Exception:
                # Rollback state on append failure
                self.used.discard(key)
                self.accept_hashes.pop(key, None)
                if key in self.reservations:
                    self.reservations[key]['state'] = 'submitted'
                raise
            return True

    def revoke(self,c):
        with self.lock:
            self.active[c]=False;self.epoch[c]+=1
            self._append({'type':'revoke','client':c,'consent_epoch':self.epoch[c]})

    def refund(self,client,t):
        self.reason='refund_forbidden';return False

    def anchor_aggregate(self, t, models, claimed, weights=None):
        """Fix 2: verify the aggregate before appending the event.

        Weights are DERIVED from the frozen roster and sample counts.  Any
        caller-supplied weight vector is rejected if len(weights) != len(roster)
        or if any weight does not match.  Requires len(models) == len(roster).
        Compares sha256 (model_hash) of each supplied model with the accept event
        model_hash and rejects on mismatch.  Rejects the round unless all roster
        clients were accepted (no renormalising).  Writes accepted_clients strictly
        in roster order (never list(set)).
        """
        t = int(t)
        with self.lock:
            roster   = self.round_roster.get(t)
            sample_n = self.round_sample_n.get(t)
            if roster is None or sample_n is None:
                raise ValueError('no_open_round')
            if len(models) != len(roster):
                raise ValueError('wrong_length_models')
            if weights is not None and len(weights) != len(roster):
                raise ValueError('wrong_length_weights')

            N = sum(sample_n[c] for c in roster)
            derived_weights = [sample_n[c] / N for c in roster]
            if abs(sum(derived_weights) - 1.0) > 1e-9:
                raise ValueError('weights_do_not_sum_to_one')

            # Reject caller-supplied weights that differ from derived
            if weights is not None:
                for dw, cw in zip(derived_weights, weights):
                    if abs(dw - cw) > 1e-9:
                        raise ValueError('weight_mismatch')

            # Item 3: reject round unless all roster clients were accepted (no renormalisation)
            # and compare sha256 of each supplied model with accept event's model_hash
            for c, m in zip(roster, models):
                key = (c, t)
                if key not in self.accept_hashes:
                    raise ValueError(f'missing_roster_client: {c}')
                if model_hash(m) != self.accept_hashes[key]:
                    raise ValueError(f'model_hash_mismatch for client {c}')

            expected = np.sum(
                np.array(models) * np.asarray(derived_weights)[:, None, None],
                axis=0)
            diff = float(np.max(np.abs(expected - claimed)))
            if diff > 1e-12:
                raise ValueError(f'aggregate_mismatch diff={diff:.3e}')

            # Write accepted_clients in roster order, never list(set)
            accepted_clients = [c for c in roster]
            client_hashes = {c: self.accept_hashes[(c, t)] for c in roster}
            self._append({'type': 'aggregate', 'round': t,
                          'model_hash': model_hash(claimed),
                          'parent': self.round_parent[t],
                          'accepted_clients': accepted_clients,
                          'client_model_hashes': client_hashes,
                          'weights': derived_weights})
            return True

    def verify_chain(self, trusted_head=None):
        """Fix 3: replay the state-machine rules:
        - spent never exceeds budget
        - reserve -> submit -> accept order is enforced
        - parent model must match the open_round record
        - aggregate is only over accepted clients
        """
        previous='0'*64
        spent_replay   = {}  # client -> cumulative
        budget_replay  = {}  # client -> budget
        state_machine  = {}  # (client, round) -> state
        round_parent_r = {}
        round_accepted = {}  # round -> set of accepted clients
        round_roster_r = {}  # round -> roster list
        round_sample_n_r = {} # round -> {client: sample_count}
        round_accept_hashes_r = {} # round -> {client: model_hash}

        for i, r in enumerate(self.records):
            # --- hash-chain integrity ---
            body={k:r[k] for k in ['height','parent','event']}
            if r['height']!=i or r['parent']!=previous or digest(canonical(body))!=r['hash']:
                return False
            seen=set()
            for item in r['certificate']:
                j=item['validator']
                if j in seen or not 0<=j<4:return False
                try:self.validators[j].public_key().verify(bytes.fromhex(item['signature']),bytes.fromhex(r['hash']))
                except (InvalidSignature,ValueError):return False
                seen.add(j)
            if len(seen)<3:return False

            # --- state-machine rules ---
            ev = r['event']
            etype = ev.get('type')

            if etype == 'open_round':
                rnd = int(ev['round'])
                round_parent_r[rnd] = ev['parent']
                round_accepted[rnd] = set()
                round_roster_r[rnd] = list(ev.get('roster', []))
                round_sample_n_r[rnd] = {c: int(n) for c, n in ev.get('sample_counts', {}).items()}
                round_accept_hashes_r[rnd] = {}

            elif etype == 'reserve':
                c = ev['client']; rnd = int(ev['round'])
                if c not in budget_replay:
                    budget_replay[c] = self.budget[c]
                    spent_replay[c]  = 0
                # parent must match open_round
                if round_parent_r.get(rnd) != ev.get('parent_model'):
                    return False
                spent_replay[c] += ev['cost_units']
                if spent_replay[c] > budget_replay[c]:
                    return False
                state_machine[(c, rnd)] = 'reserved'

            elif etype == 'submit':
                key = (ev['client'], int(ev['round']))
                if state_machine.get(key) != 'reserved':
                    return False
                state_machine[key] = 'submitted'

            elif etype == 'accept':
                rnd = int(ev['round'])
                key = (ev['client'], rnd)
                if state_machine.get(key) != 'submitted':
                    return False
                state_machine[key] = 'accepted'
                round_accepted[rnd].add(ev['client'])
                if rnd in round_accept_hashes_r:
                    round_accept_hashes_r[rnd][ev['client']] = ev.get('model_hash')

            elif etype == 'aggregate':
                rnd = int(ev['round'])
                roster = round_roster_r.get(rnd)
                sample_n = round_sample_n_r.get(rnd)
                if roster is None or sample_n is None:
                    return False

                acc_clients = ev.get('accepted_clients', [])
                # Must match exact roster in roster order
                if acc_clients != roster:
                    return False
                # Check each accepted client actually has an accept event
                accept_hashes_rnd = round_accept_hashes_r.get(rnd, {})
                if any(c not in accept_hashes_rnd for c in acc_clients):
                    return False

                # Check weights against open_round sample counts
                N = sum(sample_n[c] for c in acc_clients)
                if N <= 0:
                    return False
                expected_weights = [sample_n[c] / N for c in acc_clients]
                actual_weights = ev.get('weights', [])
                if len(actual_weights) != len(expected_weights):
                    return False
                for ew, aw in zip(expected_weights, actual_weights):
                    if abs(ew - aw) > 1e-9:
                        return False

                # Check client model hashes recorded in aggregate match accept events
                if 'client_model_hashes' in ev:
                    for c, h in ev['client_model_hashes'].items():
                        if accept_hashes_rnd.get(c) != h:
                            return False

                # Check parent and valid model_hash format
                if ev.get('parent') != round_parent_r.get(rnd):
                    return False
                mh = ev.get('model_hash', '')
                if not isinstance(mh, str) or len(mh) != 64:
                    return False

            previous = r['hash']
        return trusted_head is None or previous == trusted_head


def verify_aggregate(models,weights,claimed,tol=1e-12):
    expected=np.sum(np.array(models)*np.asarray(weights)[:,None,None],axis=0)
    return bool(np.max(np.abs(expected-claimed))<=tol),expected

def _make_coordinator_sig(t, parent, roster, sample_counts):
    """Helper: sign an open_round payload with the fixture coordinator key."""
    payload = canonical({'round': int(t), 'parent': parent,
                         'roster': list(roster),
                         'sample_counts': {c: int(n) for c, n in sample_counts.items()}})
    return COORDINATOR_KEY.sign(payload)

def _make_client_sig(client, t, parent, cost):
    """Helper: sign a reserve payload with the fixture client key."""
    key = fixture_key('client-' + client)
    payload = canonical({'client': client, 'round': int(t),
                         'parent': parent, 'cost': int(cost)})
    return key.sign(payload)

def fixture():
    a=np.arange(12,dtype=float).reshape(3,4)/10
    l=Ledger()
    parent=model_hash(np.zeros_like(a))
    roster=['A']
    counts={'A':100}
    csig = _make_coordinator_sig(0, parent, roster, counts)
    l.open_round(0, parent, roster, counts, coordinator_sig=csig)
    rsig = _make_client_sig('A', 0, parent, 10_000_000_000)
    l.reserve('A', 0, parent, 10_000_000_000, client_sig=rsig)
    r=l.receipt('A',0,a)
    return l,a,r

def attack_trials(n=1000):
    """Fix 6: every test FAILS when its check is removed.
    Asserts rejection reason.  Uses distinct models/weights in aggregate test.
    Includes a property test that 'spent' never decreases.
    """
    rows=[]
    attacks=['payload_tamper','receipt_replay','stale_model','forged_signature',
             'revoked_consent','budget_overspend','refund_laundering','aggregate_tamper',
             'dropped_clients','fake_models','wrong_length_weights',
             'unsigned_calls','signed_poisoned_update']
    rng=np.random.default_rng(440)

    for attack in attacks:
        rejected=0
        for trial in range(n):
            l,a,r=fixture()
            if attack=='payload_tamper':
                # submit first, then tamper the payload before receive
                assert l.submit(r)
                a_tampered=a.copy(); a_tampered.flat[rng.integers(a.size)]+=rng.uniform(.01,1)
                reject=not l.receive(r,a_tampered)
                assert reject, "payload_tamper was not rejected"
                assert l.reason=='commitment', f"expected 'commitment' got {l.reason!r}"
            elif attack=='receipt_replay':
                assert l.submit(r) and l.receive(r,a)
                reject=not l.receive(r,a)
                assert reject, "receipt_replay was not rejected"
                assert l.reason=='replay', f"expected 'replay' got {l.reason!r}"
            elif attack=='stale_model':
                r2=dict(r);r2['parent_model']='f'*64
                reject=not l.submit(r2)
                assert reject, "stale_model was not rejected"
                assert l.reason=='stale_parent', f"expected 'stale_parent' got {l.reason!r}"
            elif attack=='forged_signature':
                r2=dict(r);sig=bytearray.fromhex(r2['signature']);sig[rng.integers(len(sig))]^=1;r2['signature']=sig.hex()
                reject=not l.submit(r2)
                assert reject, "forged_signature was not rejected"
                assert l.reason=='signature', f"expected 'signature' got {l.reason!r}"
            elif attack=='revoked_consent':
                l.revoke('A');reject=not l.submit(r)
                assert reject, "revoked_consent was not rejected"
                assert l.reason=='revoked', f"expected 'revoked' got {l.reason!r}"
            elif attack=='budget_overspend':
                l.budget['A']=10_000_000_000
                parent2='b'*64
                roster2=['A']; counts2={'A':100}
                csig2 = _make_coordinator_sig(1, parent2, roster2, counts2)
                l.open_round(1, parent2, roster2, counts2, coordinator_sig=csig2)
                rsig2 = _make_client_sig('A', 1, parent2, 10_000_000_000)
                reject=l.reserve('A',1,parent2,10_000_000_000,client_sig=rsig2) is None
                assert reject, "budget_overspend was not rejected"
                assert l.reason=='budget_exhausted', f"expected 'budget_exhausted' got {l.reason!r}"
            elif attack=='refund_laundering':
                before=l.spent['A'];reject=(not l.refund('A',0)) and l.spent['A']==before
                assert reject, "refund_laundering was not rejected"
                assert l.reason=='refund_forbidden', f"expected 'refund_forbidden' got {l.reason!r}"
            elif attack=='aggregate_tamper':
                # Fix 6: use DISTINCT models and weights
                a1=np.ones((3,4))*0.1; a2=np.ones((3,4))*0.5; a3=np.ones((3,4))*0.9
                w=[.3,.3,.4]
                ok,expected=verify_aggregate([a1,a2,a3],w,sum(wi*ai for wi,ai in zip(w,[a1,a2,a3])))
                assert ok
                changed=expected.copy();changed.flat[rng.integers(changed.size)]+=.1
                reject=not verify_aggregate([a1,a2,a3],w,changed)[0]
                assert reject, "aggregate_tamper was not rejected"
            elif attack=='dropped_clients':
                # Open round with roster ['A', 'B'] but only client 'A' accepted
                p_drop = 'd'*64
                roster_drop = ['A', 'B']
                counts_drop = {'A': 50, 'B': 50}
                csig_d = _make_coordinator_sig(3, p_drop, roster_drop, counts_drop)
                l.open_round(3, p_drop, roster_drop, counts_drop, coordinator_sig=csig_d)
                rsig_a = _make_client_sig('A', 3, p_drop, 10_000_000_000)
                l.reserve('A', 3, p_drop, 10_000_000_000, client_sig=rsig_a)
                rec_a = l.receipt('A', 3, a)
                assert l.submit(rec_a) and l.receive(rec_a, a)
                # Client 'B' dropped; attempt to aggregate round 3 must fail
                try:
                    l.anchor_aggregate(3, [a, a], a, weights=[0.5, 0.5])
                    reject = False
                except ValueError:
                    reject = True
                assert reject, "anchor_aggregate should reject dropped client"
            elif attack=='fake_models':
                # Client 'A' accepted model 'a', coordinator presents fake model 'a+1'
                assert l.submit(r) and l.receive(r, a)
                a_fake = a + 1.0
                try:
                    l.anchor_aggregate(0, [a_fake], a_fake, weights=[1.0])
                    reject = False
                except ValueError:
                    reject = True
                assert reject, "anchor_aggregate should reject model_hash mismatch"
            elif attack=='wrong_length_weights':
                # Roster length is 1, caller supplies weights of length 2
                assert l.submit(r) and l.receive(r, a)
                try:
                    l.anchor_aggregate(0, [a], a, weights=[0.5, 0.5])
                    reject = False
                except ValueError:
                    reject = True
                assert reject, "anchor_aggregate should reject wrong length weights"
            elif attack=='unsigned_calls':
                # 1. Test unsigned open_round fails
                unsigned_open_failed = False
                try:
                    l.open_round(2, 'c'*64, ['A'], {'A': 100}, coordinator_sig=None)
                except ValueError:
                    unsigned_open_failed = True
                assert unsigned_open_failed, "unsigned open_round should have raised ValueError"
                # 2. Open round 2 properly with coordinator sig
                csig_2 = _make_coordinator_sig(2, 'c'*64, ['A'], {'A': 100})
                l.open_round(2, 'c'*64, ['A'], {'A': 100}, coordinator_sig=csig_2)
                # 3. Test unsigned reserve fails with reason 'signature'
                unsigned_res = l.reserve('A', 2, 'c'*64, 10_000_000_000, client_sig=None)
                assert unsigned_res is None and l.reason == 'signature', f"expected 'signature' got {l.reason!r}"
                reject = unsigned_open_failed and (unsigned_res is None)
            else:  # signed_poisoned_update — intentional negative control
                a_poison=np.ones_like(a)*100;r_poison=l.receipt('A',0,a_poison)
                reject=not(l.submit(r_poison) and l.receive(r_poison,a_poison))
                # This must NOT be rejected — it's a negative control
                assert not reject, "signed_poisoned_update should have been accepted"
            rejected+=int(reject)
        rows.append({'attack':attack,'trials':n,'rejected':rejected,'rejection_rate':rejected/n})

    # Fix 7: property test — compare spent between consecutive operations
    property_ledger=Ledger(budget_units=50_000_000_000, expected_cost=10_000_000_000)
    prev_spent = dict(property_ledger.spent)
    def _assert_monotonic(step_name):
        for c in property_ledger.spent:
            assert property_ledger.spent[c] >= prev_spent[c], \
                f"spent decreased after {step_name} for client {c}: {prev_spent[c]} -> {property_ledger.spent[c]}"
        prev_spent.update(property_ledger.spent)

    for t2 in range(3):
        parent_t = 'a'*62+f'{t2:02d}'
        roster_t=['A']; counts_t={'A':100}
        csig_t=_make_coordinator_sig(t2,parent_t,roster_t,counts_t)
        property_ledger.open_round(t2,parent_t,roster_t,counts_t,coordinator_sig=csig_t)
        _assert_monotonic('open_round')

        rsig_t=_make_client_sig('A',t2,parent_t,10_000_000_000)
        res=property_ledger.reserve('A',t2,parent_t,10_000_000_000,client_sig=rsig_t)
        _assert_monotonic('reserve')

        if res is not None:
            rec = property_ledger.receipt('A', t2, a)
            _assert_monotonic('receipt')
            property_ledger.submit(rec)
            _assert_monotonic('submit')
            property_ledger.receive(rec, a)
            _assert_monotonic('receive')
            property_ledger.anchor_aggregate(t2, [a], a, weights=[1.0])
            _assert_monotonic('anchor_aggregate')
            property_ledger.refund('A', t2)
            _assert_monotonic('refund')
    print("Property test: spent monotonically non-decreasing between consecutive operations — OK", flush=True)

    # Verify concurrency at a nearly exhausted budget: exactly one wins.
    wins=[]
    for j in range(100):
        l=Ledger(budget_units=10_000_000_000)
        roster_c=['A']; counts_c={'A':100}
        csig_0=_make_coordinator_sig(0,'a'*64,roster_c,counts_c)
        csig_1=_make_coordinator_sig(1,'b'*64,roster_c,counts_c)
        l.open_round(0,'a'*64,roster_c,counts_c,coordinator_sig=csig_0)
        l.open_round(1,'b'*64,roster_c,counts_c,coordinator_sig=csig_1)
        rsig_0=_make_client_sig('A',0,'a'*64,10_000_000_000)
        rsig_1=_make_client_sig('A',1,'b'*64,10_000_000_000)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(l.reserve,'A',t2,p2,10_000_000_000,rsig2)
                     for t2,p2,rsig2 in [(0,'a'*64,rsig_0),(1,'b'*64,rsig_1)]]
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
        l,a,_=fixture()
        parent=model_hash(np.zeros_like(a))
        roster=['A']; counts={'A':100}
        csig=_make_coordinator_sig(1,parent,roster,counts)
        l.open_round(1,parent,roster,counts,coordinator_sig=csig)
        rsig=_make_client_sig('A',1,parent,10_000_000_000)
        t_=time.perf_counter_ns();l.reserve('A',1,parent,10_000_000_000,client_sig=rsig);timings['reserve'].append((time.perf_counter_ns()-t_)/1e6)
        t_=time.perf_counter_ns();r=l.receipt('A',1,a);timings['sign_receipt'].append((time.perf_counter_ns()-t_)/1e6)
        byte_counts.append(len(canonical(r)))
        t_=time.perf_counter_ns();assert l.submit(r);timings['submit_verify'].append((time.perf_counter_ns()-t_)/1e6)
        t_=time.perf_counter_ns();assert l.receive(r,a);timings['payload_verify'].append((time.perf_counter_ns()-t_)/1e6)
    return {k:{'median_ms':float(np.median(v)),'p95_ms':float(np.quantile(v,.95))} for k,v in timings.items()},int(np.median(byte_counts))

def get_dataset_hp(dataset_name='wearable'):
    """Single source of truth for hyperparameters: loads tuned hyperparameters
    from results/config.json if available, or falls back to DATASET_HP from experiment.py.
    """
    cfg_file = Path(__file__).resolve().parent / 'results' / 'config.json'
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text())
            if 'tuned_hp' in cfg and dataset_name in cfg['tuned_hp']:
                return cfg['tuned_hp'][dataset_name]
        except Exception:
            pass
    return DATASET_HP[dataset_name]

def audit_reproduction():
    hp = get_dataset_hp('wearable')
    rounds = hp['rounds']
    X,y=wearable_data();tr,te=train_test_split(np.arange(len(y)),test_size=.2,stratify=y,random_state=77)
    discrepancies=[];chains=[];ledger_runs=[]
    for s in range(20):
        ids=partition(y[tr],3,1.,1000+s);weights=[len(a)/len(tr) for a in ids]
        cap_units=int(math.floor(rho_limit(4.)*SCALE))
        l=Ledger(budget_units=cap_units,expected_cost=cap_units//rounds)
        maxdiff=[0.]
        roster=['A','B','C']
        sample_counts={'A':len(ids[0]),'B':len(ids[1]),'C':len(ids[2])}

        def reserve_hook(t,parent,cost_units):
            ph=model_hash(parent)
            csig=_make_coordinator_sig(t,ph,roster,sample_counts)
            l.open_round(t,ph,roster,sample_counts,coordinator_sig=csig)
            for c in roster:
                rsig=_make_client_sig(c,t,ph,int(cost_units))
                assert l.reserve(c,t,ph,int(cost_units),client_sig=rsig) is not None

        def hook(t,parent,locals_,claimed,cost_units):
            ph=model_hash(parent)
            for c,a in zip(roster,locals_):
                assert l.reservations[(c,t)]['parent_model']==ph
                r=l.receipt(c,t,a);assert l.submit(r) and l.receive(r,a)
            # Fix 2: derive weights from ledger roster, verify then anchor
            N_total = sum(sample_counts[c] for c in roster)
            derived_w = [sample_counts[c]/N_total for c in roster]
            ok,expected=verify_aggregate(locals_,derived_w,claimed)
            assert ok;maxdiff[0]=max(maxdiff[0],float(np.max(np.abs(expected-claimed))))
            l.anchor_aggregate(t, locals_, claimed, weights=derived_w)

        result=train(X[tr],y[tr],X[te],y[te],ids,4.,5000+s,
                     audit_hook=hook,audit_reserve_hook=reserve_hook,**hp)
        reference=train(X[tr],y[tr],X[te],y[te],ids,4.,5000+s,**hp)
        assert result['weights']==reference['weights']
        assert l.verify_chain(l.head)
        discrepancies.append(maxdiff[0]);chains.append(len(l.records))
        ledger_runs.append(l)
        if s==0:
            example={'blocks':l.records,'trusted_head':l.head,'budgets':l.budget,'spent':l.spent}
    return {'matched_runs':20,'maximum_aggregate_difference':max(discrepancies),
            'identical_final_models':20,'events_per_training_run':chains[0]},example,ledger_runs

def main():
    out=Path(__file__).resolve().parent/'results';out.mkdir(exist_ok=True)
    attacks,counters=attack_trials();pd.DataFrame(attacks).to_csv(out/'audit_attacks.csv',index=False)
    timings,receipt_bytes=local_timings()
    audit,example,ledger_runs=audit_reproduction()
    result={**counters,'local_timings':timings,'median_receipt_bytes':receipt_bytes,**audit,
            'ledger_runs_count':len(ledger_runs),
            'audit_hyperparameters':get_dataset_hp('wearable')}
    (out/'audit_summary.json').write_text(json.dumps(result,indent=2))
    (out/'ledger_example.json').write_text(json.dumps(example,indent=2))
    print(pd.DataFrame(attacks).to_string(index=False));print(json.dumps(result,indent=2))

if __name__=='__main__':main()
