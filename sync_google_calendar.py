"""Sync verified market-calendar events into the authorized Google primary calendar."""
import os, json, hashlib, datetime as dt
from pathlib import Path
from collections import defaultdict
from icalendar import Calendar
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

UTC = dt.timezone.utc
def main():
    creds = Credentials.from_authorized_user_info(
        json.loads(os.environ["GOOGLE_CALENDAR_OAUTH_JSON"]),
        scopes=["https://www.googleapis.com/auth/calendar.events"])
    api = build("calendar", "v3", credentials=creds, cache_discovery=False).events()
    now = dt.datetime.now(UTC)
    events = Calendar.from_ical(Path("docs/market-indices.ics").read_bytes())
    groups = defaultdict(list)
    for e in events.walk("VEVENT"):
        start = e.decoded("DTSTART").astimezone(UTC)
        if not now-dt.timedelta(days=5) <= start <= now:
            continue
        summary = str(e["SUMMARY"])
        phase = next((p for p in ("开盘", "盘中", "收盘") if p in summary), None)
        if phase:
            groups[(start, phase)].append(e)
    if not groups:
        raise RuntimeError("No recent market events")
    existing = []
    token = None
    while True:
        page = api.list(calendarId="primary", timeMin=(now-dt.timedelta(days=6)).isoformat(),
                        timeMax=(now+dt.timedelta(days=1)).isoformat(),
                        singleEvents=True, pageToken=token).execute(num_retries=3)
        existing.extend(page.get("items", []))
        token = page.get("nextPageToken")
        if not token:
            break
    for (start, phase), items in sorted(groups.items()):
        uids = [str(e["UID"]) for e in items]
        key = hashlib.sha256((start.isoformat()+phase).encode()).hexdigest()
        matches = [e for e in existing if e.get("id")==key or
                   any("UID:"+uid in e.get("description","").splitlines() for uid in uids)]
        old = next((e for e in matches if e.get("id")==key), None) or next(iter(matches), None)
        titles, details = [], []
        for e in items:
            parts = str(e["SUMMARY"]).split("｜")
            name = parts[0].replace("🔵 ","").replace("🟣 ","").replace("纳斯达克综合指数","纳指").replace("中证A500","A500")
            titles.append(name+" "+parts[1].replace(phase+" ","")+" "+parts[-1])
            details.append(name+"\n"+str(e["DESCRIPTION"])+"\nUID:"+str(e["UID"]))
        recent = now-start <= dt.timedelta(minutes=90)
        when = start
        body = dict(summary=("🟣 " if phase=="收盘" else "🔵 ")+phase+"｜"+" / ".join(titles),
                    description="原始行情时间："+start.isoformat()+"\n"+"\n\n".join(details),
                    start={"dateTime":when.isoformat(),"timeZone":"Europe/Vienna"},
                    end={"dateTime":(when+dt.timedelta(minutes=15)).isoformat(),"timeZone":"Europe/Vienna"},
                    colorId="3" if phase=="收盘" else "9", transparency="transparent",
                    reminders={"useDefault":False,"overrides":[{"method":"popup","minutes":0}] if recent else []},
                    extendedProperties={"private":{"marketSync":"v1","marketKey":key}})
        if old:
            result = api.patch(calendarId="primary",eventId=old["id"],body=body,sendUpdates="none").execute(num_retries=3)
        else:
            body["id"]=key
            try:
                result = api.insert(calendarId="primary",body=body,sendUpdates="none").execute(num_retries=3)
            except HttpError as exc:
                if exc.resp.status != 409: raise
                body.pop("id")
                result = api.patch(calendarId="primary",eventId=key,body=body,sendUpdates="none").execute(num_retries=3)
        confirmed=api.get(calendarId="primary",eventId=result["id"]).execute(num_retries=3)
        if confirmed.get("summary") != body["summary"] or dt.datetime.fromisoformat(confirmed["start"]["dateTime"]) != start:
            raise RuntimeError("Calendar write verification failed")
        for duplicate in matches:
            if duplicate["id"] != result["id"]:
                api.delete(calendarId="primary",eventId=duplicate["id"],sendUpdates="none").execute(num_retries=3)
    print(f"Verified {len(groups)} market time groups")

if __name__ == "__main__":
    main()
