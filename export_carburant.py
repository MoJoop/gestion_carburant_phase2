# -*- coding: utf-8 -*-
"""
Exporte les données du questionnaire « GESTION CARBURANT EHCVM III - Phase II »
depuis l'API Survey Solutions (ANSD) vers data/carburant.json,
fichier consommé par le tableau de bord statique (index.html).

Usage :
    python export_carburant.py
puis  git add data/carburant.json && git commit -m "maj données" && git push
"""
import requests, sys, urllib3, json, os, time
from requests.auth import HTTPBasicAuth

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://dpeeservey2.ansd.sn:9702"
WS   = "ehcvm3"
AUTH = HTTPBasicAuth(os.getenv("SUSO_USER", "diop_api"),
                     os.getenv("SUSO_PASSWORD", "Passer1234"))
GUID = "c3a1f062668d43e3a30a4a424925eaeb"   # GESTION CARBURANT (sans tirets)
VER  = 2
HDR  = {"Accept": "application/json"}

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "carburant.json")

PRIX = {"Essence": 990, "Gasoil": 755}   # FCFA / litre (réf. variables SuSo)

GUID_DASH = "c3a1f062-668d-43e3-a30a-4a424925eaeb"

def api(path, params=None):
    return requests.get(f"{BASE}/{WS}/api/v1{path}", auth=AUTH, headers=HDR,
                        params=params, verify=False, timeout=120)

def graphql(query, variables):
    return requests.post(f"{BASE}/graphql", auth=AUTH, headers=HDR,
                         json={"query": query, "variables": variables},
                         verify=False, timeout=120)

def to_num(v):
    if v is None: return None
    try:
        return float(str(v).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None

QUERY = """query($w:String!,$skip:Int!,$take:Int!){
  interviews(workspace:$w, skip:$skip, take:$take,
    where:{questionnaireId:{eq:"%s"}, questionnaireVersion:{eq:%d}}){
    nodes{ id status responsibleName questionnaireVersion updateDateUtc }
  }
}""" % (GUID_DASH, VER)

def list_interviews():
    """Liste TOUTES les interviews v2 via GraphQL (l'endpoint REST /interviews
    est plafonné à 10 et ignore offset). Pagination skip/take."""
    out, skip, take = [], 0, 200
    while True:
        r = graphql(QUERY, {"w": WS, "skip": skip, "take": take})
        if r.status_code != 200:
            print(f"  GraphQL skip={skip} → HTTP {r.status_code} : {r.text[:200]}")
            break
        nodes = (((r.json() or {}).get("data") or {}).get("interviews") or {}).get("nodes") or []
        # garde-fou : ne garder que la version VER
        nodes = [n for n in nodes if n.get("questionnaireVersion") == VER]
        out.extend(nodes)
        if len(nodes) < take:
            break
        skip += take
        if skip > 100000:
            break
    return out, len(out)

# Variables d'intérêt → on garde le libellé tel que renvoyé par l'API (déjà décodé)
KEEP = ["date", "TypeAgent", "NomEqTechnique", "NomEqAgent", "Region", "Departement",
        "matricule", "NomChauff", "TypeCarburant", "LieuExact", "Kilometrage",
        "QttRecharge", "MontRecharge", "EquipeCharg", "Soldecarte", "RegionDes",
        "ObserCarb", "Observation", "CoordGps"]
NUMS = {"Kilometrage", "QttRecharge", "MontRecharge", "Soldecarte"}

def detail(iid):
    r = api(f"/interviews/{iid}")
    if r.status_code != 200:
        return {}
    ans = r.json().get("Answers") or []
    rec = {}
    for a in ans:
        v = a.get("VariableName")
        if v in KEEP:
            val = a.get("Answer")
            rec[v] = to_num(val) if v in NUMS else val
    return rec

def main():
    print("=== Export GESTION CARBURANT Phase II ===")
    its, total = list_interviews()
    print(f"  {len(its)} interviews listées (TotalCount API = {total})")
    records = []
    for i, it in enumerate(its, 1):
        iid = it.get("id")
        rec = detail(iid)
        rec["interviewId"]   = iid
        rec["status"]        = it.get("status")
        rec["responsable"]   = it.get("responsibleName")
        rec["lastEntryDate"] = it.get("updateDateUtc")
        # nom de l'agent affiché : technique sinon enquêteur sinon responsable
        rec["agent"] = rec.get("NomEqTechnique") or rec.get("NomEqAgent") or rec.get("responsable")
        # montant calculé de secours si MontRecharge vide
        q = rec.get("QttRecharge"); tc = rec.get("TypeCarburant")
        if rec.get("MontRecharge") is None and q is not None and tc in PRIX:
            rec["MontRechargeCalc"] = round(q * PRIX[tc])
        records.append(rec)
        if i % 10 == 0:
            print(f"    {i}/{len(its)}…")

    payload = {
        "metadata": {
            "questionnaire": "GESTION CARBURANT EHCVM III - Phase II",
            "version": VER,
            "date_export": time.strftime("%Y-%m-%d %H:%M:%S"),
            "nb_recharges": len(records),
            "prix_litre": PRIX,
        },
        "recharges": records,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"  ✅ {len(records)} recharges → {OUT}")

if __name__ == "__main__":
    main()
