# Learn⇒Audit : Simulateur d'Audit ISO 2700x

Application web Django permettant aux étudiants de simuler un audit de conformité ISO 27001/27002/27005.

---

##  Architecture du Projet

```
audit_iso/
├── manage.py
├── requirements.txt
├── db.sqlite3               (généré automatiquement)
│
├── learn_audit/             ← Configuration Django (projet)
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
└── audit_app/               ← Application principale
    ├── models.py            ← Modèles de données
    ├── views.py             ← Logique métier et vues
    ├── urls.py              ← Routes URL
    ├── admin.py             ← Interface d'administration
    │
    ├── management/
    │   └── commands/
    │       └── populate_data.py  ← Commande de seed des données
    │
    └── templates/
        └── audit_app/
            ├── base.html          ← Layout global + design system
            ├── home.html          ← Page d'accueil publique
            ├── login.html         ← Connexion
            ├── register.html      ← Inscription
            ├── dashboard.html     ← Tableau de bord auditeur
            ├── scenario_list.html ← Liste des scénarios
            ├── audit_overview.html← Vue d'ensemble d'un audit
            ├── audit_control.html ← Évaluation d'un contrôle
            └── audit_report.html  ← Rapport final
```

---

##  Modèles de Données

| Modèle | Description |
|--------|-------------|
| `Scenario` | Entreprise fictive à auditer (hôpital, e-commerce, banque…) |
| `ISOControl` | Contrôle ISO 27001/27002 (code, description, objectif) |
| `ScenarioControl` | Association Scénario ↔ Contrôle (avec ordre) |
| `Evidence` | Preuve simulée liée à un contrôle d'un scénario |
| `AuditSession` | Session d'audit d'un utilisateur sur un scénario |
| `ControlEvaluation` | Évaluation d'un contrôle par l'auditeur |

---

##  Installation et Lancement

### Prérequis
- Python 3.9+
- pip

### Étapes

```bash
# 1. Cloner / décompresser le projet
cd audit_iso_v2

# 2. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer la base de données
python manage.py migrate

# 5. Charger les données initiales (scénarios, contrôles, preuves)
python manage.py populate_data

# 6. Créer un compte administrateur
python manage.py createsuperuser

# 7. Lancer le serveur de développement
python manage.py runserver
```

Accéder à l'application : **http://127.0.0.1:8000/**
Interface admin : **http://127.0.0.1:8000/admin/**

---

##  Scénarios inclus

| Entreprise | Secteur | Difficulté | Contrôles |
|------------|---------|------------|-----------|
| Hôpital Saint-Luc | Santé | Avancé | 5 |
| BoutiqueShop SAS | E-Commerce | Intermédiaire | 5 |
| SecurePay SA | Banque/Fintech | Avancé | 5 |
| TechConsult SARL | Services | Débutant | 5 |

---

##  Routes URL

| URL | Vue | Description |
|-----|-----|-------------|
| `/` | `home` | Page d'accueil |
| `/login/` | `LoginView` | Connexion |
| `/register/` | `register` | Inscription |
| `/dashboard/` | `dashboard` | Tableau de bord |
| `/scenarios/` | `scenario_list` | Liste des scénarios |
| `/scenarios/<id>/start/` | `start_audit` | Démarrer un audit |
| `/audit/<id>/` | `audit_overview` | Vue d'ensemble audit |
| `/audit/<id>/control/<id>/` | `audit_control` | Évaluer un contrôle |
| `/audit/<id>/report/` | `audit_report` | Rapport d'audit |
| `/api/session/<id>/progress/` | `api_session_progress` | API progression (JSON) |

---

##  Ajouter un Nouveau Scénario

Via l'interface admin (`/admin/`) :

1. Créer un `Scenario` (secteur, difficulté, description…)
2. Associer des `ISOControl` via `ScenarioControl`
3. Pour chaque `ScenarioControl`, ajouter des `Evidence` avec le champ `hint` (conforme/non_conforme/partiel)

Ou directement dans `populate_data.py` en suivant le format existant.

---

##  Design System

Le projet utilise un design system sombre cohérent défini dans `base.html` :
- **Typographie** : Syne (titres) + DM Mono (code) + Inter (corps)
- **Palette** : Dark background (#0a0d14) avec accents bleu/cyan
- **Composants** : Cards, Badges, Buttons, Progress bars, Radio groups

---

##  Système de Score

| Action | Points |
|--------|--------|
| Conformité correctement identifiée | 10 pts |
| Non-conformité ou partiel correctement identifié | 7-10 pts |
| Non-applicable | 5 pts |
| Bonus justification renseignée | +2 pts |
| Bonus recommandation (si NC) | +2 pts |

Score maximum par contrôle : **10 points**
