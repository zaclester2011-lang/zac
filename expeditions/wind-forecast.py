import json, datetime, math, sys

def card(d):
    pts=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return pts[int((d%360)/22.5+0.5)%16]

# onshore sectors (wind blowing ONTO the beach -> chop)
EXPOSURE={
 "elafonissi": (200,350),   # faces W/SW, open west and south-west
 "kedrodasos": (200,350),
 "balos":      (250,10),    # opens west and north; worst NW
}

def onshore(name,d):
    a,b=EXPOSURE[name]
    return (a<=d<=b) if a<b else (d>=a or d<=b)

for name in ("elafonissi","kedrodasos","balos"):
    j=json.load(open(f"met_{name}.json"))
    rows={}
    for t in j["properties"]["timeseries"]:
        ts=datetime.datetime.fromisoformat(t["time"].replace("Z","+00:00"))
        loc=ts+datetime.timedelta(hours=2)          # Athens = UTC+2 from 26 Oct
        if not (datetime.date(2026,10,26)<=loc.date()<=datetime.date(2026,11,3)): continue
        if not (8<=loc.hour<=13): continue           # morning window
        d=t["data"]["instant"]["details"]
        rows.setdefault(loc.date(),[]).append(
            (d.get("wind_speed")*1.94384, d.get("wind_from_direction"),
             (d.get("wind_speed_of_gust") or 0)*1.94384, d.get("cloud_area_fraction")))
    print(f"\n=== {name.upper()}  (08:00-13:00 local)")
    for day in sorted(rows):
        v=rows[day]
        mean=sum(x[0] for x in v)/len(v); mx=max(x[0] for x in v)
        gst=max(x[2] for x in v)
        # circular mean direction
        sx=sum(math.sin(math.radians(x[1])) for x in v); cx=sum(math.cos(math.radians(x[1])) for x in v)
        dd=math.degrees(math.atan2(sx,cx))%360
        cld=sum(x[3] for x in v)/len(v)
        on=sum(1 for x in v if onshore(name,x[1]))/len(v)
        flag="ONSHORE" if on>0.5 else ("mixed" if on>0.2 else "offshore")
        print(f"  {day:%a %d %b}  mean {mean:4.1f} kn  max {mx:4.1f}  gust {gst:4.1f}"
              f"   {card(dd):>3s} {dd:3.0f}deg  {flag:8s}  cloud {cld:3.0f}%")
