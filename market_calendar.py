import datetime as dt
import json
import pathlib
import urllib.request
import urllib.parse
from zoneinfo import ZoneInfo

INDICES = [('^IXIC','纳斯达克综合指数','America/New_York',16),('^NDX','纳斯达克100','America/New_York',16),('000510.SS','中证A500','Asia/Shanghai',15)]
def esc(s):
    return s.replace('\\','\\\\').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
def fold(s):
    out=[]; part=''
    for c in s:
        if len((part+c).encode())>73:
            out.append(part); part=' '
        part+=c
    return '\r\n'.join(out+[part])
def intraday(symbol,name,tz,source,stamp,lines,rows):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?range=5d&interval=30m'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=30) as response:
        data=json.load(response)['chart']['result'][0]
    q=data['indicators']['quote'][0]
    groups={}
    for t,o,c in zip(data['timestamp'],q['open'],q['close']):
        local=dt.datetime.fromtimestamp(t,tz)
        if o is not None and c is not None:
            groups.setdefault(local.date(),[]).append((local,o,c))
    prior_closes={day:price for day,price in rows}
    now=dt.datetime.now(dt.timezone.utc)
    for day,bars in sorted(groups.items()):
        previous=next((prior_closes[d] for d in sorted(prior_closes,reverse=True) if d<day),None)
        if previous and bars:
            start=bars[0][0]
            for i,(when,o,c) in enumerate(bars):
                if i%2: continue
                price=o if i==0 else bars[i-1][2]
                if when.astimezone(dt.timezone.utc)>now: continue
                label='开盘' if i==0 else '盘中'
                title=f'{name}｜{label} {price:,.2f}｜昨收 {previous:,.2f}｜{(price/previous-1)*100:+.2f}%'
                desc=f'昨收：{previous:,.2f}\n{label}点数：{price:,.2f}\n涨跌点数：{price-previous:+.2f}\n涨跌幅：{(price/previous-1)*100:+.2f}%\n行情时间：{when.isoformat()}\n数据：Yahoo Finance（可能延迟）'
                utc=when.astimezone(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                lines+=['BEGIN:VEVENT',f'UID:{symbol}-{utc}-intraday@market-calendar','DTSTAMP:'+stamp,'DTSTART:'+utc,'DURATION:PT1H','SUMMARY:'+esc(title),'DESCRIPTION:'+esc(desc),'END:VEVENT']

def main():
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Market Calendar//CN','CALSCALE:GREGORIAN','X-WR-CALNAME:中美股市每日观察']
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    for symbol,name,zone,hour in INDICES:
        tz=ZoneInfo(zone)
        if symbol=='000510.SS':
            url='https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.000510&klt=101&fqt=0&lmt=90&end=20500101&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53'
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
            with urllib.request.urlopen(req,timeout=30) as response:
                data=json.load(response)['data']
            rows=[(dt.date.fromisoformat(k.split(',')[0]),float(k.split(',')[2])) for k in data['klines']]
            source='东方财富'
        else:
            url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?range=3mo&interval=1d'
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as response:
                data=json.load(response)['chart']['result'][0]
            rows=[(dt.datetime.fromtimestamp(t,tz).date(),p) for t,p in zip(data['timestamp'],data['indicators']['quote'][0]['close']) if p is not None]
            source='Yahoo Finance'
        if len(rows)<2: raise RuntimeError('Insufficient data: '+symbol)
        for (prevday,prev),(day,price) in zip(rows,rows[1:]):
            close=dt.datetime.combine(day,dt.time(hour),tzinfo=tz).astimezone(dt.timezone.utc)
            if close+dt.timedelta(minutes=20)>dt.datetime.now(dt.timezone.utc): continue
            pct=(price/prev-1)*100
            title=f'{name}｜收盘 {price:,.2f}｜昨收 {prev:,.2f}｜{pct:+.2f}%'
            desc=f'交易日：{day}\n昨收：{prev:,.2f}\n收盘：{price:,.2f}\n涨跌点数：{price-prev:+.2f}\n涨跌幅：{pct:+.2f}%\n数据：{source}（非官方，可能延迟）'
            lines+=['BEGIN:VEVENT',f'UID:{symbol}-{day}@market-calendar','DTSTAMP:'+stamp,'DTSTART:'+close.strftime('%Y%m%dT%H%M%SZ'),'DURATION:PT24H','SUMMARY:'+esc(title),'DESCRIPTION:'+esc(desc),'END:VEVENT']
        try:
            intraday(symbol,name,tz,source,stamp,lines,rows)
        except Exception as exc:
            print(f'Intraday unavailable for {symbol}: {exc}')
            raise
    lines+=['END:VCALENDAR']
    pathlib.Path('docs').mkdir(exist_ok=True)
    pathlib.Path('docs/market-indices.ics').write_bytes(('\r\n'.join(map(fold,lines))+'\r\n').encode())
if __name__=='__main__': main()
