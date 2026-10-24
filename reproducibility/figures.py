from pathlib import Path
import json, math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.ticker import FuncFormatter
from experiment import rho_limit,epsilon_from_rho,ROUNDS,DELTA

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'figures';OUT.mkdir(exist_ok=True)
DATA=ROOT/'results'
NAVY='#153A5B';TEAL='#007E87';ORANGE='#C66B12';RED='#B43143';LIGHT='#EDF3F7'
COLORS=[NAVY,TEAL,ORANGE,RED,'#62479A']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9.2,
                     'axes.spines.top':False,'axes.spines.right':False,
                     'axes.labelcolor':'#151515','text.color':'#151515',
                     'savefig.facecolor':'white','axes.grid':True,'grid.alpha':.16})

def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=320,bbox_inches='tight',pad_inches=.14)
    fig.savefig(OUT/(name+'.svg'),bbox_inches='tight',pad_inches=.14)
    plt.close(fig)

def box(ax,x,y,w,h,text,fc=LIGHT,ec=NAVY,size=9.2):
    p=FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.009,rounding_size=.012',
                    facecolor=fc,edgecolor=ec,linewidth=1.2)
    ax.add_patch(p);ax.text(x,y,text,ha='center',va='center',fontsize=size,color='#111111')

def arrow(ax,a,b,label=None,color=NAVY,dashed=False,offset=(0,0)):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=13,
                                color=color,linewidth=1.3,linestyle='--' if dashed else '-'))
    if label:ax.text((a[0]+b[0])/2+offset[0],(a[1]+b[1])/2+offset[1],label,
                     ha='center',va='center',fontsize=8,color=color,
                     bbox=dict(facecolor='white',edgecolor='none',pad=1.2))

def hospital(ax,x,y):
    ax.add_patch(Rectangle((x-.030,y-.027),.060,.054,facecolor='white',edgecolor=NAVY,linewidth=1.1))
    ax.add_patch(Rectangle((x-.026,y+.027),.052,.014,facecolor=NAVY))
    for dx in [-.018,.010]:
        for dy in [-.004,.010]:ax.add_patch(Rectangle((x+dx,y+dy),.009,.009,facecolor='#75A9C8'))
    ax.add_patch(Rectangle((x-.007,y-.027),.014,.018,facecolor=NAVY))
    ax.text(x,y+.035,'+',ha='center',va='center',color='white',fontsize=11,fontweight='bold')

def architecture():
    fig,ax=plt.subplots(figsize=(7.2,5.0));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    for i,x in enumerate([.16,.5,.84]):
        hospital(ax,x,.945);ax.text(x,.882,f'Institution {chr(65+i)}',ha='center',fontsize=10,fontweight='bold')
        box(ax,x,.782,.26,.112,'Local patient records\nFixed public transform\nRaw records stay local',size=8.7)
        arrow(ax,(x,.718),(x,.677))
        box(ax,x,.605,.26,.13,'Clip record gradients\nAdd noise every round\nSign protected model',fc='#EAF5F3',ec=TEAL,size=8.8)
    box(ax,.5,.375,.80,.15,'Off chain aggregation and independent audit\nVerify signatures and commitments\nRecompute the weighted model average',size=9.5)
    for x in [.16,.5,.84]:arrow(ax,(x,.529),(x,.458),'DP protected models' if x==.5 else None,color=TEAL,offset=(.11,0))
    box(ax,.5,.13,.91,.17,'Permissioned blockchain control plane\nAtomic budget reservation  •  Authorization epoch  •  Model commitments\nFour institutional validators  •  Three signatures per certificate',fc='#FFF4E9',ec=ORANGE,size=9.7)
    arrow(ax,(.35,.291),(.35,.223),'Signed receipts',color=ORANGE,dashed=True,offset=(-.12,0))
    arrow(ax,(.66,.223),(.66,.291),'Finalized authorization',color=ORANGE,dashed=True,offset=(.13,0))
    save(fig,'figure1_architecture')

def lifecycle():
    fig,ax=plt.subplots(figsize=(7.2,3.25));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
    xs=[.12,.37,.62,.87]
    labels=['AUTHORIZED\nRound policy fixed','RESERVED\nBudget charged','SUBMITTED\nReceipt committed','ACCEPTED\nModel verified']
    for x,label in zip(xs,labels):
        box(ax,x,.74,.20,.24,label,fc='#EAF5F3' if label.startswith('ACCEPTED') else LIGHT,size=8.8)
    for i in range(3):arrow(ax,(xs[i]+.115,.74),(xs[i+1]-.115,.74))
    box(ax,.69,.27,.38,.22,'REJECTED OR ABORTED\nBudget remains spent',fc='#FBEDEF',ec=RED,size=9)
    arrow(ax,(.37,.602),(.515,.39),'Timeout',color=RED,offset=(-.04,-.025))
    arrow(ax,(.62,.602),(.62,.39),'Invalid payload',color=RED,offset=(.16,0))
    ax.text(.05,.27,'Fresh noise requires\nanother reservation.\nA cached replay is not\na new noisy release.',fontsize=8.4,color=NAVY,va='center')
    save(fig,'figure2_lifecycle')

def _build_right_panel_from_ledger():
    """Fix 6: generate the right panel of Figure 6 from real Ledger runs,
    not from formulas.  We simulate 30 release attempts against a ρ cap of 0.10
    using the actual Ledger reserve/refund mechanics.
    """
    from protocol import (Ledger, _make_coordinator_sig, _make_client_sig,
                          fixture_key, SCALE)
    SCALE_RHO = 10**12
    cap_rho    = 0.10
    cost_rho   = 0.01
    cost_units = int(cost_rho * SCALE_RHO)
    budget     = int(cap_rho * SCALE_RHO)

    # --- Irreversible reservation (BAPFL behaviour) ---
    irrev_ledger = Ledger(budget_units=budget, clients=('A',),
                          expected_cost=cost_units)
    irrev_cumulative = []
    for attempt in range(30):
        parent = ('a'*62 + f'{attempt:02d}')
        roster = ['A']; counts = {'A': 100}
        csig   = _make_coordinator_sig(attempt, parent, roster, counts)
        rsig   = _make_client_sig('A', attempt, parent, cost_units)
        irrev_ledger.open_round(attempt, parent, roster, counts, coordinator_sig=csig)
        irrev_ledger.reserve('A', attempt, parent, cost_units, client_sig=rsig)
        irrev_cumulative.append(irrev_ledger.spent['A'] / SCALE_RHO)

    # --- Release-then-refund illustration (naive, wrong behaviour) ---
    refund_ledger = Ledger(budget_units=budget, clients=('A',),
                           expected_cost=cost_units)
    refund_cumulative = []
    refund_recorded   = []
    actual_exposure   = 0.0
    for attempt in range(30):
        parent = ('b'*62 + f'{attempt:02d}')
        roster = ['A']; counts = {'A': 100}
        csig   = _make_coordinator_sig(attempt, parent, roster, counts)
        rsig   = _make_client_sig('A', attempt, parent, cost_units)
        refund_ledger.open_round(attempt, parent, roster, counts, coordinator_sig=csig)
        result = refund_ledger.reserve('A', attempt, parent, cost_units, client_sig=rsig)
        if result is not None:
            actual_exposure += cost_rho       # a release actually occurred
            # simulate the wrong "refund" by decrementing spent manually
            refund_ledger.spent['A'] = max(0, refund_ledger.spent['A'] - cost_units)
        refund_cumulative.append(actual_exposure)
        refund_recorded.append(refund_ledger.spent['A'] / SCALE_RHO)

    return (np.arange(1, 31), irrev_cumulative,
            refund_cumulative, refund_recorded, cap_rho)

def result_figures():
    df=pd.read_csv(DATA/'utility_runs.csv');details=json.loads((DATA/'details.json').read_text())
    audit=json.loads((DATA/'audit_summary.json').read_text())
    fmt=FuncFormatter(lambda x,pos:f'{x:.2f}%')
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.2))
    for ax,dataset,label in zip(axes,['wearable','wdbc'],['Synthetic wearable surrogate','Public WDBC benchmark']):
        sub=df[(df.dataset==dataset)&df.epsilon.notna()]
        ag=sub.groupby('epsilon').accuracy.agg(['mean','std'])
        ax.errorbar(ag.index,ag['mean']*100,yerr=ag['std']*100,marker='o',color=TEAL,
                    capsize=3,lw=1.6,label='Private FL and audited private FL')
        base=df[(df.dataset==dataset)&(df.setting=='nonprivate')].accuracy.mean()*100
        ax.axhline(base,color=NAVY,ls='--',label='Matched nonprivate baseline')
        ax.set_xscale('log',base=2);ax.set_xticks([.5,1,2,4,8],['0.5','1','2','4','8'])
        ax.set(xlabel='Total privacy budget ε',ylabel='Test accuracy',title=label)
        ax.yaxis.set_major_formatter(fmt)
        ax.legend(fontsize=6.4,loc='lower right')
    fig.tight_layout(w_pad=1.8);save(fig,'figure3_privacy_utility')
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.2))
    for ax,dataset,label in zip(axes,['wearable','wdbc'],['Synthetic wearable surrogate','Public WDBC benchmark']):
        for c,setting,l in zip(COLORS[:4],['nonprivate','eps_0.5','eps_1','eps_4'],['Nonprivate','ε = 0.5','ε = 1','ε = 4']):
            h=details[f'{dataset}_{setting}']['history']
            ax.plot(np.arange(1,len(h)+1),np.asarray(h)*100,label=l,color=c,lw=1.3)
        ax.set(xlabel='Communication round',ylabel='Test accuracy',title=label)
        ax.yaxis.set_major_formatter(fmt);ax.legend(fontsize=7,loc='lower right')
    fig.tight_layout(w_pad=1.7);save(fig,'figure4_convergence')
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.25))
    for ax,dataset,labels in zip(axes,['wearable','wdbc'],[['Normal','Mild','Moderate','Severe'],['Malignant','Benign']]):
        cm=np.asarray(details[f'{dataset}_eps_4']['confusion']);norm=cm/cm.sum(axis=1)[:,None]
        ax.grid(False);ax.imshow(norm,cmap='Blues',vmin=0,vmax=1)
        for i in range(len(cm)):
            for j in range(len(cm)):ax.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=10,
                       color='white' if norm[i,j]>.6 else '#161616',fontweight='bold')
        ax.set_xticks(range(len(labels)),labels,rotation=25,ha='right');ax.set_yticks(range(len(labels)),labels)
        ax.set(xlabel='Predicted class',ylabel='True class',title='Wearable surrogate' if dataset=='wearable' else 'Public WDBC')
        for spine in ax.spines.values():spine.set_visible(False)
    fig.tight_layout(w_pad=2);save(fig,'figure5_confusion')

    attacks=pd.read_csv(DATA/'audit_attacks.csv')
    fig,axes=plt.subplots(1,2,figsize=(7.2,4))
    names=['Payload change','Replay','Stale parent','Forged signature','Revocation','Overspend','Refund attempt','Altered aggregate','Signed poisoning']
    axes[0].barh(np.arange(len(names)),attacks.rejection_rate*100,color=[TEAL]*8+[RED])
    axes[0].set_yticks(np.arange(len(names)),names,fontsize=8);axes[0].invert_yaxis()
    axes[0].set(xlabel='Rejection rate',xlim=(0,112),title='Executable protocol fault tests')
    axes[0].set_xticks([0,50,100])
    axes[0].xaxis.set_major_formatter(fmt)
    for i,x in enumerate(attacks.rejection_rate*100):axes[0].text(x+2,i,f'{x:.2f}%',va='center',fontsize=7.8)

    # Fix 6: right panel from real Ledger runs
    attempts, irrev, refund_actual, refund_recorded, cap_rho = _build_right_panel_from_ledger()
    axes[1].plot(attempts, irrev,           color=TEAL,  lw=2, label='Irreversible reservation (BAPFL)')
    axes[1].plot(attempts, refund_actual,   color=RED,   lw=2, label='Release then refund (actual exposure)')
    axes[1].plot(attempts, refund_recorded, color=NAVY,  lw=1.4, ls=':', label='Refunded ledger counter')
    axes[1].axhline(cap_rho, color='#777777', ls='--', label=f'Configured ρ cap ({cap_rho})')
    axes[1].set(xlabel='Release attempt',
                ylabel='Actual or recorded cumulative ρ',
                title='Refund attack on privacy accounting\n(from real Ledger runs)')
    axes[1].legend(fontsize=7, loc='upper left'); axes[1].set_ylim(-.015, .325)
    fig.tight_layout(w_pad=1.8);save(fig,'figure6_audit_budget')

    fig,axes=plt.subplots(1,2,figsize=(7.2,3.35))
    tt=audit['local_timings'];steps=['reserve','sign_receipt','submit_verify','payload_verify']
    x=np.arange(4)
    axes[0].bar(x-.16,[tt[s]['median_ms'] for s in steps],.32,label='Median',color=TEAL)
    axes[0].bar(x+.16,[tt[s]['p95_ms'] for s in steps],.32,label='95th percentile',color=NAVY)
    axes[0].set_xticks(x,['Reserve','Sign','Submit','Verify'],rotation=20,ha='right')
    axes[0].set(ylabel='Local emulator time in milliseconds',title='Measured cryptographic operation cost')
    axes[0].legend(fontsize=7)
    dimensions=np.array([17,128,1024,10000]);payload=8*4*(dimensions+1)
    receipt=audit['median_receipt_bytes']
    axes[1].plot(dimensions,payload,marker='o',color=NAVY,label='Full four-class model payload')
    axes[1].axhline(receipt,color=TEAL,ls='--',label=f'Signed receipt only  {receipt} bytes')
    axes[1].set_xscale('log');axes[1].set_yscale('log')
    axes[1].set_xticks(dimensions,[str(x) for x in dimensions]);axes[1].set(xlabel='Number of input features',ylabel='Serialized bytes',title='Payload size and fixed receipt size')
    axes[1].legend(fontsize=6.6,loc='upper left')
    fig.tight_layout(w_pad=1.7);save(fig,'figure7_cost_storage')

def main():architecture();lifecycle();result_figures();print('Seven publication figures generated')
if __name__=='__main__':main()
