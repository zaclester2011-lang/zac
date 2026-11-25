import json, datetime, math
def card(d):
    p=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return p[int((d%360)/22.5+0.5)%16]
NAMES=["sougia","marmara","loutro","glykanera"]
data={}
for nm in NAMES:
    j=json.load(open(f"met_{nm}.json")); rows={}
    for t in j["properties"]["timeseries"]:
        ts=datetime.datetime.fromisoformat(t["time"].replace("Z","+00:00"))
        loc=ts+datetime.timedelta(hours=2)
        if not (datetime.date(2026,10,26)<=loc.date()<=datetime.date(2026,11,3)): continue
        if not (8<=loc.hour<=13): continue
        d=t["data"]["instant"]["details"]
        rows.setdefault(loc.date(),[]).append((d["wind_speed"]*1.94384,d["wind_from_direction"],d["cloud_area_fraction"]))
    data[nm]=rows
days=sorted(data["sougia"])
print(f"\n{'morning':11s}" + "".join(f"{n[:9]:>20s}" for n in NAMES))
for day in days:
    line=f"{day:%a %d %b}  "
    for nm in NAMES:
        v=data[nm].get(day)
        if not v: line+=f"{'-':>20s}"; continue
        mean=sum(x[0] for x in v)/len(v)
        sx=sum(math.sin(math.radians(x[1])) for x in v); cx=sum(math.cos(math.radians(x[1])) for x in v)
        dd=math.degrees(math.atan2(sx,cx))%360
        # south coast: onshore = 110-250
        on = 110<=dd<=250
        line+=f"{mean:7.1f}kn {card(dd):>3s}{'*' if on else ' '}   "
    cl=[sum(x[2] for x in data[nm][day])/len(data[nm][day]) for nm in NAMES if data[nm].get(day)]
    print(line+f"  cloud {min(cl):3.0f}-{max(cl):3.0f}%")
print("\n* = onshore (south sector 110-250 deg) -> swell onto the beach")
print("\nSPREAD between the four points, per morning (max mean - min mean, kn):")
for day in days:
    ms=[sum(x[0] for x in data[nm][day])/len(data[nm][day]) for nm in NAMES if data[nm].get(day)]
    print(f"  {day:%a %d %b}  {max(ms)-min(ms):4.1f} kn   (range {min(ms):.1f}-{max(ms):.1f})")
