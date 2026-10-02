# Pécule

**Français** · [English](#-english--personal-accounting-and-budgeting-for-windows)

[![Téléchargements](https://badgen.net/github/assets-dl/andre12230-png/Pecule?label=t%C3%A9l%C3%A9chargements&color=green)](https://github.com/andre12230-png/Pecule/releases)
[![Dernière version](https://badgen.net/github/tag/andre12230-png/Pecule?label=version)](https://github.com/andre12230-png/Pecule/releases/latest)
[![Licence](https://badgen.net/github/license/andre12230-png/Pecule)](LICENSE)

> 📥 **Télécharger pour Windows 10/11** — [page de présentation](https://andre12230-png.github.io/Pecule/) · [installeur `Pecule-Setup.exe`](https://github.com/andre12230-png/Pecule/releases/latest/download/Pecule-Setup.exe) · [archive `.zip` sans installation](https://github.com/andre12230-png/Pecule/releases/latest)

> 📦 Ou en ligne de commande avec **[Scoop](https://scoop.sh)** : `scoop install https://raw.githubusercontent.com/andre12230-png/Pecule/main/bucket/pecule.json`
>
> ⏳ Un paquet **Winget** est [soumis et en attente de revue](https://github.com/microsoft/winget-pkgs/pull/416272) : `winget install` ne le connaît pas encore.

> 💬 **Un problème, une idée ?** Dites-le dans le [questionnaire en ligne](https://forms.cloud.microsoft/r/gBQcGGD33d) — deux minutes, sans compte à créer, toutes les questions facultatives (n'y indiquez ni numéro de compte ni montant). Avec un compte GitHub, vous pouvez aussi [ouvrir un ticket](https://github.com/andre12230-png/Pecule/issues).

Application de bureau pour la **gestion de comptes et de budget personnels** :
suivi des opérations, catégorisation automatique, budgets mensuels, prévisionnel
des opérations récurrentes, rapports et rapprochement bancaire.

Interface **PySide6 (Qt)**, données stockées en **SQLite** local. C'est un portage
Python d'une ancienne application HTML/JS.

> Version publiée : **1.37.0** — premier lancement repensé : importez d'abord votre relevé, Pécule vous demande ensuite le solde et règle seul la date de départ. Et un **récapitulatif de tous vos comptes**. Depuis la 1.35.0, un **installeur Windows** (`Pecule-Setup.exe`) s'ajoute à l'archive `.zip`.

---

## Aperçu

| | |
|:---:|:---:|
| ![Tableau de bord — soldes, budgets, graphiques](docs/media/promo_1_bilan.png) | ![Budgets mensuels par catégorie](docs/media/promo_3_budget.png) |
| ![Liste des opérations](docs/media/promo_2_operations.png) | ![Prévisionnel des opérations récurrentes](docs/media/promo_4_previsionnel.png) |

*Captures réalisées avec des données d'exemple.*

---

## 🇬🇧 English — personal accounting and budgeting for Windows

**Pécule** (French for "nest egg") is a free, open-source desktop application
for tracking personal bank accounts and budgets. It is built with **PySide6 (Qt)** and stores
everything in a **local SQLite** file: no account to create, no cloud, no
telemetry — your financial data never leaves your computer.

> 📥 **Download for Windows 10/11** — [installer `Pecule-Setup.exe`](https://github.com/andre12230-png/Pecule/releases/latest/download/Pecule-Setup.exe) · [`.zip`, no install](https://github.com/andre12230-png/Pecule/releases/latest) · the interface is in French only

**What it does**

- **Transactions** — filterable ledger with reconciliation (cleared/uncleared), inline editing and duplicate detection; multi-row selection lets you clear, unclear, recategorize or delete a whole batch at once (space bar or right-click), with an Undo banner after a deletion; the displayed rows export to a CSV file that opens in Excel
- **Budgets** — monthly per-category budgets with progress bars and overspend alerts
- **Auto-categorisation** — user-defined rules (pattern → category) applied on import, backed by built-in patterns (CARREFOUR → Groceries, EDF → Home…) so the very first statement lands categorised; anything explicit — the bank's own category, your rules, your habits — always wins over the guess
- **Recurring & forecast** — model recurring transactions, project the coming months, and pre-generate the current month's expected entries; each one is later *completed* by the real bank line at import time instead of creating a duplicate
- **CSV, OFX and QIF import** — French bank statement exports; CSV columns are matched by name, so no bank-specific setup (semicolon-separated, windows-1252 or UTF-8). OFX statements are read in both flavours of the format (1.x SGML and 2.x XML), deferred-debit card statements included; QIF files exported from another program are read as well. Imported entries are marked as cleared — a statement only carries transactions the bank has already processed — unless the file itself provides a "Pointage" column (BPCE), which then has the final say. When nothing can be read, the report says why: comma separator, unrecognised column names, or dates outside DD/MM/YYYY
- **Multiple accounts** — track several bank accounts in one file; the account picker drives the whole window. Transactions, budgets, forecast and opening balance belong to each account, while auto-categorisation rules and categories are shared
- **Archiving** — set aside older transactions so lists and period pickers stay short. Nothing is deleted: archived entries stay in the database, and their total rolls into the opening balance, so the displayed balance never changes. A checkbox brings them back, and archiving can be undone
- **Reports** — printable / PDF monthly report, dashboard with KPIs and charts (including a month-end balance line, actual vs forecast), global search
- **Export & restore** — write everything (transactions, rules, budgets, recurring entries, settings) to a JSON file, and merge it back later: on restore the most recent version of each record wins, so nothing newer than the file is overwritten
- **Automatic daily backup** of the database

**Install**

On Windows, the simplest way is the installer:
**[download `Pecule-Setup.exe`](https://github.com/andre12230-png/Pecule/releases/latest/download/Pecule-Setup.exe)**
(always the latest version), run it and follow the wizard. No admin rights
are needed, and uninstalling never deletes your data. Windows may show a
SmartScreen warning because the program is not code-signed: click
*More info*, then *Run anyway*.

Prefer not to install anything? Take the `.zip` from the
[latest release](https://github.com/andre12230-png/Pecule/releases/latest),
unzip it anywhere and run `Pecule.exe`. Either way your data lives in
`%LOCALAPPDATA%\Pecule`; for a truly portable copy (USB stick), close Pécule
and copy your `comptes.db` next to `Pecule.exe`. Or install via [Scoop](https://scoop.sh):

```bash
scoop install https://raw.githubusercontent.com/andre12230-png/Pecule/main/bucket/pecule.json
```

From source (any OS):

```bash
pip install PySide6
python pecule.py
```

A **Winget** package has been
[submitted](https://github.com/microsoft/winget-pkgs/pull/416272) and is
awaiting review; `winget install` does not know about it yet.

Requires Python ≥ 3.9 (developed and tested on 3.13 / 3.14). Licensed under
**MIT**. Windows 10/11 is the primary target, but the code is pure Python + Qt
and runs on Linux and macOS.

> ℹ️ **Note:** the user interface, the built-in manual and the rest of this
> README are in **French**. The CSV importer is tuned for French bank exports.
> Contributions towards internationalisation are welcome — see
> [Issues](https://github.com/andre12230-png/Pecule/issues).
>
> 💬 **Feedback and problem reports** are welcome through a short
> [online questionnaire](https://forms.cloud.microsoft/r/gBQcGGD33d) (in French,
> no account needed) or in the [Issues](https://github.com/andre12230-png/Pecule/issues).

---

## Fonctionnalités

L'application s'organise en onglets :

| Onglet | Rôle |
|---|---|
| 🏠 **Bilan** | Tableau de bord : soldes, KPIs, alertes budget, graphiques, top dépenses |
| 📋 **Opérations** | Liste filtrable des transactions, pointage, édition, doublons |
| 🎯 **Budget** | Budgets par catégorie avec barres de progression |
| 🏷️ **Catégories** | Exploration par catégorie (drill-down), recatégorisation en masse |
| 🔮 **Prévisionnel** | Opérations récurrentes, projection des prochains mois et **génération des échéances du mois** |

Trois outils ne sont pas des onglets mais des boutons du menu de gauche, qui
les ouvrent dans une fenêtre à part : la **📖 Notice** (mode d'emploi et
glossaire), les **🧠 Règles auto** (catégorisation automatique, motif →
catégorie) et **🔖 Ranger sous-catégories** (tri, fusion, renommage), dans le
menu **🧹 Mettre au propre…**.

Autres outils : **import CSV, OFX et QIF** des relevés bancaires (BPCE / CM / CA,
encodage windows-1252), **harmonisation** des catégories et libellés,
**recherche globale** (Ctrl+F), **rapport mensuel** imprimable / PDF,
**export CSV** des opérations affichées (pour Excel),
**export de toutes vos données vers une autre installation**, et **sauvegarde
quotidienne automatique** de la base, plus la **💾 Sauvegarde externe** sur
clé USB ou disque externe, avec un rappel quand la dernière date.

### Dès le premier relevé

Un nouvel utilisateur n'a ni règle ni historique : l'import s'en charge seul.

- Les opérations importées sont **pointées** — un relevé ne porte que des
  opérations déjà passées en banque —, donc le solde du Bilan est juste
  immédiatement, sans avoir à cliquer ligne à ligne. Les relevés qui portent
  eux-mêmes une colonne **Pointage** (BPCE) gardent la main : ce qu'ils
  annoncent « en attente » reste non pointé.
- Elles sont **classées d'après leur libellé** (CARREFOUR → Alimentation,
  EDF → Logement…). Ce qui est explicite passe d'abord — catégorie fournie par
  la banque, vos règles, vos habitudes ; la reconnaissance par motif ne comble
  que ce qui resterait « Non classé ».
- Si rien ne s'importe, le compte rendu **dit pourquoi** : colonnes séparées
  par des virgules, colonnes portant d'autres noms, ou dates hors du format
  JJ/MM/AAAA — avec la manœuvre à faire dans le tableur. Un tableur, un PDF ou
  un export JSON déposé sur la fenêtre reçoit lui aussi son explication.
- **Premier lancement** : le bouton « Importer mon premier relevé… » lit votre
  relevé, puis demande le solde du compte au jour de sa dernière opération ;
  Pécule en déduit seul la date et le solde de départ.
- Sinon, la **date de départ** proposée est le 1<sup>er</sup> janvier de l'année
  en cours, et le Bilan prévient tant que le **solde de départ** n'est pas
  renseigné — ou quand des opérations plus anciennes que cette date restent
  hors du calcul du solde. Il propose alors de reculer la date, en calculant
  le solde de départ qui laisse le solde du jour inchangé.

### Au quotidien

- **Pointer plusieurs lignes d'un coup** : sélection multiple dans la liste
  (Maj+clic, Ctrl+clic, Ctrl+A), puis <kbd>barre d'espace</kbd> ou clic droit.
  La touche <kbd>Suppr</kbd> porte elle aussi sur toute la sélection.
- **Reclasser plusieurs lignes d'un coup** : même sélection, puis clic droit
  → « Changer la catégorie de ces N opérations… ».
- **Annuler une suppression** : après une suppression, un bandeau propose
  « ↩ Annuler la suppression » et remet les lignes telles qu'elles étaient.
- **Exporter vers Excel** : le bouton 📤 Exporter de l'onglet Opérations
  enregistre les lignes affichées (filtres et tri compris) dans un CSV qui
  s'ouvre d'un double-clic dans Excel ou LibreOffice.
- **Courbe du solde** : sur le Bilan, le solde en fin de mois sur douze mois,
  en trait plein pour ce qui est constaté, en pointillés pour ce qui est prévu.
- **Vos propres catégories** : le champ Catégorie s'écrit librement — tapez
  « Animaux », elle est créée, colorée et budgétable comme les autres.
- **Une seule fenêtre à la fois** sur un même fichier de données : deux
  fenêtres ouvertes en même temps se contrediraient.

### Mettre à jour

**Avec l'installeur** : fermez Pécule et lancez le nouveau
`Pecule-Setup.exe`. Il remplace le programme sans toucher à vos données,
rangées à part dans `%LOCALAPPDATA%\Pecule` ; s'il trouve Pécule ouvert, il
demande de le fermer.

**Avec l'archive `.zip`** : décompressez la nouvelle version où vous voulez
(par-dessus l'ancienne, c'est le plus simple) et lancez son `Pecule.exe` : vos
données, rangées à part dans `%LOCALAPPDATA%\Pecule`, sont retrouvées toutes
seules. L'installeur et l'archive partagent ce dossier : on passe de l'un à
l'autre sans rien faire. Avec Scoop, `scoop update pecule` suffit.

**En usage portable** (un `comptes.db` à côté de `Pecule.exe` : installations
commencées avant la 1.22, ou rendues portables en y copiant sa base),
décompressez la nouvelle version **par-dessus** votre dossier Pécule : l'archive
ne contient ni `comptes.db` ni le dossier `sauvegardes`, vos opérations ne
peuvent donc pas être écrasées. Si vous lancez le nouvel exécutable **depuis un
autre dossier** (celui des téléchargements, par exemple), il ne trouve pas
votre fichier de données et ouvre celui de `%LOCALAPPDATA%\Pecule`, vide.
Rien n'est perdu — Pécule indique alors où il range ses données et propose de
**reprendre** le `comptes.db` de votre ancienne installation, qui est copié
sans être touché.
La reprise reste accessible par le bouton **📂 Reprendre un fichier** tant que
l'installation est vide.

Une version plus ancienne peut relire une base récente sans l'abîmer : ce
qu'elle ne comprend pas, elle le laisse en place, et la version récente le
retrouve à la réouverture.

### Plusieurs comptes

Depuis la 1.24.0, Pécule suit **plusieurs comptes bancaires** dans un même
fichier. Une liste **Compte** apparaît au début de la rangée d'onglets dès
qu'il existe au moins deux comptes ; le compte choisi commande tout l'écran
(bilan, opérations, budget, prévisionnel, rapport, recherche). Le bouton
**🏦 Mes comptes** permet d'en ajouter, d'en renommer et d'en supprimer. Le
bouton **📊 Tous les comptes**, à côté, donne, compte par compte, le solde en banque, le
non pointé, le solde comptable et la date du dernier pointage, puis le total.

| | Propre à chaque compte | Commun à tous les comptes |
|---|---|---|
| | Opérations, budgets, prévisionnel, solde et date de départ | Règles automatiques, catégories, sous-catégories, libellés harmonisés |

Une base créée avant la 1.24.0 est reprise telle quelle : tout est rattaché à
un compte « Compte courant » créé au premier lancement, qui hérite du solde et
de la date de départ enregistrés. Qui n'a qu'un seul compte ne voit aucun
changement — la liste reste cachée.

### Archiver les opérations anciennes

Le bouton **📦 Archiver** met de côté les opérations antérieures à une date, sur
un compte ou sur tous à la fois. **Rien n'est supprimé** : les opérations
archivées restent dans la base, mais sortent des listes, des graphiques, des
périodes proposées et des outils. Une case **Voir les archives** les réaffiche,
et **↩ Tout rétablir** annule l'archivage.

Le solde ne change pas : le total des opérations archivées rejoint le solde de
départ, qui se décale au lendemain de la coupure — comme une banque qui ouvre
un relevé sur un solde reporté. La date proposée par défaut est la fin de la
dernière année entièrement plus vieille que trois ans, pour que les années
restent entières et comparables.

### Saisir d'avance les échéances du mois

Le bouton **📅 Générer les échéances du mois** (onglet Prévisionnel) crée en une
fois les opérations attendues du mois d'après vos récurrences. Elles sont
enregistrées **non pointées** et marquées ⏳ : elles apparaissent dans la liste
et dans « ce qui est prévu », mais ne pèsent pas sur le solde en banque.

À l'import du relevé, chacune est **complétée** par la ligne réelle de la banque
— date, montant, libellé d'origine, référence, pointage — au lieu de créer un
doublon, avec une tolérance de 7 jours et deux modes de reconnaissance : même
montant, ou libellé concordant (pour les factures à montant variable). Votre
libellé et votre catégorie sont conservés.

Le Bilan résume tout cela dans son bandeau du mois : **où le compte finira le
mois** (le verdict), puis, sous **🗓 Ce mois-ci**, les sorties et les entrées
encore à venir.

### Transférer vos données vers une autre installation

Deux boutons de **⚙️ Paramètres**, partie « Avancé », servent à transférer
toutes vos données vers une autre installation de Pécule, ou à fusionner deux
installations. Pour une simple sauvegarde, préférez **💾 Sauvegarde externe**
(menu de gauche), qui copie vos données sur une clé USB ou un disque externe et
vérifie la copie :

- **📤 Exporter vers une autre installation…** écrit dans le fichier de votre choix la **totalité**
  de ce que contient le compte : opérations, règles, budgets, récurrences et
  réglages (solde et date de départ compris).
- **♻️ Fusionner un export…** relit un tel fichier et le **fusionne** avec vos
  données au lieu de les écraser : pour chaque opération, règle ou récurrence,
  c'est la version la plus récente qui l'emporte, de même pour les réglages
  de chaque compte (solde de départ, archivage). Rien de plus récent que le
  fichier n'est perdu, et les suppressions sont propagées.

C'est ce qui permet de transporter ses données vers un autre ordinateur, ou de
récupérer un état ancien sans repartir de zéro.

---

## Installation et lancement

**Prérequis :** Python ≥ 3.9 (les annotations `list[...]` l'exigent ; développé
et testé avec 3.13 / 3.14) et la dépendance **PySide6**.

```bash
pip install PySide6
```

**Lancer l'application :**

```bash
python pecule.py
```

**Sous Windows, préférez `py`**, le Python Launcher officiel : quand plusieurs
Python sont installés, `python` désigne celui du PATH, qui n'est pas forcément
celui où PySide6 a été installé.

```bash
py pecule.py
```

On peut aussi double-cliquer sur [`Lancer-Pecule.bat`](Lancer-Pecule.bat) : il
utilise `pyw`, la variante du lanceur qui n'ouvre pas de console noire derrière
l'application (et retombe sur `py` si `pyw` est absent). Ou lancer le paquet
directement :

```bash
python -m comptesbudget
```

---

## Construction d'un exécutable autonome

Le script [`Construire-Exe.bat`](Construire-Exe.bat) produit, via **PyInstaller**,
un **dossier autonome** `dist\Pecule\` : `Pecule.exe` et ses bibliothèques
dans `_internal\`, soit environ 130 Mo — une cinquantaine une fois compressé.
C'est ce dossier qui est publié en `.zip`, et une mise à jour ne remplace que ces
deux éléments : ni `comptes.db` ni `sauvegardes\` ne sont touchés.

```bash
py outils\version_exe.py build\version-exe.txt
py -m PyInstaller --noconfirm --onedir --windowed ^
    --name "Pecule" --icon Budget.ico ^
    --version-file build\version-exe.txt --add-data "Budget.ico;." ^
    --distpath dist --workpath build --specpath build pecule.py
```

Le premier appel écrit les **informations d'identité** du `.exe` (nom, version,
copyright) à partir de `APP_VERSION` : sans elles, l'avertissement SmartScreen de
Windows affiche « Éditeur inconnu » et un panneau vide. Le script passe ces
chemins en **absolu**, car `--add-data`, `--icon` et `--version-file` sont résolus
depuis le `--specpath` et non depuis le dossier courant.

Le point d'entrée reste `pecule.py` : PyInstaller suit l'import du package
et embarque automatiquement tout `comptesbudget/`.

---

## Architecture du projet

Le code est organisé en un **lanceur léger** (`pecule.py`) et un **package
`comptesbudget/`** découpé en couches. Les dépendances sont **strictement
descendantes (graphe acyclique)** : l'interface dépend de la logique, qui dépend
de la fondation — jamais l'inverse.

```mermaid
flowchart TD
    L["pecule.py — lanceur"] --> APP["comptesbudget/app.py — main()"]
    APP --> MW["ui/main_window.py — MainWindow"]
    MW --> V["ui/views/ — 8 vues"]
    MW --> C["ui/ — dialogs · assistants · models · widgets · report · search"]
    MW --> LOG["Logique métier (Python pur)"]
    MW --> F["Fondation"]
    V --> C
    V --> LOG
    C --> LOG
    LOG --> F
    C --> F
    V --> F

    subgraph LOG_G ["Logique métier — testable sans Qt"]
        LOG
        R["rules · labels · recurring · csv_import · ofx_import · qif_import · sync"]
    end
    subgraph F_G ["Fondation"]
        F
        FF["constants · utils · database"]
    end
```

### Arborescence

```
pecule.py            Lanceur (point d'entrée des .bat et de PyInstaller)
comptesbudget/
├── __init__.py
├── __main__.py              Permet « python -m comptesbudget »
├── app.py                   main() : QApplication, palette, lancement
│
│   ── Fondation (Python pur, sans Qt) ──
├── constants.py             Catégories, couleurs, règles d'harmonisation,
│                            fréquences, chemins, numéro de version
├── utils.py                 Dates, formatage €, normalisation, sauvegarde
├── database.py              class Database (schéma + accès SQLite)
│
│   ── Logique métier (Python pur, sans Qt) ──
├── rules.py                 Auto-catégorisation (matches_rule, apply_rules_to_tx)
├── labels.py                Nettoyage et profilage des libellés
├── recurring.py             Occurrences récurrentes + détection automatique
├── csv_import.py            Import des relevés bancaires CSV
├── ofx_import.py            Import des relevés bancaires OFX (compte et carte)
├── qif_import.py            Import des fichiers QIF (autres logiciels)
├── sync.py                  Moteur de fusion (LWW) : export et restauration
│                            de ⚙️ Paramètres › Avancé
├── export_csv.py            Export CSV des opérations affichées (pour Excel)
│
└── ui/                      ── Interface (PySide6/Qt) ──
    ├── models.py            TxTableModel (modèle de table)
    ├── widgets.py           PeriodBar (sélecteur de période)
    ├── flow_layout.py       FlowLayout : barre d'outils qui passe à la ligne
    ├── dialogs.py           Édition : transaction, réglages, règle, récurrence
    ├── assistants.py        Harmonisation, pré-remplissage du prévisionnel
    ├── report.py            Rapport mensuel (HTML, aperçu, PDF, impression)
    ├── search.py            Recherche globale (Ctrl+F)
    ├── main_window.py       MainWindow : assemble onglets et menu d'actions
    └── views/
        ├── operations.py    Vue Opérations
        ├── bilan.py         Vue Bilan
        ├── budget.py        Vue Budget
        ├── categories.py    Vue Catégories
        ├── subcategories.py Vue Sous-catégories
        ├── previsionnel.py  Vue Prévisionnel
        ├── rules_view.py    Vue Règles auto
        └── notice.py        Vue Notice (ouverte en fenêtre, pas en onglet)

outils/
├── captures_promo.py       Refabrique les captures de docs/media/ à partir
│                           d'une base de démonstration inventée
├── faire_archive.py        Fabrique le .zip de la release et son empreinte
├── faire_installeur.py     Fabrique l'installeur Pecule-Setup.exe
├── pecule.iss              Recette de l'installeur (Inno Setup 6)
└── version_exe.py          Écrit les informations de version de l'exécutable

tests/                     Suite pytest : couche métier et smoke tests de l'UI
docs/                      Site de présentation, publié par GitHub Pages
├── index.html             Accueil : téléchargement, captures, description
├── import-csv.html        Aide à l'import, plus une page par banque
├── import-csv-problemes.html
├── confidentialite.html
├── sitemap.xml
└── media/                 Logo et captures d'écran

bucket/pecule.json         Manifeste Scoop (version publiée + empreinte)
winget/                    Manifestes Winget — voir winget/README.md
JOURNAL.md                 Carnet de bord des séances de travail
```

Pour refaire les captures de la page de présentation après un changement
d'interface :

```bash
python outils/captures_promo.py
```

Le script fabrique une base de démonstration dans un dossier temporaire,
photographie les quatre onglets de la vitrine, puis efface cette base. Aucune
donnée réelle n'y figure, et votre `comptes.db` n'est jamais ouverte.

Pour préparer une release, après `Construire-Exe.bat` :

```bash
python outils/faire_archive.py
```

Il ajoute `Lisez-moi.txt` et `Budget.ico` au dossier construit, écrit le `.zip`
puis affiche l'empreinte SHA-256 à reporter dans `bucket/pecule.json` — et,
le moment venu, dans les manifestes Winget de [`winget/`](winget/README.md).

**Ne fabriquez pas ce `.zip` avec le clic droit de Windows.** `Compress-Archive`
écrit les entrées de dossier sans le marqueur « répertoire » : un outil strict
y voit un fichier vide en conflit avec le dossier du même nom et refuse
l'archive, alors que Windows l'extrait sans rien signaler. Le script n'écrit
que des fichiers, et vérifie l'archive produite avant de rendre la main.

Un **installeur** Windows se fabrique de la même façon, avec
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (gratuit :
`winget install JRSoftware.InnoSetup`) :

```bash
python outils/faire_installeur.py
```

Il produit `dist\Pecule-Setup.exe` — un nom **sans numéro**, pour que le lien
`…/releases/latest/download/Pecule-Setup.exe` du site mène toujours à la
dernière version — d'après la recette
[`outils/pecule.iss`](outils/pecule.iss) : installation pour l'utilisateur seul
(sans droits administrateur) dans `%LOCALAPPDATA%\Programs\Pecule`, raccourci
dans le menu Démarrer, désinstallation depuis les Paramètres de Windows. Il ne
livre que le programme : les données restent dans `%LOCALAPPDATA%\Pecule`, que
ni la mise à jour ni la désinstallation ne touchent. Si Pécule est ouvert, il
demande de le fermer au lieu de le fermer de force. L'installeur s'ajoute au
`.zip`, il ne le remplace pas : Scoop et Winget téléchargent le `.zip`.

### Couches

1. **Fondation** (`constants`, `utils`, `database`) — données de configuration,
   utilitaires et accès SQLite. Aucune dépendance vers le reste.
2. **Logique métier** (`rules`, `labels`, `recurring`, `csv_import`, `ofx_import`,
   `qif_import`, `sync`) —
   pur Python, **testable sans interface graphique**. Ne dépend que de la fondation.
3. **Interface** (`ui/`) — widgets, dialogues et vues PySide6. La fenêtre
   principale assemble cinq onglets ; trois autres vues (la notice, les
   règles automatiques et les sous-catégories) s'ouvrent en fenêtre depuis le
   menu de gauche. Aucune vue n'en instancie une autre.

---

## Données et fichiers

Depuis la **1.22.0**, les données ne vivent plus forcément à côté du programme.
`_data_dir()` (`comptesbudget/constants.py`) tranche entre deux cas :

- **S'il existe déjà un `comptes.db` à côté de l'application**, c'est celui-là
  qui sert et rien ne bouge : l'installation reste « portable », comme dans les
  versions précédentes, ou parce qu'on y a copié sa base pour un usage portable.
  C'est aussi ce qui se passe avec Scoop, dont le
  mécanisme `persist` place justement le fichier à cet endroit.
- **Sinon** — installation neuve, par l'installeur, l'archive `.zip` ou
  Winget — les données vont dans
  `%LOCALAPPDATA%\Pecule`. C'est indispensable : un gestionnaire de paquets
  remplace le dossier du programme à chaque mise à jour, et emporterait la base
  avec lui.

Les deux fichiers de données suivent ce dossier ; `Budget.ico`, lui, accompagne
le programme :

| Fichier / dossier | Contenu | Versionné ? |
|---|---|---|
| `comptes.db` | Base SQLite (opérations, budgets, règles, récurrences, réglages) | non (données perso) |
| `sauvegardes/` | Copies quotidiennes automatiques de la base (les 10 dernières, plus la première de chacun des 12 derniers mois) | non |
| `Budget.ico` | Icône de l'application | oui |

La sauvegarde quotidienne est effectuée **au lancement, avant l'ouverture de la
base** : même une migration ratée ne peut pas abîmer la copie du jour.

Les fichiers écrits par **📤 Exporter vers une autre installation…** (⚙️ Paramètres › Avancé) ne vivent pas là : ils vont où
vous les enregistrez, sous le nom que vous choisissez.

---

## Notes de développement

- **Module `sync.py`** : le moteur de fusion par enregistrement
  (*last-write-wins*) a été écrit pour la synchronisation avec l'ancienne
  application HTML, retirée en v1.9.5. La synchronisation automatique, elle,
  n'existe plus — mais le moteur sert toujours : c'est lui qui porte les
  boutons **📤 Exporter vers une autre installation…** et **♻️ Fusionner un export…** de ⚙️ Paramètres ›
  Avancé (`ui/main_window.py`, méthodes `action_export` et `action_import_json`).
- **Couche métier testée** : `rules`, `labels`, `recurring`, `csv_import`,
  `ofx_import`, `qif_import` et `database` s'importent et s'exécutent sans Qt. Une suite de
  tests unitaires (`tests/`) couvre le formatage, l'auto-catégorisation, les occurrences
  récurrentes, le nettoyage des libellés et les imports CSV, OFX et QIF (dédoublonnage
  compris).
  La couche UI (PySide6) est couverte par des *smoke tests* : chaque vue et
  dialogue est construit en mode « offscreen » puis rafraîchi, pour détecter
  les plantages et erreurs de câblage sans serveur d'affichage.
  Enfin, `test_compat_python.py` relit le code source pour vérifier qu'aucune
  annotation n'emploie la notation `X | Y`, réservée à Python 3.10 : elle
  ferait échouer le démarrage sur la version 3.9 annoncée en prérequis.

  ```bash
  pip install -r requirements-dev.txt
  pytest
  ```
- **Qualité** : le code passe `ruff` sur le jeu de règles *pyflakes* **F**
  (aucun import manquant, aucun nom non défini, aucun import inutilisé). Ce
  jeu doit être demandé explicitement : sans `--select F`, `ruff` ajoute ses
  règles de style par défaut, que ce code ne suit pas (instructions séparées
  par des points-virgules, notamment).

  ```bash
  ruff check --select F comptesbudget
  ```

---

## Licence

Distribué sous licence **MIT** — voir le fichier [`LICENSE`](LICENSE). Vous êtes
libre d'utiliser, modifier et redistribuer ce logiciel, y compris à des fins
commerciales, à condition de conserver la mention de copyright.

> ⚠️ **Confidentialité** : aucune donnée personnelle n'est incluse dans ce dépôt.
> La base `comptes.db` est créée vide au premier lancement et reste sur votre
> machine. Elle n'est jamais versionnée (voir `.gitignore`).
