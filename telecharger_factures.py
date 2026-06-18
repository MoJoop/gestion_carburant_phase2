# -*- coding: utf-8 -*-
"""
Télécharge les photos de factures du questionnaire « GESTION CARBURANT Phase II »,
les regroupe par équipe et produit des ZIP (un par équipe + un global) dans factures/,
ainsi qu'un manifeste factures/factures_index.json consommé par le dashboard.

Les images sont recompressées (max 1600 px, JPEG q=70) pour tenir sous la limite
GitHub de 100 Mo/fichier.

Usage :
    python telecharger_factures.py
    FACTURES_ZIP=chemin\\vers\\binary.zip python telecharger_factures.py   # réutilise un export déjà téléchargé
puis : git add factures && git commit -m "maj factures" && git push
"""
import requests, sys, urllib3, json, os, re, io, time, zipfile, shutil
from requests.auth import HTTPBasicAuth
from PIL import Image, ImageOps

sys.stdout.reconfigure(encoding="utf-8")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://dpeeservey2.ansd.sn:9702"
WS   = "ehcvm3"
AUTH = HTTPBasicAuth(os.getenv("SUSO_USER", "diop_api"),
                     os.getenv("SUSO_PASSWORD", "Passer1234"))
QID  = "c3a1f062668d43e3a30a4a424925eaeb$2"
HDR  = {"Accept": "application/json", "Content-Type": "application/json"}

HERE     = os.path.dirname(os.path.abspath(__file__))
DATA     = os.path.join(HERE, "data", "carburant.json")
OUTDIR   = os.path.join(HERE, "factures")
BUILD    = os.path.join(HERE, "_factures_build")
MAXSIDE  = 1600
QUALITY  = 70

def api_get(path, **kw):  return requests.get(f"{BASE}/{WS}{path}", auth=AUTH, verify=False, timeout=kw.pop("timeout", 120), **kw)
def api_post(path, body): return requests.post(f"{BASE}/{WS}{path}", auth=AUTH, headers=HDR, json=body, verify=False, timeout=120)

# ---------- 1. Obtenir le ZIP binaire (export) ----------
def telecharger_export_binaire():
    reuse = os.getenv("FACTURES_ZIP")
    if reuse and os.path.exists(reuse):
        print(f"  Réutilisation de l'export existant : {reuse}")
        return reuse
    print("  Déclenchement export binaire…")
    r = api_post("/api/v2/export", {"ExportType": "Binary", "QuestionnaireId": QID, "InterviewStatus": "All"})
    jid = r.json()["JobId"]
    print(f"  JobId={jid}, attente…")
    dl = ""
    for _ in range(120):
        j = api_get(f"/api/v2/export/{jid}").json()
        if j["ExportStatus"] == "Completed" and j["Links"]["Download"]:
            dl = j["Links"]["Download"]; break
        time.sleep(5)
    if not dl:
        sys.exit("  ✗ Export non terminé dans le délai imparti.")
    print("  Téléchargement du ZIP (peut être volumineux)…")
    path = os.path.join(HERE, "_factures_binary.zip")
    with api_get(dl, timeout=900, stream=True) as resp, open(path, "wb") as f:
        for chunk in resp.iter_content(1 << 20):
            f.write(chunk)
    print(f"  ✓ {os.path.getsize(path)/1e6:.0f} Mo téléchargés")
    return path

# ---------- 2. Mapping clé interview -> équipe + infos ----------
def charger_mapping():
    d = json.load(open(DATA, encoding="utf-8"))
    m = {}
    for r in d["recharges"]:
        if r.get("key"):
            m[r["key"]] = r
    return m

def equipe_de(resp):
    """EQ23_enq4_v2 -> ('eq23','Équipe 23') ; sinon login -> dossier."""
    mo = re.match(r"EQ(\d+)_", resp or "", re.I)
    if mo:
        return f"eq{mo.group(1)}", f"Équipe {mo.group(1)}"
    if resp:
        slug = re.sub(r"[^a-z0-9_]+", "", resp.lower())
        return slug, resp
    return "inconnu", "Inconnu"

def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(s or "")).strip("_")

# ---------- 3. Recompresser + ranger par équipe ----------
def recompresser(data_bytes):
    img = Image.open(io.BytesIO(data_bytes))
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAXSIDE, MAXSIDE))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=QUALITY, optimize=True)
    return buf.getvalue()

def main():
    print("=== Téléchargement des factures par équipe ===")
    zippath = telecharger_export_binaire()
    mapping = charger_mapping()

    if os.path.exists(BUILD): shutil.rmtree(BUILD)
    os.makedirs(BUILD, exist_ok=True)

    labels, per_team_count = {}, {}
    used = {}
    z = zipfile.ZipFile(zippath)
    entries = [n for n in z.namelist() if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    print(f"  {len(entries)} images dans l'export, recompression…")
    for i, name in enumerate(entries, 1):
        key = name.split("/")[0]
        rec = mapping.get(key, {})
        team, label = equipe_de(rec.get("responsable"))
        labels[team] = label
        # nom de fichier lisible : date_matricule_cle
        d = (rec.get("date") or "")[:10].replace(":", "-")
        base = "_".join(x for x in [safe(d), safe(rec.get("matricule")), key] if x)
        fname = base + ".jpg"
        n = used.get((team, fname), 0)
        if n: fname = f"{base}_{n+1}.jpg"
        used[(team, fname)] = n + 1
        try:
            out = recompresser(z.read(name))
        except Exception as e:
            print(f"    ⚠ {key}: {e}"); continue
        tdir = os.path.join(BUILD, team)
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, fname), "wb") as f:
            f.write(out)
        per_team_count[team] = per_team_count.get(team, 0) + 1
        if i % 25 == 0: print(f"    {i}/{len(entries)}…")

    # ---------- 4. Zipper ----------
    if os.path.exists(OUTDIR): shutil.rmtree(OUTDIR)
    os.makedirs(OUTDIR, exist_ok=True)
    index = {"date_generation": time.strftime("%Y-%m-%d %H:%M:%S"),
             "total_factures": sum(per_team_count.values()), "equipes": []}

    # zip global
    glob_path = os.path.join(OUTDIR, "factures_global.zip")
    with zipfile.ZipFile(glob_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for team in sorted(per_team_count):
            for fn in os.listdir(os.path.join(BUILD, team)):
                zf.write(os.path.join(BUILD, team, fn), f"{team}/{fn}")
    index["global"] = {"fichier": "factures_global.zip",
                       "taille_mo": round(os.path.getsize(glob_path)/1e6, 2)}

    # zip par équipe (ordre : eqN numérique puis le reste)
    def tri(t):
        mo = re.match(r"eq(\d+)$", t)
        return (0, int(mo.group(1))) if mo else (1, t)
    for team in sorted(per_team_count, key=tri):
        zp = os.path.join(OUTDIR, f"{team}.zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in os.listdir(os.path.join(BUILD, team)):
                zf.write(os.path.join(BUILD, team, fn), fn)
        index["equipes"].append({
            "id": team, "label": labels[team],
            "fichier": f"{team}.zip", "nb": per_team_count[team],
            "taille_mo": round(os.path.getsize(zp)/1e6, 2),
        })

    json.dump(index, open(os.path.join(OUTDIR, "factures_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    shutil.rmtree(BUILD)

    print(f"\n  ✅ {index['total_factures']} factures · {len(index['equipes'])} équipes")
    print(f"     Global : {index['global']['taille_mo']} Mo")
    for e in index["equipes"]:
        print(f"     {e['label']:14s} {e['nb']:3d} factures  {e['taille_mo']:.1f} Mo")
    if index["global"]["taille_mo"] > 95:
        print("  ⚠ ZIP global > 95 Mo : proche de la limite GitHub (100 Mo). Baisser QUALITY/MAXSIDE.")

if __name__ == "__main__":
    main()
