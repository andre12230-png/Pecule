# Journal du projet Pécule

Carnet de bord des décisions et des étapes importantes.
La date la plus récente est en haut.

> Ce journal a été ouvert le **31 août 2026**. Il ne remplace pas le
> **journal de version** en tête de `comptesbudget/constants.py`, qui reste la
> référence de ce que chaque version publiée apporte : celui-ci raconte les
> séances de travail — ce qui a été fait, pourquoi, et ce qui reste ouvert —
> y compris quand elles ne donnent lieu à aucune version. Les entrées
> antérieures à cette date n'ont pas été reconstituées ; l'historique d'avant
> se lit dans `constants.py` et dans les messages de commit.

---

## 2026-09-01 — L'abonnement Claude AI en récurrence mensuelle

**Fait.** Ajout de l'opération récurrente « Anthropique (Claude AI) » sur le
Compte courant : 21,60 € le 1er de chaque mois, catégorie Abonnements,
type Carte bancaire, à partir du 1er septembre 2026. Insertion faite avec
`Database.insert_recurring()` plutôt qu'en SQL direct, base sauvegardée avant.

**Pourquoi.** Le libellé est le point délicat. La banque écrit
« Anthropique », pas « Claude AI » : or le prévisionnel rapproche une échéance
de l'opération réelle en comparant les libellés normalisés, mot à mot, le plus
court devant être le DÉBUT du plus long. Une récurrence nommée « Claude AI »
donne la clé `claude`, qui ne correspond jamais à `anthropique` — l'échéance
serait restée éternellement non soldée, en double avec l'opération réelle à
chaque import. En commençant par le mot de la banque, la clé devient
`anthropique claude`, dont `anthropique` est bien le préfixe : le
rapprochement fonctionne. Vérifié en simulant l'arrivée du relevé sur une
copie de la base.

**Puis.** André a signalé que les 21,60 € de septembre n'étaient pas encore
en banque et devaient donc apparaître non pointés. Il avait raison, et le
motif est plus intéressant qu'il n'y paraît : ses 23 opérations prévues de
septembre étaient déjà générées (`prevue=1`, `pointee=0`) ; seule Claude AI
manquait, la récurrence ayant été créée après cette génération. La ligne a
été ajoutée à la main, avec les champs exacts de `_creer_operations` —
date de valeur au 04/10 via `date_debit_differe`, `pointee=0`, `prevue=1`.

**Le vrai défaut, structurel.** L'assistant ne reproposera jamais cette
échéance : `echeances_du_mois` retient une opération si sa date **ou** sa
date de valeur tombe dans la fenêtre du mois. Pour une carte à débit
différé, l'opération du mois M porte une date de valeur au 4 du mois M+1 —
elle solde donc systématiquement l'échéance de M+1. Mesuré : septembre et
octobre sont `_deja=True`, novembre ne le devient qu'une fois l'opération
d'octobre créée. Le défaut ne s'était jamais manifesté parce que Claude AI
est la **seule récurrence de type « Carte bancaire »** sur 24 — les autres
sont des prélèvements et virements, sans différé.

**Corrigé.** André a choisi de réparer le moteur plutôt que de compenser à la
main. Deux tests écrits d'abord, dont un qui échouait bien sur le symptôme
exact (`_deja` vrai pour octobre) ; le second garde le cas ordinaire, où la
date de valeur doit continuer de servir — un prélèvement présenté le 31/07 et
daté du 03/08 solde l'échéance d'août.

La correction tient en une règle : dans `echeances_du_mois`, une opération
payée par **carte** n'est plus rapprochée que sur sa **date d'opération**. Sa
date de valeur est celle du prélèvement groupé du mois suivant, pas le
décalage de quelques jours d'un prélèvement de fin de mois : elle ne dit rien
du mois auquel l'achat se rattache. Le critère « type contenant *carte* »
était déjà écrit deux fois (Bilan, Prévisionnel) ; il devient
`utils.est_paiement_carte()`, à côté de `date_debit_differe` dont il partage
le sujet. Les deux appels existants n'ont pas été refaits — ajouter sans
remanier.

Résultat sur les données réelles : septembre reste soldé, octobre à décembre
repassent à « à proposer », et les 24 échéances de septembre restent toutes
reconnues. 192 tests au vert, aucun écart `ruff` nouveau (les deux points-
virgules signalés préexistaient).

**Exécutable reconstruit.** `APP_VERSION` reste à **1.25.3** : comme le
10/08/2026, l'exe installé devance la version publiée pour qu'André profite
tout de suite du correctif. Le numéro sera incrémenté à la prochaine
publication — vérifier alors ce qui est dans le source sans être sorti.
Construit en rejouant les étapes 2 et 3 de `Construire-Exe.bat` (jamais le
`.bat` lui-même, dont la dernière étape écrase l'installation sans contrôle),
puis `Pecule.exe` et `_internal` seuls recopiés vers `F:\budget-app\Pecule` —
`comptes.db` vérifiée par empreinte avant/après, inchangée, et les
10 sauvegardes intactes. L'ancien exe est conservé sous
`Pecule.exe.avant-correction`.

**Contrôler un exe, pas à l'œil.** Chercher `est_paiement_carte` dans le
binaire ne donne rien : le code est compressé dans l'archive PYZ, et un
premier test a donc conclu à tort à son absence. La preuve se fait en lisant
l'archive — `CArchiveReader` puis `ZlibArchiveReader`, et inspection des
`co_names` du module embarqué. Les deux modules la portent bien.

**Classeur, puis alignement des deux outils.** Deux écritures dans
« Budget 2026.xlsx » par Excel COM : Anthropic 21,60 € porté à l'encours CB de
septembre, et « Les Voûtes » (27 €, non pointé) reporté de l'encours d'août
vers celui de septembre — la banque ne l'ayant pas rattaché au lot du 4/09, il
partira au suivant. Le prélèvement du 4 septembre passe de 1006,51 € à
979,51 €. Contrôle après coup en comparant le XML du fichier à celui de sa
sauvegarde : graphiques, graphiques miniatures, tableaux et validations
intacts ; une seule mise en forme conditionnelle a bougé, étendue d'une ligne
pour suivre le tableau.

Restait un désaccord entre les deux outils : Pécule datait le débit de
« Les Voûtes » au 04/09, le classeur au 04/10. Sa date de valeur a été
décalée d'un lot (`date_debit_differe` appliqué à la date de valeur, pas à la
date d'achat). Les deux disent maintenant la même chose — lot du 4 septembre
à 979,51 € sur 26 opérations, 48,60 € reportés au 4 octobre. Le prévisionnel
n'a pas bougé : depuis la correction du matin, les cartes se rapprochent sur
la date d'achat, que la date de valeur ne concerne plus.

**Le piège de la séance.** PowerShell fige le type du premier paramètre passé
à `Value2` sur un objet COM : après un nombre, écrire une chaîne lève
`InvalidCastException` — et dans l'autre ordre, le message s'inverse. Il n'y a
pas de « bon ordre » ; il faut écrire en liaison explicite via `InvokeMember`.
Le premier essai a échoué à mi-parcours et le classeur a été restauré depuis
sa sauvegarde ; la méthode a ensuite été mise au point sur une copie avant de
toucher à l'original. Noté en mémoire avec les quatre autres pièges Excel.

**Reste.**

- Rien n'est **commité** : le dépôt est public, le commit et la publication
  restent à la main d'André.
- ~~Aucune règle de catégorisation pour « Anthropique »~~ — **ajoutée** :
  motif `ANTHROPIQUE`, sens `debit`, vers Abonnements / Abonnements, sans
  montant figé (le tarif d'un abonnement bouge). Simulée sur toute la base
  avant insertion : elle reconnaît les trois opérations existantes, n'en
  reclasse aucune et n'entre en conflit avec aucune des 73 autres règles.
  Vérifiée ensuite par le vrai moteur `apply_rules_to_tx` sur cinq libellés,
  dont un suffixe bancaire et un tarif différent, tous classés — et un
  remboursement (crédit), qui reste bien non classé. Cette règle vit dans la
  base d'André, pas dans le dépôt : elle n'est pas concernée par le commit.
- Les deux appels dupliqués du critère « carte » (Bilan, Prévisionnel)
  pourraient adopter `est_paiement_carte()` — cosmétique, non urgent.

---

## 2026-08-31 — Le README confronté au code : sept écarts

Séance d'audit : plutôt que relire le README, le confronter au code, et
lancer les commandes qu'il annonce au lieu de les croire sur parole. Trois
projets y sont passés le même jour ; celui-ci était le seul à porter un vrai
défaut de fonctionnement.

### Le seul écart qui n'était pas documentaire

`labels.py` annotait `dict | None`, notation apparue en **Python 3.10**, alors
que le README promet 3.9 à deux endroits. Sur un 3.9, l'import du module lève
une `TypeError` et l'application ne démarre pas. Une seule ligne dans tout le
projet, corrigée en `Optional[dict]`, la forme employée partout ailleurs.

`tests/test_compat_python.py` verrouille ce cas. Il relit le code source avec
`ast` au lieu de l'exécuter : il voit donc le problème même en tournant sur
3.13, où il ne se manifeste pas. Il a bien échoué avant la correction, sur la
ligne exacte.

### `sync.py` n'était pas dormant

Le README le présentait trois fois comme *dormant*, « plus câblé à l'interface
depuis la v1.9.5 ». Il porte en réalité les boutons **💾 Exporter (JSON)** et
**♻️ Restaurer (JSON)** du menu de gauche. Deux fonctions visibles par
l'utilisateur, absentes du README en français comme en anglais : une section
les décrit désormais.

### Les cinq autres

- La **Notice** n'est plus un onglet depuis qu'elle s'ouvre en fenêtre — le
  commentaire du code le disait déjà. Le tableau annonçait huit onglets, le
  code en crée sept.
- Sur **`ruff`**, l'affirmation et la commande étaient fausses toutes les deux.
  `ruff check comptesbudget` rend 99 erreurs, car sans `--select F` les règles
  de style s'ajoutent. Restreint au jeu F annoncé, il restait deux imports
  inutilisés : `QFrame`, vraiment mort, retiré ; `_app_dir`, réexport
  volontaire, marqué `noqa`.
- **`comptes_sync.json`** figurait parmi les fichiers de données. `SYNC_PATH`
  n'est qu'une valeur par défaut jamais utilisée : le fichier n'est jamais créé.
- **`docs/`** — les sept pages du site publiées par GitHub Pages — ne figurait
  pas dans l'arborescence, non plus que `tests/`, `bucket/` et `winget/`.
- Le **diagramme** oubliait que `main_window` dépend directement de la
  fondation et du métier. L'architecture n'est pas en cause, les flèches
  manquaient.

### Ce qui reste

- **Les 99 erreurs `ruff` hors jeu F** n'ont pas été traitées : 87 E702 (deux
  instructions sur une même ligne), 7 E741 (noms de variables ambigus), et
  quelques autres. Choix assumé — le README dit maintenant pourquoi la
  commande porte `--select F`. Deux façons de fermer le sujet un jour : les
  corriger, ou poser un `ruff.toml` comme dans les deux autres projets, pour
  qu'un `ruff check` sans argument dise vrai tout seul.
- **La 1.25.3 n'est pas publiée.** La dernière release téléchargeable, le
  manifeste Scoop et `docs/index.html` restent en 1.23.2 ; le code du dépôt est
  en avance de six versions.
- **Le paquet Winget** est toujours en attente de revue.

---
