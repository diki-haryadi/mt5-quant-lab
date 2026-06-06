"""sr_sweep.py — sweep RMULT × wick-filter utk S/R konfluensi v2 (fetch 1×/simbol, sim banyak).
Cari apakah ADA kombinasi yg lolos PF>1.1 di IS DAN OOS (anti-overfit)."""
import math, datetime as dt, bisect, sys
from mt5_scalper import MT5Api, calc_lot
from backtest_lab import atr_series

API = "http://192.168.0.111:8000"
BAL, RISK, MAXR, ATRP = 1000.0, 0.5, 6.0, 14
NEAR, CLUST, ENTRYTOL, SLBUF, MINTF, COOLDOWN, PIVL, DAYS = 1.2, 0.30, 0.5, 0.5, 3, 16, 4, 540
api = MT5Api(API, timeout=120)
def ema(c,p):
    n=len(c);o=[float('nan')]*n
    if n<p:return o
    k=2/(p+1);s=sum(c[:p])/p;o[p-1]=s
    for i in range(p,n):s=c[i]*k+s*(1-k);o[i]=s
    return o
def pivots(bars,L=PIVL):
    n=len(bars);hi=[b['high'] for b in bars];lo=[b['low'] for b in bars];out=[]
    for i in range(L,n-L):
        if hi[i]==max(hi[i-L:i+L+1]):out.append((bars[i+L]['time'],hi[i]))
        if lo[i]==min(lo[i-L:i+L+1]):out.append((bars[i+L]['time'],lo[i]))
    out.sort();return out
def fetch(sym,tf,frm,to):
    d=api._get(f"/api/symbols/{sym}/bars/range",timeframe=tf,from_time=str(frm),to_time=str(to))
    return d.get("bars",[]) if isinstance(d,dict) else []

def load(sym):
    end=int(dt.datetime.now().timestamp());start=int((dt.datetime.now()-dt.timedelta(days=DAYS)).timestamp())
    m15=fetch(sym,"M15",start,end)
    if len(m15)<1500:return None
    sinfo=api.symbol_info(sym)
    d1=fetch(sym,"D1",start,end);h4=fetch(sym,"H4",start,end)
    TFS=["H2","H1","M30","M15"]
    conf={"H2":pivots(fetch(sym,"H2",start,end)),"H1":pivots(fetch(sym,"H1",start,end)),"M30":pivots(fetch(sym,"M30",start,end)),"M15":pivots(m15)}
    return dict(sym=sym,m15=m15,sinfo=sinfo,d1=d1,h4=h4,d1e=ema([b['close'] for b in d1],50),
                h4e=ema([b['close'] for b in h4],50),atr=atr_series(m15,ATRP),conf=conf,TFS=TFS)

def sim(L,rmult,wickmin):
    m15=L['m15'];sinfo=L['sinfo'];pt=sinfo["point"];tk=sinfo.get("trade_tick_size") or pt;tv=sinfo.get("trade_tick_value") or 1.0
    money=lambda d,lot:(d/tk)*tv*lot;d1=L['d1'];h4=L['h4'];d1e=L['d1e'];h4e=L['h4e'];atr=L['atr'];TFS=L['TFS']
    ptr={k:0 for k in TFS};active={k:[] for k in TFS}
    def near(tf,lo,hi):
        a=active[tf];i=bisect.bisect_left(a,lo);j=bisect.bisect_right(a,hi);return a[i:j]
    def cluster(price,tn,tc):
        pts=[]
        for tf in TFS:
            for lv in near(tf,price-tn,price+tn):pts.append((lv,tf))
        if len(pts)<MINTF:return None
        pts.sort();best=None
        for x in range(len(pts)):
            grp=[pts[x]]
            for y in range(x+1,len(pts)):
                if pts[y][0]-pts[x][0]<=tc:grp.append(pts[y])
                else:break
            if len(set(g[1] for g in grp))>=MINTF:
                ctr=sum(g[0] for g in grp)/len(grp);cand=(ctr,grp[0][0],grp[-1][0])
                if best is None or abs(ctr-price)<abs(best[0]-price):best=cand
        return best
    pd_=ph=0;bal=BAL;peak=BAL;ddp=0.0;T=[];pos=None;leb=-10**9;lz=None
    for i in range(60,len(m15)):
        b=m15[i];t=b['time']
        if pos:
            hit=None
            if pos['side']=='buy':
                if b['low']<=pos['sl']:hit=pos['sl']
                elif b['high']>=pos['tp']:hit=pos['tp']
            else:
                if b['high']>=pos['sl']:hit=pos['sl']
                elif b['low']<=pos['tp']:hit=pos['tp']
            if hit is not None:
                plp=(hit-pos['e']) if pos['side']=='buy' else (pos['e']-hit)
                net=money(plp,pos['lot'])-money(pos['spr'],pos['lot']);bal+=net
                peak=max(peak,bal);ddp=max(ddp,(peak-bal)/peak*100 if peak>0 else 0)
                T.append({"net":net,"t":t,"win":net>0});pos=None
        if pos:continue
        a=atr[i]
        if math.isnan(a) or a<=0:continue
        for tf in TFS:
            piv=L['conf'][tf];p=ptr[tf]
            while p<len(piv) and piv[p][0]<=t:bisect.insort(active[tf],piv[p][1]);p+=1
            ptr[tf]=p
        if i-leb<COOLDOWN:continue
        while pd_+1<len(d1) and d1[pd_+1]['time']<=t:pd_+=1
        while ph+1<len(h4) and h4[ph+1]['time']<=t:ph+=1
        if math.isnan(d1e[pd_]) or math.isnan(h4e[ph]):continue
        bd=d1[pd_]['close']>d1e[pd_];bh=h4[ph]['close']>h4e[ph]
        bias=1 if (bd and bh) else (-1 if (not bd and not bh) else 0)
        if bias==0:continue
        price=b['close'];cl=cluster(price,NEAR*a,CLUST*a)
        if cl is None:continue
        ctr,clo,chi=cl
        if abs(ctr-price)>ENTRYTOL*a:continue
        if lz is not None and abs(ctr-lz)<0.6*a and i-leb<80:continue
        rng=b['high']-b['low']
        if rng<=0:continue
        if bias==1:
            lw=min(b['open'],b['close'])-b['low']
            if not((b['low']<=chi+ENTRYTOL*a) and (b['close']>b['open']) and (b['close']>ctr) and (lw/rng>=wickmin)):continue
            sl=clo-SLBUF*a;risk=price-sl
            if risk<=0:continue
            tp=price+rmult*risk;side='buy'
        else:
            uw=b['high']-max(b['open'],b['close'])
            if not((b['high']>=clo-ENTRYTOL*a) and (b['close']<b['open']) and (b['close']<ctr) and (uw/rng>=wickmin)):continue
            sl=chi+SLBUF*a;risk=sl-price
            if risk<=0:continue
            tp=price-rmult*risk;side='sell'
        lot,est=calc_lot(bal*RISK/100,risk,sinfo)
        if est>bal*MAXR/100:continue
        pos=dict(side=side,e=price,lot=lot,spr=b['spread']*pt,sl=sl,tp=tp);leb=i;lz=ctr
    if not T:return None
    half=(T[0]['t']+T[-1]['t'])//2
    def stt(tr):
        if not tr:return (0,0,0)
        w=[x for x in tr if x['win']];gw=sum(x['net'] for x in w);gl=-sum(x['net'] for x in tr if not x['win'])
        return (len(tr),(gw/gl) if gl else 999,sum(x['net'] for x in tr))
    return dict(full=stt(T),IS=stt([x for x in T if x['t']<half]),OOS=stt([x for x in T if x['t']>=half]),dd=ddp)

if __name__=="__main__":
    syms=sys.argv[1:] or ["XAUUSD","USDJPY","EURUSD","GBPUSD"]
    print(f"SWEEP RMULT×wick | konfluensi v2 cluster>=3TF cooldown16 | {DAYS}d")
    for s in syms:
        L=load(s)
        if not L:print(f"{s}: data kurang");continue
        print(f"\n=== {s} ===")
        print(f"{'RMULT':>5} {'wick':>4} | {'IS(n/PF/net)':>22} | {'OOS(n/PF/net)':>22} | dd%")
        for rm in (1.0,1.2,1.5,2.0):
            for wk in (0.0,0.4):
                r=sim(L,rm,wk)
                if not r:continue
                I=r['IS'];O=r['OOS']
                flag=" <== robust" if (I[1]>1.1 and O[1]>1.1) else ""
                print(f"{rm:>5} {wk:>4} | {I[0]:>4}/{I[1]:>5.2f}/${I[2]:>+6.0f} | {O[0]:>4}/{O[1]:>5.2f}/${O[2]:>+6.0f} | {r['dd']:.0f}{flag}")
