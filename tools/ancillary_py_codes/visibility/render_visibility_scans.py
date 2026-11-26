"""Render a restartable plot PDF for each scan from the visibility checkpoints.

Run after both collectors and assess_visibilities.py. Existing PDFs with matching
inputs and renderer modification times are skipped. The report assembler adds
an index, interpretation and flag selections around these plot sheets.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

def spans(coords, selected, halfwidth):
    """Compact projection of selected cells, retaining real gaps."""
    values=np.sort(np.asarray(coords)[selected])
    if not len(values):return []
    return [(g[0]-halfwidth,g[-1]+halfwidth) for g in np.split(values,np.flatnonzero(np.diff(values)>2.02*halfwidth)+1)]


import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator,FormatStrFormatter

from visibility_preview import POL_COLORS,INK


def cell(fig,slot,x,z,pols,title,domain,native,hits,centers,duration,missing):
    grid=slot.subgridspec(2,1,hspace=.10)
    upper=fig.add_subplot(grid[0]); lower=fig.add_subplot(grid[1],sharex=upper)
    upper.set_title(title,loc='left',fontsize=8,weight='bold',pad=2)
    is_time=domain=='time'
    if native and not is_time and z is not None:
        amplitudes,phases=z
    elif z is not None:
        amplitudes,phases=abs(z),np.angle(z,deg=True)
    if z is None or not np.isfinite(amplitudes).any():
        upper.text(.5,.5,'No valid samples' if is_time or not native else 'No channel spectrum',
                   ha='center',va='center',transform=upper.transAxes,fontsize=7)
    elif native and is_time:
        ti,fi,pi=np.nonzero(np.isfinite(z))
        order=np.random.default_rng(17).permutation(len(ti));ti,fi,pi=ti[order],fi[order],pi[order]
        colors=np.array([matplotlib.colors.to_rgba(POL_COLORS[p]) for p in pols])[pi]
        for ax,values in [(upper,amplitudes*1000),(lower,phases)]:
            ax.scatter(x[ti],values[ti,fi,pi],c=colors,s=.42,lw=0,alpha=.60,rasterized=True)
    else:
        for p,name in enumerate(pols):
            for ax,values in [(upper,amplitudes*1000),(lower,phases)]:
                ax.plot(x,values[:,p],ls='none',marker='o',ms=.78 if native else 1.9,
                        mew=0,color=POL_COLORS[name],rasterized=native)
    for event in hits:
        if is_time and 'lo' in event:
            for ax in (upper,lower):
                ax.axvspan(event['lo'],event['hi'],lw=0,color='#e9ad45',alpha=.22,zorder=0)
        if is_time or z is None: continue
        if event['kind']=='repeatable phase slope':
            lower.axvspan(centers[event['first']],centers[event['last']],color='#97c6df',alpha=.2,lw=0)
        if event['kind']=='IF excursion':
            i=event['spw']
            if native:
                for ax in (upper,lower):
                    ax.axvspan(centers[i]-.029,centers[i]+.029,color='#a0c6d5',alpha=.18,lw=0)
            else:
                p=pols.index(event['pols'][0])
                for ax,y in [(upper,amplitudes[i,p]*1000),(lower,phases[i,p])]:
                    ax.scatter(centers[i],y,s=15,facecolors='none',edgecolors=INK,lw=.55)
        if native and event['kind']=='channel peak':
            i=int(np.argmin(abs(x-event['ghz'])))
            p=max((pols.index(k) for k in event['pols']),key=lambda j:amplitudes[i,j])
            upper.scatter(x[i],amplitudes[i,p]*1000,s=17,facecolors='none',edgecolors=INK,lw=.55)
    if is_time: lower.set_xlim(0,duration)
    else:
        lower.set_xlim(centers.min()-.06,centers.max()+.06)
        lower.xaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    if missing:
        intervals,label=missing
        for lo,hi in intervals:
            upper.plot([lo,hi],[.985,.985],transform=upper.get_xaxis_transform(),
                       color='#9B3098',lw=2.0,solid_capstyle='butt',zorder=6)
        upper.text(.01,.895,label,ha='left',va='top',fontsize=6.4,
                   color='#731E70',transform=upper.transAxes,
                   bbox=dict(facecolor='white',edgecolor='none',alpha=.9,pad=.6))
    upper.tick_params(labelbottom=False)
    upper.set_ylim(bottom=0)
    upper.set_ylabel('mJy' if native and not is_time else '|V| × 1000')
    upper.yaxis.set_major_locator(MaxNLocator(3))
    lower.set_ylabel('Phase (°)');lower.set_yticks([-180,0,180]);lower.set_ylim(-191,191)
    lower.xaxis.set_major_locator(MaxNLocator(5))
    lower.set_xlabel('Time from scan start (s)' if is_time else 'Frequency (GHz)',labelpad=1)
    for ax in (upper,lower):
        ax.grid(axis='y',lw=.35,color='#cad3d7')
        ax.spines[['right','top']].set_visible(False)
        ax.tick_params(length=2,pad=1.5)


def ordered_commands(root):
    quality=json.loads((root/'flag_plan.json').read_text())
    full=json.loads((root/'full_pol_plan.json').read_text())
    priority=lambda p:(0 if '&' not in p['kwargs']['antenna'] else 1 if ',' in p['kwargs']['antenna'] else 2 if p['target']=='export' else 3,p['scan'],p['kwargs']['antenna'])
    plans=sorted(quality,key=priority)
    for category in ('commands','closure'):
        plans.extend(dict(p,target='export') for p in full[category])
    return [dict(p,id=i) for i,p in enumerate(plans,1)]


def indices(spec):
    for term in spec.split(','):
        ends=list(map(int,term.split('~')))
        yield from range(ends[0],ends[-1]+1)


def selection(action,b,t,origin,nif,nchan,pols):
    """Return time, spectral and hand indices in this action's own grid."""
    from datetime import datetime
    k=action['kwargs']
    if set(k)-{'antenna','timerange','spw','correlation','scan'}:
        raise ValueError(f'Unsupported selection: {k}')
    if 'scan' in k and str(action['scan'])!=str(k['scan']):
        raise ValueError('Expand multi-scan commands into per-scan masks first')
    a,sep,partners=k['antenna'].partition('&')
    if a not in b.split('-') or (sep and not (set(b.split('-'))-{a})&set(partners.split(','))):
        return None
    times=np.ones(len(t),bool)
    if 'timerange' in k:
        lo,hi=[datetime.strptime(v,'%Y/%m/%d/%H:%M:%S.%f') for v in k['timerange'].split('~')]
        times=(t>=(lo-origin).total_seconds())&(t<=(hi-origin).total_seconds())
    spectral=np.ones((nif,nchan),bool)
    if 'spw' in k:
        spectral[:]=False
        for term in k['spw'].split(','):
            win,colon,chan=term.partition(':')
            channels=list(indices(chan.replace(';',','))) if colon else list(range(nchan))
            spectral[np.ix_(list(indices(win)),channels)]=True
    hands=np.isin(pols,k.get('correlation',','.join(pols)).split(','))
    return np.flatnonzero(times),np.flatnonzero(spectral),np.flatnonzero(hands)


def cleaned(v,w,t,bins,duration,mask):
    from collect_visibility_samples import weighted_mean
    weights=np.where(mask,0,w)
    native=np.where(weights>0,v,complex(np.nan,np.nan))
    means=[]
    for i,mid in enumerate(bins):
        use=(t>=mid-2)&(t<mid+2+(.011 if i==len(bins)-1 else 0))
        means.append(weighted_mean(v[use],weights[use],(0,1)))
    return native,np.asarray(means),weighted_mean(v,weights,0)


def render(root,coverage,source='M87',scans=None,check_only=False):
    from datetime import datetime
    from textwrap import fill
    from matplotlib.lines import Line2D
    from astropy.io import fits
    rows=defaultdict(list)
    for r in csv.DictReader(coverage.open()):rows[int(r['scan'])].append(r)
    plans=ordered_commands(root)
    output=root/'review_plots'
    if not check_only:output.mkdir(exist_ok=True)
    polinfo=json.loads((root/'full_pol_plan.json').read_text())['details']
    day=fits.getval(coverage.resolve().parent.parent/(source+'_calibrated.uvf'),'DATE-OBS')[:10]
    plt.rcParams.update({'font.size':7,'axes.labelsize':7,'xtick.labelsize':6,'ytick.labelsize':6,'axes.linewidth':.55,'pdf.fonttype':42})
    for scan,group in rows.items():
        if scans and scan not in scans:continue
        with np.load(root/'uv'/f'scan{scan}.npz') as u,np.load(root/'channels'/f'scan{scan}.npz') as c:
            uv=dict(u);ch=dict(c)
        centers=uv['freq'];pols=list(uv['pols']);bins=uv['bin_centers'];duration=float(uv['duration'])
        freq=ch.get('frequency');nif=len(centers);nc=len(freq)//nif if freq is not None else None
        origin=datetime.strptime(day+'T'+group[0]['start_utc'],'%Y-%m-%dT%H:%M:%S.%f')
        active=[p for p in plans if p['scan']==scan]
        pairs=[r['station1']+'-'+r['station2'] for r in group]
        examples=defaultdict(list);data={}; notes={}
        for b in pairs:
            t=uv[b+'_t'];v=uv[b+'_v'];w=uv[b+'_w']
            direct=np.zeros(w.shape,bool);fine=np.zeros((len(freq) if nc else 0,len(pols)),bool)
            ids=[]
            for p in active:
                channel=p['target']=='channelized'
                if channel and nc is None:raise ValueError(f"Missing grid for command {p['id']}")
                sel=selection(p,b,t,origin,nif,nc if channel else 1,pols)
                if sel is None:continue
                ti,fi,hi=sel
                if not len(ti):continue
                if channel:
                    if 'timerange' in p['kwargs']:raise ValueError('Time-resolved fine channels required')
                    fine[np.ix_(fi,hi)]=True
                    support=np.isfinite(ch[b][0][np.ix_(fi,hi)]).sum() if b in ch else 0
                else:
                    ix=np.ix_(ti,fi,hi);direct[ix]=True;support=(w[ix]>0).sum()
                if support:
                    examples[p['id']].append((int(support),b,sel));ids.append(p['id'])
            # A single export sample mixes all fine channels. Withhold unresolved aggregates.
            mask=direct.copy()
            if nc:mask|=fine.reshape(nif,nc,-1).any(axis=1)[None,:,:]
            native,avg,spec=cleaned(v,w,t,bins,duration,mask)
            diag=None
            if b in ch:
                diag=ch[b].copy()
                # Scan averages cannot be repaired after a contributing integration was removed.
                unavailable=np.repeat((direct&(w>0)).any(axis=0),nc,axis=0)
                diag[:,fine|unavailable]=np.nan
            removed=(mask&(w>0))
            fine_spans=[]
            if b in ch:
                omitted=np.isfinite(ch[b][0]) & ~np.isfinite(diag[0])
                fine_spans=spans(freq,omitted.any(1),abs(freq[1]-freq[0])/2)
            half_if=abs(np.median(np.diff(np.sort(centers))))/2 if nif>1 else .001
            marks=[spans(t,removed.any((1,2)),np.median(np.diff(t))/2 if len(t)>1 else .2),
                   spans(centers,removed.any((0,2)),half_if),fine_spans]
            data[b]=(native,avg,spec,diag,marks)
            notes[b]=(ids,int((direct&(w>0)).sum()),int(((mask&~direct)&(w>0)).sum()))
        if check_only:
            no_data=[p['id'] for p in active if not examples[p['id']]]
            print(f'Scan {scan}: {len(active)} commands; no recoverable examples {no_data}; '
                  f'{sum(v[1] for v in notes.values())} directly removed; '
                  f'{sum(v[2] for v in notes.values())} unresolved export samples withheld',flush=True)
            continue
        def sheet(title,subtitle):
            fig=plt.figure(figsize=(11.7,13))
            fig.text(.045,.967,title,size=15,weight='bold');fig.text(.045,.945,subtitle,size=8)
            fig.legend(handles=[Line2D([],[],ls='none',marker='o',ms=3,color=color,label=h) for h,color in POL_COLORS.items()],
                       loc='upper right',bbox_to_anchor=(.98,.99),ncol=4,frameon=False)
            return fig
        def publish(name,draw):
            tmp=output/(name+'.partial.pdf')
            with PdfPages(tmp) as pdf:draw(pdf)
            tmp.replace(output/(name+'.pdf'))
        def evidence(pdf):
            for start in range(0,len(active),3):
                fig=sheet(f'{source}   /   Scan {scan}   /   Evidence before flagging','One row per command. Rings or shading locate its selected spectral channels, windows or UTC interval.')
                grid=fig.add_gridspec(3,2,left=.085,right=.965,top=.86,bottom=.07,hspace=.94,wspace=.28)
                for j,p in enumerate(active[start:start+3]):
                    k=p['kwargs']; choices=sorted(examples[p['id']],key=lambda z:(-z[0],z[1]))[:2]
                    y=grid[j,0].get_position(fig).y1
                    fig.text(.055,y+.049,f"C{p['id']:03}   {p['reason']}",weight='bold',size=10)
                    fig.text(.055,y+.029,'   '.join(f'{key}={value}' for key,value in k.items()),size=7)
                    if not choices:fig.text(.09,y-.05,'No recoverable samples in this diagnostic selection.')
                    for col,(count,b,(ti,fi,hi)) in enumerate(choices):
                        channel=p['target']=='channelized';time='spw' not in k and not channel
                        x=bins if time else freq if channel else centers
                        z=uv[b+'_avg'] if time else ch[b] if channel else uv[b+'_spectrum']
                        events=[]
                        if time:
                            tt=uv[b+'_t'][ti];events=[dict(kind='interval',lo=min(tt)-.2,hi=max(tt)+.2)]
                        elif channel:
                            events=[dict(kind='channel peak',ghz=x[f],pols=[pols[h] for h in hi if np.isfinite(z[0,f,h])]) for f in fi if np.isfinite(z[0,f,hi]).any()]
                        else:
                            events=[dict(kind='IF excursion',spw=f,pols=[pols[h]]) for f in fi for h in hi]
                        detail=f'{count:,} matching input samples'
                        if channel:
                            ratios=[]
                            for f in fi:
                                for h in hi:
                                    ref=z[0,(f//nc)*nc:(f//nc+1)*nc,h]
                                    ref=ref[np.isfinite(ref)]
                                    if len(ref) and np.median(ref)>0 and np.isfinite(z[0,f,h]):
                                        ratios.append(z[0,f,h]/np.median(ref))
                            if ratios:detail+=f'   •   peak / same-hand window median {max(ratios):.2f}×'
                        elif time:
                            selected=(bins>=min(tt))&(bins<=max(tt))
                            inside=np.abs(z[np.ix_(selected,hi)]);outside=np.abs(z[np.ix_(~selected,hi)])
                            if np.isfinite(inside).any() and np.isfinite(outside).any():
                                detail+=f'   •   median inside / outside: {1000*np.nanmedian(inside):.3g} / {1000*np.nanmedian(outside):.3g}'
                        missing=None
                        if 'feed only' in p['reason']:
                            labels=[r for r in polinfo if r['scan']==scan and r['baseline']==b]
                            if labels:
                                missing=([(centers[f]-.029,centers[f]+.029) for f in fi],
                                         '\n'.join(f"{r['missing']} missing in SPWs {r['spw']}" for r in labels))
                        slot=grid[j,:] if len(choices)==1 else grid[j,col]
                        cell(fig,slot,x,z,pols,f'{b}  ·  Scan {scan}', 'time' if time else 'freq',channel,events,centers,duration,missing)
                        pos=slot.get_position(fig)
                        fig.text(pos.x0,pos.y0-.044,detail,fontsize=7,color='#45606c')
                pdf.savefig(fig,dpi=220);plt.close(fig)
        def coverage_pages(pdf):
            for start in range(0,len(pairs),6):
                for native_view in (False,True):
                    view='Individual integrations and channel spectra' if native_view else 'Weighted complex means'
                    fig=sheet(f'{source}   /   Scan {scan}   /   {view}',f"After selections   •   {group[0]['start_utc']}–{group[0]['end_utc']} UTC   •   Baselines {start+1}–{min(start+6,len(pairs))} of {len(pairs)}")
                    grid=fig.add_gridspec(4,3,left=.076,right=.975,top=.91,bottom=.08,hspace=.60,wspace=.32)
                    for j,b in enumerate(pairs[start:start+6]):
                        v,a,s,d,marks=data[b];rr=2*(j//3);cc=j%3
                        for spectral in (False,True):
                            x=(freq if native_view and d is not None else centers) if spectral else uv[b+'_t'] if native_view else bins
                            z=(d if native_view else s) if spectral else v if native_view else a
                            domain='Frequency' if spectral else 'Time'
                            cell(fig,grid[rr+int(spectral),cc],x,z,pols,f'{b}  ·  Scan {scan}  /  {domain}',domain.lower(),native_view,[],centers,duration,
                                 (marks[2 if native_view and spectral else int(spectral)],'Removed / withheld') if marks[2 if native_view and spectral else int(spectral)] else None)
                        ids,n,w=notes[b];pos=grid[rr+1,cc].get_position(fig)
                        desc='C'+', '.join(map(str,ids)) if ids else 'No matching flags'
                        fig.text(pos.x0,pos.y0-.038,fill(f'{desc}  |  export: {n} removed, {w} unresolved withheld',62),fontsize=6,color='#731E70',va='top')
                    fig.text(.045,.014,'Magenta bar: some samples removed or withheld. C numbers link to the evidence. Fine scan averages overlapping export time flags are withheld. Missing channels are never interpolated.',fontsize=8)
                    pdf.savefig(fig,dpi=220);plt.close(fig)
        if active:publish(f'evidence{scan}',evidence)
        publish(f'clean{scan}',coverage_pages)
        print('Prepared scan',scan,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('coverage',type=Path);p.add_argument('--source',default='M87')
    p.add_argument('--scans',type=int,nargs='+')
    p.add_argument('--check-only',action='store_true',help='Compute selections and residual arrays without writing plots')
    args=p.parse_args();render(args.root,args.coverage,args.source,args.scans,args.check_only)
