# Suivi du carburant — EHCVM III Phase II

Tableau de bord de suivi des recharges de carburant, alimenté par le questionnaire
Survey Solutions **« GESTION CARBURANT EHCVM III - Phase II »** (ANSD).

🔗 **Dashboard en ligne :** https://mojoop.github.io/gestion_carburant_phase2/

## Contenu

| Fichier | Rôle |
|---|---|
| `index.html` / `style.css` / `app.js` | Tableau de bord statique (Chart.js) |
| `data/carburant.json` | Données exportées depuis Survey Solutions |
| `export_carburant.py` | Script d'export API → `data/carburant.json` |
| `telecharger_factures.py` | Télécharge les photos de factures, les regroupe par équipe → `factures/*.zip` |
| `factures/` | ZIP des factures (un par équipe + global) + `factures_index.json` |

## Indicateurs

- KPIs : nombre de recharges, litres totaux, montant total (FCFA), véhicules, équipes, régions, prix moyen au litre.
- Graphiques : montant par région, litres par type (Essence/Gasoil), évolution quotidienne, top véhicules, recharges par équipe.
- Tableau détaillé filtrable (région, carburant, équipe, statut, recherche) + export CSV.

## Mettre à jour les données

```bash
# Identifiants API (sinon valeurs par défaut dans le script)
export SUSO_USER=diop_api
export SUSO_PASSWORD=********

python export_carburant.py            # régénère data/carburant.json
git add data/carburant.json
git commit -m "maj données carburant"
git push
```

Le dashboard se met à jour automatiquement après le `push` (GitHub Pages).

## Mettre à jour les factures (photos)

```bash
python telecharger_factures.py          # export binaire SuSo → recompression → factures/*.zip
git add factures && git commit -m "maj factures" && git push
```

Les photos sont recompressées (max 1600 px, JPEG q=70) pour tenir sous la limite
GitHub de 100 Mo/fichier. Un ZIP global + un ZIP par équipe (`eq*.zip`) sont produits,
avec des boutons de téléchargement sur le dashboard.

> ⚠️ Les factures sont publiées sur un site **public** (toute personne ayant l'URL
> peut les télécharger). Pour un usage confidentiel, ne pas pousser le dossier `factures/`.

## Détails techniques

- L'export liste les interviews via **GraphQL** (`/graphql`) — l'endpoint REST
  `/api/v1/interviews` est plafonné à 10 résultats et ignore l'offset — puis récupère
  les réponses libellées via `/api/v1/interviews/{id}`.
- Filtre sur le questionnaire `c3a1f062-668d-43e3-a30a-4a424925eaeb` **version 2**
  (la v1 « Mai 2025 » partage le même GUID).
- Prix de référence : Essence 990 F/L, Gasoil 755 F/L (montant calculé de secours
  si `MontRecharge` est vide).
