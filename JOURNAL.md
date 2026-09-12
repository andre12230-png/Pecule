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

## 2026-09-12 — Préparation de la 1.37.0

**Fait.** Les cinq porteurs de version remontés ensemble : `APP_VERSION` et
l'entrée d'historique de `constants.py`, l'en-tête de `Lisez-moi.txt`, la ligne
de version du README, le `softwareVersion` de `docs/index.html`, le manifeste
Scoop (version, url, empreinte `eb1f6ae9…99ab`). README, Lisez-moi et page de
présentation décrivent le nouveau premier lancement et le récapitulatif « Tous
les comptes ». Exe construit sans le `.bat` (étapes 2-3 à la main), archive
(182 fichiers) et `Pecule-Setup.exe` fabriqués. Contrôles : 336 tests ; exe
lancé sur une base d'essai, titre « Pécule — v1.37.0 », fermeture propre ;
installeur joué en silencieux dans un dossier temporaire — installation,
lancement, désinstallation sans reste (inscription, menu Démarrer), base
d'essai inchangée. Manifestes Winget non touchés.
**Pourquoi.** La 1.37.0 réunit le récapitulatif « Tous les comptes », la
correction de l'archivage, le nouveau premier lancement, la proposition de
reculer la date de départ et la correction de la barre de période. Nouveautés
visibles : numéro mineur plutôt que 1.36.1.
**Reste.** Rien n'est poussé ni publié : push, `gh release create v1.37.0`
avec le `.zip` et `Pecule-Setup.exe`, puis contrôle des empreintes
retéléchargées et des badges — sur accord d'André. Installation d'André dans
`F:\budget-app\Pecule` pas encore mise à jour.

## 2026-09-12 — Premier lancement : importer d'abord, le solde ensuite

**Fait.** L'accueil d'une base vide offre « Importer mon premier relevé… » (à
côté de « Reprendre mes données… » et « Démarrer à neuf »). Après l'import, une
seule question : le solde du compte au jour de la dernière opération du relevé.
Pécule règle alors la date de départ (plus ancienne opération) et le solde de
départ (solde donné − opérations pointées passées en banque ce jour-là).
`Database.bornes_operations()` / `depart_depuis_solde()`,
`MainWindow.action_premier_releve()`, notice à jour (rubrique 1 réordonnée : l'import d'abord, le réglage à la
main ensuite). 7 tests
(`tests/test_premier_releve.py`, avec un vrai CSV au format Crédit Agricole),
vus en échec avant ; 336 passent. Parcours joué par capture sur une base
d'essai : le Bilan affiche le solde donné, aucun bandeau.
**Pourquoi.** Demande d'André, après le cas d'un nouvel utilisateur (entrée
ci-dessous) : c'est demander le solde AVANT l'import qui fabrique le piège. On demande le solde à la date de la
dernière opération, pas celui du jour : sinon les opérations d'entre-deux
seraient comptées deux fois au prochain import. Lecture automatique du solde
dans le fichier écartée : formats CSV disparates, et le solde annoncé est daté
du téléchargement (piège du 01/09/2026).
**Reste.** Pas de numéro de version (1.37.0 à venir). Vu en passant et corrigé :
la barre de période restait sur « Toutes périodes » après le premier import
(`PeriodBar` consommait son placement initial sur une base encore vide ; test
ajouté). Fausse alerte : le « Cancel » d'une capture venait du script, qui ne
chargeait pas la traduction Qt (`installer_traduction_qt`). Plus tard peut-être :
pré-remplir le solde depuis l'OFX (`LEDGERBAL` + `DTASOF`).

## 2026-09-12 — Reculer la date de départ sans changer le solde du jour

**Fait.** Quand des opérations précèdent la date de départ, Pécule propose de
reculer la date à la plus ancienne, avec un solde de départ calculé pour que le
solde d'aujourd'hui reste identique (ancien solde − opérations pointées
réintégrées). La question vient après chaque import qui a ajouté des lignes, et
par le lien du bandeau orange du Bilan (qui ouvrait les Paramètres). Trois
réponses : « Reculer la date », « Régler moi-même… », « Laisser tel quel ».
Calcul dans `Database.proposition_recul_depart()` / `reculer_depart()`,
boîte dans `MainWindow.proposer_recul_depart()`, notice (rubrique 1) à jour.
9 tests (`tests/test_recul_depart.py`), écrits avant et vus en échec ;
329 tests passent. Contrôlé par capture sur une base d'essai : même solde
avant et après, bandeau disparu.
**Pourquoi.** Cas d'un nouvel utilisateur (capture du 12/09/2026, 1.33.x) : il
a saisi son solde du jour, puis importé un an de relevé CSV — 350 opérations
hors du solde. Le bandeau disait « reculez la date » sans dire
quel solde mettre en face : un calcul que personne ne fait seul. Le piège
guette tout nouvel utilisateur, puisque le solde est demandé avant l'import.
Pas de proposition si le solde de départ n'a jamais été saisi (rien à
préserver) ni s'il y a des archives (le départ effectif en dépend) : le lien
retombe alors sur les Paramètres. Les deux comptes d'André n'ont aucune
opération avant leur départ : la question ne lui sera jamais posée.
**Reste.** Pas de numéro de version. À la prochaine publication (1.37.0),
ajouter l'entrée au journal de version de `constants.py`. D'ici là, la
manœuvre à la main : Paramètres, date = plus ancienne opération, solde =
solde actuel − total annoncé par le bandeau ; le Bilan doit garder le même solde.

## 2026-09-11 — Récapitulatif « Tous les comptes »

**Fait.** Bouton « 📊 Tous les comptes » sous la liste des comptes (caché tant
qu'il n'y en a qu'un) : une fenêtre (`ui/recapitulatif.py`) donne, par compte,
le solde en banque, le non pointé, le solde comptable et la date du dernier
pointage, puis le total ; un double-clic affiche le compte. Calcul dans
`Database.soldes_compte()`, notice (rubrique 2) complétée, 7 tests
(`tests/test_recapitulatif.py`). Contrôlé sur une copie de la vraie base :
soldes identiques au Bilan de chaque compte.
**Pourquoi.** Premier vrai retour d'un utilisateur via le questionnaire
« Votre avis » : « un récapitulatif de l'ensemble des comptes serait très utile ».
La vue consolidée avait été écartée en 1.24.0 ; André l'a demandée ce jour.
Pour qu'un compte n'affiche jamais deux soldes différents, `soldes_compte`
passe par le même chemin que le Bilan au lieu d'en recopier les règles.
Installé le soir même dans `F:\budget-app\Pecule` à la demande d'André
(exe contrôlé d'abord sur une copie de la base ; ancien exe gardé en
`Pecule.exe.avant-recapitulatif` ; `comptes.db` inchangée).
**Reste.** Pas de numéro de version ni de publication : André ne veut pas
publier tout de suite. À la prochaine publication, ce sera la 1.37.0.
Anomalie repérée en chemin, **corrigée le soir même** à la demande d'André :
archiver une opération pointée datée AVANT la date de départ la faisait
entrer dans le solde (`total_archivees` ignorait la date de départ) ; et une
coupure antérieure au départ faisait « reprendre » le compte trop tôt. Deux
tests dans `tests/test_archives.py`, écrits avant la correction et vus en
échec. Soldes réels inchangés. Correction pas encore
installée dans `F:\budget-app\Pecule` (sans effet sur ses données).

## 2026-09-11 — Fiche Gratilog : demande de passage en 1.36.0

**Fait.** Demande de modification envoyée sur `modfile.php?lid=3695` : titre et
version 1.36.0, lien vers `Pecule-1.36.0-win64.zip` (testé : 54 019 353
octets servis), taille 54 019 353, et trois retouches de la description —
phrase sur le bouton « Mise à jour », mention de l'installeur (proposé sur la
page d'accueil) à côté de l'archive portable, bloc « Changements » vers la
release v1.36.0. Drapeau et loupe conservés.
**Pourquoi.** La fiche affichait encore la 1.33.1 ; un membre (jasonliu777)
avait signalé la 1.36.0 en commentaire. Le lien reste le .zip (habitude de la
fiche, public attaché au portable).
**Reste.** Validation par Sylvie Pierrard, puis relire la fiche champ par champ
(la taille surtout).

Message posté dans le fil du forum (sujet 21527, `post_id` 228327) : installeur,
bouton « Mise à jour », bouton « Votre avis », correction du Bilan. La 1.35.1
(retour du logo) volontairement passée sous silence. Réponse de remerciement
à jasonliu777 sous la fiche (commentaire 10861, en réponse au 10859).

## 2026-09-10 — Version 1.36.0 publiée (bouton « Mise à jour »)

**Fait.** Release `v1.36.0` avec `Pecule-Setup.exe` (premier installeur publié
directement sous son nom fixe) et `Pecule-1.36.0-win64.zip`. Porteurs de
version remontés (`APP_VERSION` + historique, Lisez-moi, README, JSON-LD,
manifeste Scoop). Contrôles avant publication : 311 tests ; exe et installeur
en 1.36.0 installés, lancés et désinstallés en dossier d'essai sur une copie
de la base (aucun `comptes.db` livré, icône = ancien logo). Installation
d'André en 1.36.0, ancien exe gardé en `Pecule.exe.avant-1.36.0`,
`comptes.db` inchangée.
**Pourquoi.** André a demandé la publication. Numéro 1.36.0 : nouveauté
visible (le bouton), plus le lien direct dans la notice et le Lisez-moi.
**Reste.** Winget toujours en 1.23.0 (PR #416272).

## 2026-09-10 — Bouton « 🔄 Mise à jour », sans Internet

**Fait.** Nouveau bouton « 🔄 Mise à jour » (rubrique Aide) et fenêtre
`ui/mise_a_jour.py` : la version installée, « Voir les nouveautés » (page de
la dernière release) et « Télécharger l'installeur » (lien direct), tous deux
ouverts dans le navigateur. Adresses dans `constants.py` (`PAGE_VERSIONS_URL`,
`INSTALLEUR_URL`). Notice (tableau des boutons, § 9) et `Lisez-moi.txt`
complétés. Trois tests, dont un garde-fou : aucun module de `comptesbudget`
n'importe de bibliothèque réseau.
**Pourquoi.** André voulait que Pécule annonce les nouvelles versions au
lancement. Cela exigeait une connexion à GitHub, contraire à la promesse
« aucun accès réseau » (confidentialité, site, revue Winget). Trois voies
présentées ; il a choisi « sans Internet » : pas d'annonce automatique, un
bouton qui confie la vérification au navigateur.
**Reste.** Non publié. Libellé court exprès (largeur du menu, cf. moitié
d'écran).

## 2026-09-10 — Lien direct vers l'installeur

**Fait.** L'installeur s'appelle désormais `Pecule-Setup.exe`, sans numéro
(`pecule.iss`, `faire_installeur.py`). Le fichier de la release `v1.35.1` a
été renommé sur GitHub par l'API (contenu inchangé, aucun téléchargement
perdu : il n'en avait aucun) et ses notes mises à jour. Le bouton du site, son
étape 1 d'installation, le JSON-LD (`downloadUrl`, `installUrl`) et le README
pointent vers `…/releases/latest/download/Pecule-Setup.exe` ; le `.zip` garde
un lien vers la page de la release. Lisez-moi et notice citent le nouveau nom
(ils n'arriveront chez les utilisateurs qu'à la prochaine version). Partie
anglaise du README : ligne « 📥 Download » en tête de section, et rubrique
« Install » réordonnée (installeur d'abord, avec la marche à suivre
SmartScreen ; puis `.zip` et Scoop ; `pip` en dernier). `Lisez-moi.txt` :
lien direct dans « Mise à jour » et dans « Infos » — il ne sortira qu'avec
la prochaine version, le fichier voyageant dans le `.zip` et l'installeur.
Notice intégrée, rubrique 9 : lien cliquable « Télécharger la dernière
version de l'installeur » (le `QTextBrowser` ouvre les liens dans le
navigateur), adresse écrite en clair à côté. Même réserve : il n'arrive chez
les utilisateurs qu'à la prochaine version ; l'exe d'André a été reconstruit
pour qu'il le voie dès maintenant (il affiche toujours v1.35.1).
**Pourquoi.** André voulait un lien direct vers l'installeur. Le lien
`latest/download` de GitHub exige un nom de fichier identique d'une version à
l'autre ; un lien vers le nom numéroté aurait fini par servir une vieille
version.
**Reste.** La `v1.35.0` garde son `Pecule-Setup-1.35.0.exe` : c'est de
l'historique. Ne plus jamais publier l'installeur sous un nom numéroté, sinon
le bouton du site renverra une erreur 404.

## 2026-09-10 — Version 1.35.1 : retour de l'ancien logo

**Fait.** `Budget.ico` et `docs/media/logo.png` remis dans leur état du commit
`b01cf1a` (sac d'argent + jeton €) ; release `v1.35.1` avec installeur et
`.zip`. Contrôles : 308 tests ; icône intégrée à l'exe et à l'installeur
vérifiée visuellement ; installation, lancement et désinstallation en dossier
d'essai ; les deux fichiers retéléchargés identiques au bit près, `v1.23.0`
(Winget) intacte ; release « Latest ». Installation d'André en 1.35.1, ancien
exe gardé en `Pecule.exe.avant-1.35.1`, `comptes.db` inchangée.
**Pourquoi.** André voulait que l'installeur crée la même icône que son
raccourci du Bureau. Celui-ci pointait vers un vieux `Budget.ico` resté dans
`F:\budget-app\Pecule` (les mises à jour ne remplacent pas ce fichier) : le
dessin d'avant la refonte du 11/08. Averti que ce dessin vient d'une banque
d'icônes à la licence inconnue — raison de la refonte —, il a choisi
« ancien logo partout ».
**Reste.** Les badges affichaient encore 1.35.0 juste après la publication
(cache de badgen). Si l'origine de l'icône est un jour contestée, le dessin
« euro évidé » reste disponible au commit `28f5d58`.

## 2026-09-10 — Version 1.35.0 publiée, avec l'installeur

**Fait.** Release `v1.35.0` sur GitHub avec deux fichiers :
`Pecule-Setup-1.35.0.exe` et `Pecule-1.35.0-win64.zip`. Porteurs de version
remontés (`APP_VERSION` + historique, `Lisez-moi.txt`, README, JSON-LD du
site, manifeste Scoop avec url et empreinte). Site, README, `Lisez-moi.txt`
et notice (§ 9) décrivent maintenant les deux façons d'installer et de mettre
à jour, et le passage du `.zip` à l'installeur (« Reprendre mes données »).
Contrôles : 308 tests ; exe et installeur en 1.35.0 installés, lancés et
désinstallés en dossier d'essai ; les deux fichiers retéléchargés depuis
GitHub identiques au bit près, archive `v1.23.0` (Winget) intacte ; release
marquée « Latest ». Installation d'André mise à jour en 1.35.0, ancien
programme gardé en `Pecule.exe.avant-1.35.0`, `comptes.db` inchangée.
**Pourquoi.** André a demandé de publier la nouvelle version avec
l'installeur. Numéro 1.35.0 : une nouveauté (l'installeur) plus la
correction du bandeau.
**Reste.** Manifestes Winget toujours en 1.23.0 (PR #416272 pendante). Le
lien du site mène à la page de la release : l'utilisateur y choisit le
Setup.exe dans « Assets » — un lien direct serait possible en publiant
l'installeur sous un nom sans numéro. SmartScreen inchangé.

## 2026-09-10 — Un installeur Windows (Inno Setup)

**Fait.** Inno Setup 6.7.3 installé sur le PC (winget, pour l'utilisateur).
Nouvelle recette `outils/pecule.iss` et script `outils/faire_installeur.py`,
qui reprend les contrôles de `faire_archive.py` puis produit
`dist\Pecule-Setup-X.Y.Z.exe` (38 Mo). Installation sans droits administrateur
dans `%LOCALAPPDATA%\Programs\Pecule`, raccourci menu Démarrer (Bureau en
option), inscription dans « Applications ». Mise à jour : `_internal` vidé
puis remplacé, rien d'autre. Si Pécule est ouvert, l'installeur (et le
désinstalleur) demande de le fermer ; il ne le ferme jamais de force. README
complété. Essais complets en dossier d'essai, sur une copie de la base :
installation, lancement, mise à jour (reste d'ancienne version nettoyé),
refus propre avec Pécule ouvert, désinstallation — empreinte de la base
identique à chaque étape, aucun `comptes.db` livré ni créé à côté de l'exe.
**Pourquoi.** André voulait proposer aux utilisateurs un exécutable
d'installation plutôt qu'un `.zip` à décompresser soi-même. `_data_dir()`
prévoyait déjà ce cas depuis la 1.22.0 : aucune ligne de l'appli n'a changé.
Inno Setup retenu : gratuit, standard, recette lisible.
**Reste.** Rien de publié. À la prochaine release : joindre le Setup.exe à
côté du `.zip` (qui reste, pour Scoop et Winget — `v1.23.0` intouchable), et
adapter le bouton et les instructions du site, le README et `Lisez-moi.txt`.
L'avertissement SmartScreen demeure (exe non signé) : chantier à part.
Garder l'`AppId` de `pecule.iss` à jamais, et son encodage UTF-8 avec BOM.

## 2026-09-10 — Fausse alerte « opérations antérieures à la date de départ »

**Fait.** Le bandeau orange du Bilan (« N opération(s) antérieure(s) au … »)
compare désormais la **date de valeur**, comme le calcul du solde, et non plus
la date d'opération (`_refresh_hors_solde_alert`, `ui/views/bilan.py`). Test
`test_bilan_ne_signale_pas_un_achat_carte_debite_apres_le_depart` écrit
d'abord (il échouait), puis la correction ; suite complète : 308 réussis.
Contrôlé sur une copie de la vraie base : le bandeau a disparu sur les deux
comptes.
**Pourquoi.** Après l'archivage au 31/12/2022, le compte courant affichait
« 20 opérations antérieures au 01/01/2023 » : les achats carte
de décembre 2022, débités le 04/01/2023. L'archivage (date de valeur) les
avait laissés visibles à juste titre, le solde (date de valeur) les comptait
bien, seul le bandeau (date d'achat) les croyait hors solde. Son conseil,
reculer la date de départ, les aurait comptés deux fois.
Notice mise à jour dans la foulée (c'est la date de débit qui compte). Exe
reconstruit (étapes 2-3 du `.bat` rejouées à la main), contrôlé sur une copie
de la base (« Pécule — v1.34.0 », fermeture propre), puis installé dans
`F:\budget-app\Pecule` : `comptes.db` inchangée.
**Reste.** L'exe installé porte toujours « v1.34.0 » mais contient cette
correction, non versionnée. Rien de poussé ni de publié : elle sortira avec
la prochaine version.

## 2026-09-10 — Un bouton « 💬 Votre avis » et un questionnaire en ligne

**Fait.** Questionnaire Microsoft Forms « Pécule — votre avis » créé
(10 questions facultatives : installation, banque, import, problèmes, idées,
version ; lien court `forms.cloud.microsoft/r/gBQcGGD33d`). Dans l'appli :
bouton `💬 Votre avis` en rubrique Aide (`ui/avis.py`), qui copie la version
de Pécule et de Windows puis ouvre le questionnaire dans le navigateur, avec un
lien secondaire vers les tickets GitHub. Et une **seule** invitation, deux
semaines après le premier lancement, seulement si la base contient des
opérations ; « Non merci » ne revient jamais. Ligne ajoutée au tableau du § 6
de la notice. Cinq tests ; suite complète : 307 réussis.
**Pourquoi.** Les utilisateurs ne remontent rien : le seul canal était un
ticket GitHub, qui exige un compte. Un questionnaire n'en demande pas et ne
publie aucune adresse e-mail. Pécule ne fait qu'ouvrir le navigateur, à la
demande : la promesse « ne contacte aucun serveur » reste vraie. Les deux
réglages de l'invitation portent le préfixe `_meta_` pour ne pas rajeunir
l'horodatage des réglages synchronisés.
Le lien est aussi **publié sur le site et le README** (commit `ef833e8`) :
rubrique « Un problème ? Une idée ? » et rappel après l'installation sur
l'accueil, pied de page, page « Mon relevé ne s'importe pas », contact de la
politique de confidentialité — qui précise que le questionnaire est hébergé par
Microsoft Forms. Qui échoue à installer n'ouvrira jamais l'appli : c'est là
qu'il le trouvera.
**Livré le jour même en 1.34.0** : les cinq porteurs de version remontés
(`constants.py`, JSON-LD d'`index.html`, README, `Lisez-moi.txt` — qui décrit
aussi le bouton —, manifeste Scoop), et le § 3 de la politique de
confidentialité complété, en français et en anglais : le bouton ouvre le
navigateur, l'application ne transmet rien. Exe contrôlé sur une base
d'essai (titre « Pécule — v1.34.0 », fermeture propre).
**Reste.** Attendre les premières réponses (Forms → « Voir les réponses »).

## 2026-09-09 (notices) — Les trois notices confrontées au code

**Fait.** Nouvelle règle de travail posée par André : *avant de reconstruire
l'exe et de déployer, vérifier que la notice est à jour*. Les notices des trois
applications ont donc été relues à côté du code qu'elles décrivent — menus,
libellés de boutons, fonctions ajoutées depuis la dernière relecture.

- **Pécule** : un seul écart. Le tableau « 6. Outils du menu de gauche »
  listait 14 boutons sur les 15 du menu — `📂 Reprendre un fichier` manquait.
  Il était décrit au § 9 (mise à jour), mais introuvable pour qui lit le
  tableau. Ligne ajoutée, avec la précision qu'il n'apparaît que tant que
  l'installation est vide. Le reste est fidèle, y compris les points récents :
  import pointé et classé, pointage en masse, bandeau d'encours et la
  disparition du bloc « Reste pour la carte » en 1.30.7.
- **pv-dashboard** et **Recharges VE** : rien à corriger, leurs notices ayant
  été relues le jour même (TVA autoconsommation pour l'un, audit du nouvel
  utilisateur pour l'autre).

**Pourquoi.** Une notice est figée dans l'exe jusqu'à la construction suivante :
ce qui n'y est pas au moment du `PyInstaller` reste invisible des mois durant.
La relire est donc une étape de la publication, pas une tâche de fond.

**Vérifié.** Aucun fichier source `.py` des trois projets n'a été modifié après
la construction de son exécutable : les exe en place contiennent bien les
notices actuelles. 78 tests d'interface passent après la retouche.

**Reste.** La ligne ajoutée n'est pas dans l'exe déployé. Elle partira avec la
prochaine version — cela ne justifie pas de republier la 1.33.1.

---

## 2026-09-09 (Gratilog) — Le fil rattrape sept versions, et la taille corrigee

**Fait.** Deux gestes sur Gratilog, le fil du forum etant reste a la 1.26.0 du
3 septembre alors que la 1.33.1 est publiee.

- **Message #9 poste dans le sujet** `topic_id=21527`. Un seul message pour les
  sept versions, plutot que sept annonces. Angle choisi : ce qui bloquait un
  nouvel utilisateur (le solde faux apres import faute de colonne de pointage,
  le premier releve entierement en « Non classe », l'import muet qui ne disait
  pas pourquoi), puis le pointage en masse, la fenetre qui descend a 383 px, le
  bandeau de verdict du Bilan. Et, pour ceux qui ont deja installe, le defaut
  des sauvegardes corrige en 1.33.1 — c'est la raison de mettre a jour.
- **Demande de modification de la fiche** (`modfile.php?lid=3695`) portant sur
  un seul champ : la taille annoncee etait restee a **53 843 997 octets**, celle
  de la 1.26.0, alors que l'archive 1.33.1 en fait **53 744 013**. La fiche
  elle-meme etait deja en 1.33.1, description complete, et son lien mene bien a
  l'archive publiee (redirection `visit.php` suivie jusqu'au bout).

**Le piege du titre, a ne pas prendre pour une fiche perimee.** L'onglet du
navigateur et le `<title>` de la page annoncaient « Pecule v 1.23.2 » — deux
versions majeures en arriere — pendant que le corps de la page affichait bien
1.33.1. C'est un **cache** du site : la meme URL avec un parametre en plus
(`&x=<horodatage>`) renvoie le bon titre. Rien a corriger, rien a redemander.

**Pourquoi.** Le fil est le seul endroit ou les lecteurs de Gratilog suivent un
logiciel : deux d'entre eux ont commente en aout, et l'un d'eux avait demande
le multicompte. La fiche, elle, decide de ce que le visiteur telecharge.

**Verifie.** Le message publie en un seul exemplaire (#9, compteur passe a
6 messages), signature automatique presente. Fiche relue apres la demande :
inchangee — c'est normal, une demande attend validation — drapeau `france.gif`
et ligne de la **loupe** toujours en place, les deux elements que la mémoire du
projet signale comme perdus au moindre copier-coller.

**Reste.** Attendre la validation de la taille. La relire ensuite champ par
champ : la validation du 4 septembre avait laisse de cote une partie de la
demande.

---

## 2026-09-09 (vitrine, suite) — Le texte du site remis d'aplomb

**Fait.** Les sept pages de `docs/` confrontees une a une a ce que fait
vraiment la 1.33.1. Trois affirmations etaient FAUSSES, pas seulement en
retard :

- « Le format OFX n'est pas reconnu par Pecule », dit deux fois sur la page
  Credit Mutuel — l'OFX se lit depuis la 1.26.0. La page dissuadait le
  lecteur d'un format qui marche. Sa propre balise `description` annoncait
  pourtant deja « CSV, QIF et OFX » : le corps n'avait jamais suivi.
- « Les operations arrivent NON POINTEES, a vous de les pointer d'un clic »
  (pages Credit Agricole et Credit Mutuel) — depuis la 1.31.0, un releve sans
  colonne de pointage arrive POINTE. On promettait des centaines de clics
  inutiles.
- Le bouton « 📥 Importer CSV » s'appelle « 📥 Importer un releve » depuis la
  1.23.x. Corrige sur les quatre pages qui le nommaient.

**Ajoute, parce que rien ne l'annoncait.** Les formats QIF et OFX sur la page
d'accueil (texte, `description`, JSON-LD) et sur les pages BPCE, Credit
Agricole et import-csv ; deux fiches « Plusieurs comptes » (1.24.0) et
« Archivage » (1.25.0) ; la marche a suivre pour METTRE A JOUR sans croire
avoir tout perdu (1.33.0) ; la categorisation du premier releve par motifs
integres (1.31.0).

**Corrige aussi.** Les deux messages d'erreur decrits dans « Mon releve ne
s'importe pas » ont change (diagnostic en clair depuis la 1.31.0, fichier
tableur signale depuis la 1.32.0). La politique de confidentialite parlait de
CSV et QIF seulement, ignorait les comptes multiples, et annoncait une
rotation des sauvegardes qui, depuis la 1.33.1, ne touche plus aux copies
faites a la main (versions FR et EN). Dates du `sitemap.xml` au 09/09.

**Pourquoi.** Une vitrine qui decrit une autre version que celle qu'on
telecharge coute deux fois : le visiteur renonce a ce qui marche, et celui qui
installe ne trouve pas ce qu'on lui a promis.

**Verifie.** Chaque affirmation confrontee au CODE, pas au journal de version
(`est_passee` dans `csv_import.py`, `_EST_SAUVEGARDE_AUTO` dans `utils.py`,
le filtre de fichiers de `main_window.py`, l'ordre de categorisation).
Balises des sept pages equilibrees (controle par `html.parser`), JSON-LD
relu par `json.loads`, pages servies en local et relues a l'ecran.

**Reste.** Le titre des trois guides par banque dit encore « au format CSV »
alors qu'ils mentionnent maintenant les trois formats : garde tel quel, c'est
ce que les gens tapent dans un moteur de recherche.

---

## 2026-09-09 (vitrine) — Les captures refaites pour la 1.33.1

**Fait.** Les quatre captures de `docs/media/` refaites avec
`outils/captures_promo.py`. Elles dataient du 3 septembre et montraient la
1.26 : entre-temps le selecteur de periode a ete coupe en deux (1.29.0), le
bandeau Encours carte a change de contenu (1.30.0), une tuile a ete renommee
(1.30.5) et le Budget compte a la date d'achat (1.30.2). Aucune de ces
nouveautes n'apparaissait sur la vitrine.

**Pourquoi.** Ces images sont ce qu'un visiteur regarde avant de telecharger.
Une capture en retard de sept versions annonce un autre logiciel que celui
qu'il va installer.

**Rien d'autre a refaire.** La couverture et l'image de partage
(`outils/couverture.py`) ne montrent pas l'interface — logo et texte
seulement — et `smartscreen.png` est une fenetre de Windows : elles ne
vieillissent pas avec les versions. Le HTML de la page n'a pas bouge, les
quatre fichiers portent les memes noms.

**Reste.** La page ne parle que du **CSV** pour l'import (« relevés bancaires
au format CSV »), alors que Pécule lit aussi le **QIF** et l'**OFX** depuis la
1.26.0. Signale a Andre, pas corrige.

---

## 2026-09-08 — Publication de la 1.33.0, puis 1.33.1 : les sauvegardes qui disparaissaient

**Fait.** La 1.33.0 publiée (exe reconstruit, commit, push, release, Scoop,
vitrine, installation d'André mise à jour), puis une **1.33.1** dans la foulée
pour un défaut découvert par le contrôle final.

**Le défaut.** L'installation d'André n'avait **plus aucune sauvegarde
automatique depuis le 3 septembre**. La rotation de `backup_db` gardait les
10 fichiers les plus récents en triant par NOM, sur tout ce qui commence par
`comptes-`. Or une copie manuelle `comptes-avant-quelque-chose.db` se classe
APRÈS les sauvegardes datées — « a » vient après « 2 ». Les dix copies
manuelles du dossier suffisaient donc à faire supprimer, à chaque lancement,
la sauvegarde du jour qui venait d'être créée. Le filet de sécurité était
neutralisé sans un mot. La rotation ne regarde plus que les noms datés
(`comptes-AAAA-MM-JJ.db`) ; les copies faites à la main sont ignorées.

**Vérifié.** Test écrit avant le correctif et vu échouer avec l'ancien filtre
(remis temporairement pour le prouver). Puis en conditions réelles, avec l'exe
1.33.1 : dossier rempli de dix copies manuelles, lancement, la sauvegarde du
jour est là. 302 tests.

**Pourquoi ce défaut a tenu si longtemps.** Il ne se déclenche qu'à partir de
dix copies manuelles dans le dossier — une pratique récente (les sauvegardes
« comptes-avant-… » prises avant chaque modification de données). Aucun test
ne couvrait la rotation.

**Aussi.** Le premier jet du test écrivait dans le dossier `sauvegardes` du
projet : `backup_db(path)` range ses copies dans `_data_dir()`, pas à côté du
fichier qu'on lui passe. Fichier parasite supprimé, test isolé par
`monkeypatch` sur `_data_dir`.

**Contrôles de publication** (les deux versions) : archive retéléchargée depuis
l'adresse publique et comparée au manifeste Scoop — identique ; `scoop install
pecule` réel (empreinte ok, pre_install ok, persist ok) puis désinstallation ;
badges README et vitrine à jour ; `softwareVersion` du JSON-LD servi avec un
cache-buster ; release `v1.23.0` et manifestes Winget intacts (PR #416272 non
soldée).

**Reste.** Rien. La version publiée est la **1.33.1**.

---

## 2026-09-08 — Ce que devient une installation qu'on met à jour

**Fait.** Les quatre chemins de mise à jour joués pour de vrai, puis deux
corrections.

- **Une base ancienne se migre sans perte.** Une vraie sauvegarde de juin 2026
  (avant les comptes multiples, les échéances prévues et l'archivage), remplie
  comme l'aurait fait cette version, puis ouverte par la version actuelle :
  4 opérations, 2 283,31 € de somme, budget et règle retrouvés à l'identique,
  compte « Compte courant » créé avec le solde et la date d'origine, solde
  affiché juste. Une sauvegarde du jour est écrite avant même l'ouverture.
- **Le retour à une version antérieure ne détruit rien.** La 1.23.2 publiée,
  extraite du dépôt, rouvre une base écrite par la version actuelle, la lit et
  accepte un import. L'opération qu'elle ajoute n'a pas de compte (notion
  qu'elle ignore) ; au retour, la migration la rattache — vérifié, elle
  réapparaît.
- **L'archive n'écrase pas les données.** Les trois zips publiés ne contiennent
  ni `comptes.db` ni `sauvegardes/`. L'avertissement en capitales du
  `Lisez-moi.txt` (« vous écraseriez votre fichier comptes.db ») décrivait donc
  un risque que l'archive ne fait pas courir.
- **Le vrai piège**, en revanche, n'était signalé nulle part : lancer le nouvel
  exécutable depuis un AUTRE dossier (Téléchargements). Sans `comptes.db` à
  côté de lui, Pécule ouvre une base neuve dans le dossier personnel et
  s'affiche vide — de quoi croire tout perdu.

**Les deux corrections.**

1. **Reprendre un fichier.** Une base vide annonce maintenant où elle se
   trouve et propose de reprendre un `comptes.db` existant : il est copié,
   l'original n'est jamais touché, et l'écran se recharge sans redémarrer
   (`Database.rouvrir()`). Un bouton **📂 Reprendre un fichier** garde la porte
   ouverte, visible tant que l'installation est vide (`Database.est_vide()`).
   Garde-fous : fichier vérifié comme base Pécule, refus si des opérations
   existent déjà, refus si c'est le fichier déjà ouvert, retour à la base
   d'origine si la copie échoue.
2. **Le verrou de la 1.32.0 corrigé.** `setStaleLockTime(0)` faisait qu'un
   `pecule.lock` recopié avec le dossier — mise à jour, clé USB, dossier
   synchronisé — venait d'une autre machine : Qt ne peut pas savoir si son
   processus vit encore et l'aurait respecté **pour toujours**, interdisant
   tout démarrage. Délai porté à 30 s. Sur la machine, rien ne change : un test
   prouve que le numéro de processus prime sur l'âge du fichier, donc une
   fenêtre ouverte ne se fait jamais voler son verrou. `faire_archive.py`
   retire un `pecule.lock` d'essai avant de fabriquer le zip.

**Pourquoi.** C'est le moment où un logiciel de comptes peut faire le plus de
dégâts, et celui où l'utilisateur est le plus démuni : il vient de suivre une
procédure, l'écran est vide, il ne sait pas si c'est lui ou le programme.

**Vérifié.** 301 tests. Parcours complet rejoué : ancienne installation à
3 opérations, nouvel exécutable lancé ailleurs, base vide reconnue, reprise
réussie (3 opérations, solde de départ 1 500 € retrouvé), ancien fichier
intact, bouton de secours disparu ensuite, seconde reprise refusée.

**Aussi.** `Lisez-moi.txt` : l'avertissement remplacé par ce qu'il faut
vraiment éviter (supprimer l'ancien dossier avant de coller le nouveau) et par
la marche à suivre quand l'application s'ouvre vide. Même chose dans la notice
(nouvelle section 9) et dans le README. Version **1.33.0**.

**Reste.** Rien de publié : la dernière release est toujours la 1.26.0.

---

## 2026-09-08 — Le reste de l'audit du nouvel utilisateur

**Fait.** Les six points laissés ouverts le matin, traités dans l'ordre.

1. **Date de départ** : le 1er janvier de l'année en cours remplace le
   « 2025-01-01 » figé dans le code. Bases neuves seulement — une base déjà
   réglée n'est jamais réécrite, c'est vérifié par un test.
2. **Deux bandeaux sur le Bilan.** « Solde de départ non renseigné » : l'invite
   du premier lancement ne revenait plus dès qu'on l'avait fermée, et valider
   son formulaire sans y toucher enregistrait 0 € pour toujours — une
   confirmation le demande maintenant, une seule fois. « N opérations
   antérieures au JJ/MM/AAAA » : leur total sortait du solde sans un mot.
3. **Pointage en masse** : la liste passe en sélection multiple, barre d'espace
   ou clic droit pour pointer ou dépointer d'un coup ; la touche Suppr porte
   elle aussi sur toute la sélection, avec son nombre dans la question.
4. **Le menu de gauche défile.** Mesuré, pas supposé : ses seize boutons
   réclamaient 730 px et fixaient à eux seuls la hauteur minimale de la fenêtre
   à 754 px — trop pour un portable 1366 × 768. Elle tombe à 383 px, et rien ne
   change sur un grand écran (aucune barre de défilement tant qu'il y a la
   place).
5. **Une seule fenêtre à la fois** sur une même base (QLockFile) : deux
   instances se marchaient dessus en silence, et un import pouvait tomber sur
   « database is locked » — reproduit avant correction.
6. **Glisser-déposer** : un .xlsx, un .pdf ou un .json déposé sur la fenêtre
   était ignoré sans un mot, ce qui faisait croire à un glisser-déposer en
   panne. Chacun reçoit désormais son explication.

**Aussi.** Le champ Catégorie s'écrivait déjà librement — créer « Animaux »
marche, avec couleur et budget — mais rien ne le disait : infobulle sur les
trois formulaires concernés, et un paragraphe dans la notice.

**Vérifié.** 295 tests (9 de plus, chacun écrit avant son correctif). Contrôle
de bout en bout sur une installation neuve : verrou pris puis refusé au second
lancement, date de départ au 01/01/2026, 5 opérations importées et pointées,
les deux bandeaux affichés, hauteur minimale 383 px, dépointage et repointage
en masse, captures à 1280 × 800 et 1280 × 690.

**Incident.** Un premier script de capture a écrit quatre opérations d'essai
dans le `comptes.db` de la racine du projet : `sys.path.insert()` sur le
dossier du projet en fait le « dossier du programme », et le mode portable
choisit alors cette base — quoi qu'on mette dans `LOCALAPPDATA`. Base de
démonstration vide, rien de réel en jeu ; les quatre lignes ont été retirées et
l'état d'origine retrouvé (0 opération, comme la sauvegarde du 04/09). Les
scripts passent maintenant par une copie du code, hors du projet. Noté en
mémoire.

**Reste.** Version portée à **1.32.0**, rien de publié : la dernière release
est toujours la 1.26.0. Les manifestes Winget restent en 1.23.0 tant que la PR
n'est pas soldée. `comptesbudget/ui/views/bilan.py` et `tests/test_ui_smoke.py`
portaient déjà des modifications non commitées avant la séance (travail sur les
cadres du Bilan) : elles sont intactes.

---

## 2026-09-08 — Les trois obstacles du premier relevé

**Fait.** Trois corrections, trouvées en installant Pécule à neuf dans un bac à
sable et en jouant le parcours d'un nouvel utilisateur : premier lancement,
solde de départ, import du relevé de sa banque, lecture du Bilan.

1. **Les opérations importées sont pointées** quand le relevé n'a pas de
   colonne « Pointage » — le cas de presque toutes les banques hors BPCE. Le
   « Solde bancaire réel » du Bilan ne compte que les opérations pointées : sur
   un relevé Crédit Agricole d'essai, il restait affiché à 1 500,00 € (le solde
   de départ) alors que le compte était à 2 845,26 €. Quand la colonne existe,
   elle garde le dernier mot : une ligne « en attente » reste non pointée.
2. **Le classement par motifs s'applique à l'import.** Les motifs intégrés
   (« carrefour » → Alimentation, « edf » → Logement) ne servaient qu'au bouton
   « Harmoniser » : le premier relevé arrivait donc à 100 % en « Non classé ».
   Ils passent maintenant en **dernier** recours, après la catégorie fournie par
   la banque, les règles de l'utilisateur et l'habitude du libellé.
3. **Un import qui ne lit rien dit pourquoi.** Nouvelle fonction
   `diagnostiquer_releve()` : séparateur virgule (Revolut, N26), colonnes
   portant d'autres noms (Boursorama et sa colonne « label »), dates hors du
   format JJ/MM/AAAA. Elle nourrit à la fois le message d'erreur d'en-tête —
   qui ne disait que « En-tête CSV introuvable » — et le compte rendu d'un
   import à zéro opération, jusque-là muet.

**Pourquoi.** Le banc d'essai a joué onze formats de relevés français : sept
passaient, trois échouaient, un s'importait à zéro ligne en silence. Ce qui
marchait chez André marchait parce que la Caisse d'Épargne fournit la colonne
« Pointage » — personne d'autre ne l'a. Les trois défauts se cumulaient sur le
même écran : solde figé, camembert « 100 % Non classé », message d'erreur
opaque. C'est la première impression du logiciel.

**Vérifié.** 286 tests (11 nouveaux, chacun écrit avant son correctif et vu
échouer). Parcours rejoué de bout en bout dans le bac à sable : solde à
2 845,26 €, quatre catégories réparties, camembert et sources de revenus
remplis. Les quatre messages d'import contrôlés en interceptant les boîtes de
dialogue. Notice rendue sans erreur, balises équilibrées.

**Aussi.** README (FR et EN), `Lisez-moi.txt` et la notice intégrée mis
d'accord avec le nouveau comportement — la notice décrivait le pointage
automatique comme réservé aux relevés à colonne « Pointage ». Version portée à
**1.31.0** avec son entrée d'historique dans `constants.py`.

**Reste.** Les autres points relevés pendant l'audit, non traités : la date de
départ figée au 01/01/2025 (un clic sur OK au premier lancement enregistre 0 €
pour toujours, et l'invite ne revient plus) ; l'historique antérieur à cette
date exclu du solde sans un mot ; le pointage impossible en masse (sélection
simple dans la liste) ; la création d'une catégorie possible mais documentée
nulle part ; la fenêtre qui réclame 754 px de haut, trop pour un portable
1366×768 ; deux fenêtres ouvertes sur la même base qui se marchent dessus
(« database is locked » reproduit). Rien n'est publié : la dernière release
reste la 1.26.0.

---

## 2026-09-08 — Colonnes alignées dans les trois cadres du Bilan

**Fait.** Les trois listes du bas du Bilan (dépenses par catégorie, sources de
revenus, plus grosses dépenses) posent maintenant leurs lignes dans une grille
commune au lieu d'une rangée indépendante par ligne. Les quatre colonnes —
pastille, libellé, pourcentage ou date, montant — sont alignées d'une ligne à
l'autre, et les montants cadrés à droite du cadre.

**Pourquoi.** Chaque ligne calculait ses largeurs dans son coin : les
pourcentages et les dates se décalaient, et les libellés n'avaient pas deux
fois la même longueur. Une grille laisse Qt donner à chaque colonne la largeur
de son contenu le plus large, pour toutes les lignes à la fois.

**Aussi.** Les pastilles n'étaient pas centrées sur leur ligne : c'était le
caractère « ● » d'une police plus grande que celle du libellé, posé sur sa
propre ligne de base. Remplacé par un vrai disque peint de 9 px — taille
impaire, comme la hauteur d'une ligne, sans quoi il reste un pixel trop haut.
Écart mesuré : 0 px sur les trois cadres.

**Puis.** Liseré gris retiré : le style de la carte visait « tout QFrame » et
descendait donc sur ses étiquettes, un QLabel étant un QFrame. Il vise
maintenant la carte par son nom (`QFrame#carteBilan`) ; les étiquettes, qui
tiraient de lui leur fond blanc, sont passées en fond transparent.

**Enfin.** Même correction aux quatre autres cadres du Bilan : les tuiles du
haut (`QFrame#tuileKpi`, création et recoloration) et les deux bandeaux
(`#bandeauCarte`, `#bandeauMois`). Chaque étiquette y répétait la bordure et,
sur les tuiles, le trait coloré de 3 px du haut. Une règle
`… QWidget { background: transparent }` accompagne chaque cadre : sans elle,
les étiquettes et les mini-blocs peignent le gris de la palette là où ils
prenaient auparavant le fond du cadre.

**Et.** Le bloc « Reste pour la carte » du bandeau Encours carte est supprimé.
André : « c'est faux, puisque si à la fin du mois je suis en négatif il ne reste
rien pour n'importe quelle dépense ». Le chiffre était plafonné à 0,00 € et,
aligné avec trois autres, se lisait comme un budget encore disponible. Le
calcul (`_reste_du_mois`) reste : il alimente la phrase du détail — « Solde
prévu fin de mois … moins … déjà passés à la carte — il MANQUE … » — et le
verdict du mois précédent. Notice réécrite, et les onze assertions qui
visaient le bloc portent désormais sur cette phrase.

**Exe.** Reconstruit et installé. Étapes 2 et 3 du `.bat` rejouées à la main
(`outils/version_exe.py` puis PyInstaller, chemins absolus), puis mise à jour
de `F:udget-app\Pecule` : `Pecule.exe` copié et `_internal\` en robocopy
/MIR. `comptes.db` inchangée (2 101 248 octets, même horodatage) et les dix
sauvegardes en place. Contrôlé en lançant l'application : titre « Pécule —
v1.30.7 — Compte courant », bandeau carte à trois blocs, cadres du bas alignés
et sans liseré.

**Reste.** `APP_VERSION` est toujours 1.30.7 : l'exe installé contient donc
plus que la 1.30.7, et aucune entrée de version n'a été écrite dans
`constants.py`. À faire si l'on publie.

---

## 2026-09-07 — L'onglet Catégories dit à quelle date il compte (1.30.7)

**Fait.** Une ligne sous le tableau nomme la date utilisée. En date de valeur
et sur un compte à débit différé, elle prévient que l'onglet Budget, qui compte
à la date d'achat, affiche d'autres totaux — et pourquoi. En date d'opération,
elle dit simplement que les deux onglets comptent pareil. La détection du débit
différé (`carte_a_debit_differe`) quitte le Bilan pour `utils.py` : deux écrans
s'en servent maintenant. Test ajouté, notice complétée, 276 tests.

**Pourquoi.** Le point resté ouvert depuis la 1.30.2 : pour septembre, l'onglet
Catégories affichait 248,93 € en Shopping quand le Budget affichait 0,00 €.
Aucun des deux n'a tort — l'un dit ce qui est sorti du compte, l'autre ce qui a
été dépensé — mais rien ne l'expliquait. Trois sorties étaient possibles ;
André a choisi de garder les deux logiques et de les écrire, plutôt que
d'aligner Catégories (ce qui l'aurait éloigné du Bilan) ou de changer de mode
de date (ce qui fausserait la lecture du solde).

**Reste.** Rien sur ce point. Toujours ouvert : la publication — dernier tag
`v1.23.2`, alors que le code et l'exe installé sont en 1.30.7.

---

## 2026-09-07 — Le Bilan tout entier suit le mois choisi (1.30.2 → 1.30.6)

**Fait.** Cinq pas, partis d'un constat d'André sur le bandeau des budgets
dépassés.

- **1.30.2** — l'onglet **Budget** et son bandeau d'alerte comptent les
  dépenses à la **date d'achat**, sans plus suivre le sélecteur « Date ».
- **1.30.3** — le bandeau **« Budget dépassé »** suit la période : « Budget
  dépassé en août 2026 », « Tout près du budget ».
- **1.30.4** — les deux derniers bandeaux calés sur le mois courant, le
  **verdict** et le bandeau vert **« Ce mois-ci »**, suivent à leur tour. Un
  mois clos se raconte au passé (« a fini le mois à… », « ce qui est passé »,
  tuiles « Débité » / « Encaissé »), un mois à venir annonce ce qui est prévu.
  Deux méthodes ajoutées : `_mouvements_du_mois()` et `_creux_du_mois()`.
- **1.30.5** — la tuile **« Mouvement du mois »** s'appelle « Mouvement de
  l'année » ou « Mouvement — toutes périodes » selon la période.
- **1.30.6** — **« Pointé sur la période »** devient **« Mouvement pointé »**,
  la période passant dans son sous-titre.

**Pourquoi.** « Dans le bandeau budget dépassé, la plupart sont des dépenses
carte du mois d'avant » : vérifié, sur les cinq catégories annoncées dépassées
le 07/09, **une seule l'était** (Banque et assurances, des prélèvements).
Restaurants & Sorties affichait 147 % pour un mois sans un seul restaurant —
c'était le lot de la carte d'août, débité le 4. Un budget répond à « qu'ai-je
dépensé ? », pas à « qu'a prélevé la banque ? ». Puis, de fil en aiguille : si
le Budget suit la période, tout le Bilan doit la suivre, sinon il dit deux
choses à la fois sans le signaler.

**Contrôles.** Le solde de fin de mois sort du même calcul pour les quatre
bandeaux : ils ne peuvent pas se contredire. Vérifié sur la vraie base — août
part de −316,43 € (fin juillet), −2 439,02 € débités, +3 873,76 € encaissés,
−1 016,31 € de carte → **102,00 €**, le solde affiché. 275 tests, six tests
ajoutés dont deux reproduisant le défaut avant correction. Exe reconstruit et
installé à chaque version (`Pecule.exe.avant-1.30.x` conservés, `comptes.db`
jamais touchée).

**Reste.** L'onglet **Catégories** suit toujours le sélecteur « Date » : en
date de valeur, il attribue un achat d'août à septembre et peut donc
contredire le Budget — à trancher. **Rien n'est publié** : le dernier tag reste
`v1.23.2`, et Scoop, README, `Lisez-moi.txt` et la vitrine annoncent toujours
cette version-là.

---

## 2026-09-07 — « Reste pour la carte » ne descend plus sous zéro (1.30.1)

**Fait.** Le chiffre pouvait afficher un montant **négatif** quand le mois se
terminait déjà dans le rouge. Il est désormais borné à **0,00 €**, en rouge.

**Pourquoi.** Remarque d'André : « comme à la fin du mois le prévisionnel est
négatif, pour les achats carte il reste 0 € ». Il a raison — « ce qui reste »
répond à « combien puis-je encore dépenser ? », et la réponse est *rien*, pas
*moins tant*. Le montant qui **manque** est une autre question, et il était
déjà dit dans le détail à droite du bandeau : rien n'est perdu.

**Reste.** Rien. Notice et journal de version à jour, 269 tests.

---

## 2026-09-07 — Le bandeau Encours dit ce qui reste vraiment (1.30.0)

> Les montants de ce journal sont volontairement absents ou donnés en exemple :
> le dépôt est public, et les chiffres d'un compte réel n'y ont pas leur place.
> Le détail chiffré des séances vit dans un journal privé, hors dépôt.

**Fait.** Le bandeau Encours carte du Bilan a été repris en plusieurs temps
dans la même séance.

*D'abord :* un chiffre « disponible », le bandeau qui suit la période choisie,
le verdict du mois écoulé, et une estimation de fin de mois à partir du 10.

*Puis la correction de fond.* Le disponible se comparait au **plafond fixe**
saisi dans les Paramètres (1.28.0) et pouvait annoncer qu'il restait de la
marge pendant que le bandeau juste en dessous prévoyait un solde **négatif** en
fin de mois. Les deux se contredisaient.

**Ce qui a changé.** Le chiffre s'appelle **« Reste pour la carte »** et vaut :
*solde du compte à la fin du mois, une fois tout payé* **moins** *les achats
déjà engagés sur la carte*. Pour le mois en cours, ce solde est celui du
bandeau « Ce mois-ci » — les deux ne peuvent donc plus se contredire. Pour un
mois clos, c'est le solde réellement constaté au dernier jour.

**Le plafond est retiré**, du bandeau comme des Paramètres. La valeur reste
dans la table `settings`, simplement inutilisée : aucune donnée n'est effacée.

**Deux lectures ont été chiffrées avant de trancher** : partir du **compte**
(report des mois précédents compris) ou juger le **mois seul** (entrées moins
sorties hors lot carte). La première a été retenue — la seule qui ne puisse pas
contredire le bandeau voisin, puisqu'elle en part.

**Puis le jour du découvert.** Après un tour d'horizon critique de l'écran
Bilan (cinq points pour, cinq contre, puis cinq améliorations classées), une
ligne annonce désormais **le jour** où le compte passera sous zéro, l'opération
qui fait basculer et le point le plus bas. Un total de fin de mois ne dit pas
QUAND on plonge, or le creux vient souvent du **calendrier** : le lot carte est
prélevé le 4-5 quand les pensions arrivent le 7 et le 9. Un mois peut finir à
l'équilibre en étant passé dans le rouge au milieu.

**Horizon de 45 jours**, pas la fin du mois : il faut voir le prélèvement carte
du 4 du mois suivant **et** la remontée derrière. Le calcul réutilise
`_lignes_a_venir` (opérations enregistrées + échéances du Prévisionnel non
couvertes), cumule dans l'ordre des dates, retient le premier jour négatif et
le point le plus bas. Il ne compte que le **connu** : les achats à venir
creuseront le trou d'autant.

**Cartes SANS débit différé.** Défaut reproduit par un test avant d'être
corrigé : sur un compte à débit immédiat, le bandeau s'affichait avec trois
zéros et **retranchait les achats une seconde fois** du solde de fin de mois,
alors qu'ils en étaient déjà sortis. Il s'efface désormais entièrement — le
« Solde au … » du bandeau vert répond déjà à la question. Reconnu **sans
réglage**, à la trace laissée dans les données : une opération carte dont la
date de valeur dépasse la date d'achat. Un réglage aurait obligé l'utilisateur
à savoir ce qu'est un débit différé avant de s'en servir.

**La saisie manuelle imposait le différé elle aussi** : tout achat par carte en
débit voyait sa date de valeur reportée au 4 du mois suivant. Corrigé, avec la
même détection — l'opération en cours de modification comptant elle-même, pour
que corriger le type d'un achat déjà différé lui rende sa date. **Les imports,
eux, étaient déjà justes** : l'OFX n'applique le différé qu'à un relevé de
carte séparé, le CSV suit la date de valeur du relevé.

**Le Bilan défile maintenant.** Sa hauteur minimale imposait **1 087 px** à la
fenêtre — 986 pour lui seul — et montait à chaque bandeau ; en dessous, Qt
comprimait et les libellés des panneaux du bas se chevauchaient. Un
`QScrollArea` autour de son contenu : la fenêtre descend désormais à **811 px**
sans rien écraser, et les ajouts futurs ne la feront plus monter.

**Un verdict en tête.** La ligne du découvert ouvre par le résultat du mois :
où le compte finit, à partir de quand il est négatif, l'opération qui fait
basculer, le point le plus bas. Vert quand le compte tient. Il parle toujours
du mois **en cours**, même en consultant un mois passé : c'est un verdict pour
agir. En contrepartie, **le bandeau « Ce qui est prévu » (15 jours) est
retiré** : son « solde à quinze jours » était un jalon arbitraire là où le
verdict donne le **pire** moment. Ses deux apports uniques — les trois
prochaines échéances nommées et les opérations carte en cours — sont repris
dans le bandeau « Ce mois-ci », qui reste seul.

**Le graphique montre douze mois.** Il suivait la période affichée et ne
dessinait qu'**une seule barre** sur un mois — un quart de l'écran pour un
chiffre donné six fois ailleurs. La période **déplace** désormais la fenêtre au
lieu de la réduire (un mois → les douze qui s'achèvent sur lui ; une année →
ses douze mois ; toutes périodes → les douze derniers), avec repli sur les
derniers mois connus si la fenêtre choisie est vide.

**Six tuiles ramenées à quatre.** « Revenus » et « Dépenses » répétaient le
« Mouvement net », dont ils sont les deux moitiés : trois cases pour deux
informations. Ils passent en sous-titre de la tuile devenue **« Mouvement du
mois »**. Et **« Solde pointé » n'était pas un solde** : c'est la somme des
opérations pointées **de la période affichée**, donc un mouvement. À une valeur
voisine du solde réel juste à côté, les deux se confondaient — la tuile
s'appelle maintenant **« Pointé sur la période »**.

**Lisibilité des textes gris.** Les sous-titres des tuiles étaient en **#999
sur blanc**, soit un contraste de **2,8 pour 1** là où le minimum lisible est
4,5. Ils passent en **#555** (7,5:1) et de 8 à 9 points. Même correction pour
les pourcentages des listes du Bilan, pour la **date de valeur** de la liste
des opérations (presque illisible alors qu'elle sert au rapprochement), pour
les **lignes pointées** — qui restent plus claires que le texte normal, comme
le veut le signal « déjà vérifiée », mais lisibles — et pour les assistants.

**Trois pièges rencontrés.**

- **Rendu hors écran** : les captures montraient un graphique **vide**.
  `QChart.SeriesAnimations` part de zéro et le rendu arrivait avant la fin de
  l'animation ; les valeurs des `QBarSet`, elles, étaient justes. Même piège
  pour une ligne du bandeau, invisible parce que le script rendait la fenêtre
  **sans `show()`** — le layout n'était pas encore appliqué.
- **Étiquettes d'axe** : sur douze colonnes, « Oct 25 » ne tient pas et Qt
  tronque en « Oc… ». **Réduire la police n'y change rien**, le découpage se
  faisant à la largeur de la colonne. Les bornes sont passées dans le **titre**
  du cadre, où elles ont toute la place.
- **Largeur des blocs** : le repli des libellés (`setWordWrap`) ramène la
  largeur minimale de la fenêtre, mais rétrécit les blocs au point de couper
  les montants — d'où un `setMinimumWidth` sur les valeurs.

**Vérifié.** 269 tests, dont une trentaine de neufs. Les tests du bandeau ont
été entièrement réécrits sur la nouvelle base de calcul, et ceux qui portaient
sur la fenêtre des 15 jours reportés sur celle du mois, **date figée** — leurs
échéances relatives auraient débordé du mois en fin de mois.

**Reste.** Rien n'est publié : ni release, ni tag, ni manifeste Scoop, et les
fichiers qui s'adressent au visiteur restent sur la version publiée.

---

## 2026-09-07 — Le sélecteur de période coupé en deux (1.29.0)

**Fait.** La barre du haut affiche désormais **‹ [année] [mois] ›** au lieu
d'une seule liste. Le menu de gauche porte « Toutes périodes » et les années,
celui de droite les mois de l'année choisie ; deux flèches reculent ou avancent
d'un cran à échelle constante (un mois reste un mois, une année une année) et
se grisent en bout de course. Le menu des mois se grise sur « Toutes
périodes », qui est à cheval sur toutes les années. Changer d'année garde le
mois affiché s'il existe là-bas, pour comparer un même mois d'une année sur
l'autre.

C'est **le sélecteur de pv-dashboard et de Recharges VE**, tous deux refaits le
même jour : les trois applications se manœuvrent maintenant pareil.

**Pourquoi.** L'ancienne liste rangeait les mois en retrait sous leur année, et
ne dépliait que l'année en cours pour ne pas devenir interminable : atteindre
un mois d'une année passée demandait de choisir l'année, puis de rouvrir la
liste et d'y viser la bonne ligne. Surtout, le geste le plus fréquent — « et le
mois d'avant ? » — tient maintenant en un clic. Coupée en deux, la liste ne
s'allongera plus : le menu des années gagne une entrée par an, celui des mois
n'en gagnera jamais.

**Ce qui n'a pas bougé.** Les valeurs internes (`all`, `2026`, `2026-09`) sont
inchangées : **aucune vue n'a été touchée**, elles filtrent exactement comme
avant. Le mode « Date » et la case « Voir les archives » restent à leur place,
et l'ouverture sur le mois en cours fonctionne comme avant, repli sur « Toutes
périodes » compris quand le mois en cours ne porte encore aucune opération.

**Un choix à noter.** Le mois en cours est **toujours proposé** dans le menu,
même vide — sinon on ne pourrait pas y aller — alors qu'on n'**ouvre** pas
dessus s'il est vide. Proposer et ouvrir sont deux questions distinctes.

**Où.** Cinq fonctions de calcul ajoutées à `utils.py` (`annees_disponibles`,
`mois_disponibles`, `annee_de_periode`, `periode_voisine`, `nom_mois_fr`),
pures et testées à part de l'écran ; `PeriodBar` réécrit dans `ui/widgets.py` ;
section 4 de la Notice remise d'accord avec l'écran. `list_periods` reste comme
liste de référence de ce qui est sélectionnable. 11 tests neufs.

**Vérifié.** Fenêtre rendue hors écran sur une **copie** d'une base réelle :
ouverture sur le mois en cours, flèche gauche vers le mois précédent, passage à
l'année précédente en gardant le mois, « Toutes périodes » qui grise le menu
des mois et les flèches. Balayage de toutes les périodes de toutes les années
sans une erreur. Largeur minimale de la fenêtre **inchangée à 1 082 px**.

---

## 2026-09-05 — Le plafond d'encours carte s'affiche en rouge (1.28.0)

**Fait.** Nouveau réglage **« Plafond d'encours carte »** dans Paramètres : le
montant que l'encours de la carte ne devrait pas dépasser sur un mois. Quand le
**« Total des achats à débiter »** du bandeau Encours du Bilan le dépasse, le
chiffre passe en **rouge** et le détail annonce de combien ; en dessous du
plafond, il annonce ce qu'il reste.

Trois fichiers touchés : `SettingsDialog` (nouveau champ), `action_settings` de
`main_window` (lecture/écriture), et `_refresh_cb_banner` de `bilan.py`
(couleur + ligne de détail). Zéro = pas de plafond, et le bandeau reste
exactement comme avant. Le réglage est commun à tous les comptes et vit dans la
table `settings` : aucune modification de la structure de la base.

**Reste.** *(Ajouté le 07/09/2026 : ce plafond a été retiré en 1.30.0. Un
repère fixe pouvait annoncer qu'il restait de la marge pendant que le bandeau
voisin prévoyait un solde négatif en fin de mois ; le calcul part désormais des
mouvements réels. La valeur reste dans la base, inutilisée.)*

---

## 2026-09-05 — Ce que peut peser l'encours carte : une analyse hors dépôt

**Fait.** Calcul, à partir d'une base réelle, du montant maximum d'encours
carte compatible avec un mois à l'équilibre. Deux lectures selon ce qu'on met
en face des recettes garanties : les charges récurrentes « nues » de la table
`recurring`, ou les charges réellement passées sur un mois complet et sans
exceptionnel. L'écart entre les deux tient aux **factures variables**, qui
peuvent doubler ou décupler d'un mois sur l'autre.

**Ce qu'on en retient pour le logiciel** — le reste étant propre à un compte
donné, et consigné hors du dépôt :

- **Un plafond met à l'équilibre, pas en remboursement.** Le solde cesse de se
  dégrader mais ne remonte pas seul ; ce qui reconstitue un matelas, ce sont
  les recettes exceptionnelles.
- **Le creux de début de mois est un problème de calendrier, pas de niveau** :
  le lot carte est prélevé le 4-5, alors que les pensions n'arrivent que le 7
  et le 9. C'est ce constat qui a fait naître, le 07/09, la ligne « quand le
  compte passe sous zéro ».
- **Une projection linéaire de fin de mois est trompeuse** quand une grosse
  dépense tombe en début de mois : elle peut annoncer un encours cinq fois
  supérieur au réel. D'où le seuil du 10 du mois avant d'oser une tendance.
- **Le mois où l'on dépense n'est pas celui où l'on paie** : juger un mois sur
  son propre encours, jamais sur son solde.

---

## 2026-09-04 — Relevé du 1er au 4 septembre : concordance vérifiée, deux dates recalées

**Fait.** André avait déjà importé le relevé du compte courant (6 opérations) et
mis le classeur à jour avant la séance ; le travail a donc été de **vérifier**, puis
de corriger trois détails.

* **Contrôle croisé à 0,00 €** : banque (copie d'écran de l'espace client),
  Pécule et classeur donnent tous **824,90 € au 04/09**, et **−229,39 €**
  d'encours carte sur les mêmes quatre achats. Le lot prélevé le 04/09 fait
  **−979,51 €** sur 26 opérations, exactement la ligne « CUMUL DES DEBITS
  DIFFERES » du relevé — qui n'a donc pas à être importée telle quelle.
* **Récurrence assurance auto L'olivier : jour 5 → 4.** L'échéancier de
  l'assureur fixe le prélèvement au 4 (49,40 €/mois jusqu'au 04/05/2027) ; la
  récurrence créée le matin même portait le 5, parce que celui d'août était
  tombé le 05/08.
* **Échéance BPCE Assurances de septembre recalée du 05 au 07.** Le 5 est un
  samedi et la banque l'annonce au lundi 7 dans son onglet « À venir ».
* **Classeur, feuille Septembre, D17 : −29,18 → −29,14** (corrigé par André).
  C'était une saisie d'avance recopiée de mars, seul mois où ce montant a
  existé ; avril à août portent tous 29,14 €.

**Pourquoi.** Recaler une échéance décalée par un week-end **avant** l'import est
la seule façon d'éviter un doublon : une fois la ligne pointée à la main, aucune
des clés de rapprochement ne correspond plus. Et un écart de quatre centimes dans
le classeur ne se voit pas tant que la ligne n'a pas de date, mais fausse le mois
dès qu'on la pointe.

**Deux fausses pistes écartées.** L'assurance auto portait un `0` (« en attente »)
dans la colonne Pointage du CSV alors qu'elle était pointée des deux côtés : la
copie d'écran de la banque, solde 824,90 € à l'appui, montre qu'elle est bien
débitée — c'est le fichier qui retardait. Et l'échéancier de L'olivier annonce
**65,09 € le 04/07/2026**, jamais prélevé : ce document date du 24/05 et
l'assureur a revu son plan depuis. Rien à rattraper.

**Reste.** Rien d'ouvert. Pas de date de fin posée sur la récurrence auto
volontairement : le contrat se reconduit au 28/05/2027, seul le montant sera
révisé — l'arrêter ferait disparaître une charge réelle du prévisionnel.

---

## 2026-09-04 (suite) — Masquer les catégories qu'on n'utilise pas (1.27.0)

**Fait.** Les 17 catégories livrées d'origine étaient proposées à chaque saisie, sans
moyen de les retirer : qui n'a ni animaux, ni enfants, ni épargne les voyait quand même.
Un bouton « Catégories proposées… », sous la liste de l'onglet Catégories, ouvre une
fenêtre à cocher. Masquer n'efface **rien** — ni catégorie, ni opération : c'est un filtre
d'affichage, réversible en recochant la case.

**Pourquoi.** Question d'André après avoir vérifié ce que reçoit un nouvel utilisateur :
17 catégories, **aucune sous-catégorie** (elles se créent au fil de l'eau), aucune règle
personnelle, et 12 règles intégrées qui reconnaissent les enseignes françaises via le
bouton « Harmoniser » — lequel **propose** sans jamais décider. Tout est modifiable, les
listes déroulantes étant éditables ; la seule limite était justement ces 17 entrées
indéboulonnables.

**Les deux garde-fous, et pourquoi ils sont à la LECTURE.** Ils sont appliqués dans
`categories_proposees()` plutôt qu'au moment de masquer, pour que la liste se répare
d'elle-même :

* une catégorie portée par **au moins une opération** reste proposée même si elle figure
  parmi les masquées. Sans cela, cette opération ne pourrait plus être reclassée sous son
  propre libellé — et un import ultérieur ressusciterait une catégorie devenue invisible ;
* `Non classé` et `Transaction exclue` ne sont jamais masquables : la première accueille
  tout ce qui arrive d'un relevé sans être reconnu, la seconde sort une opération du calcul
  du solde (cf. les deux pièges du solde).

**Un piège évité.** Les trois dialogues de saisie faisaient
`sorted(set((categories or []) + CATEGORIES_DEFAUT))` : ils **rajoutaient** les 17 d'origine
à la liste reçue. Masquer n'aurait donc rien changé pour eux. Les huit endroits qui
construisent une liste de catégories passent désormais par `categories_proposees()`.

Le réglage est **commun à tous les comptes**, comme les catégories : vérifié que la table
`settings` n'est pas rattachée à un compte, contrairement au solde et à la date de départ.

**Vérifié.** Cinq tests écrits d'abord et vus échouer, puis le code — 232 tests au vert.
La fenêtre a été construite hors écran avec une vraie base : « Alimentation », portant une
opération, ressort verrouillée avec la mention « utilisée par 1 opération(s) », et les deux
catégories structurelles avec « nécessaire au fonctionnement ». Décocher deux catégories
les retire bien des propositions (15 au lieu de 17). L'onglet et l'application entière ont
été rendus à l'écran pour contrôler la place du bouton.

**Puis la francisation des boutons, demandée dans la foulée.** L'application est
entièrement en français mais ses boîtes de dialogue affichaient « Cancel », « Yes », « No » :
ces libellés ne viennent pas du code du projet, **c'est Qt qui les fabrique**.

Solution retenue : charger les traductions que **Qt livre lui-même**
(`qtbase_fr.qm`, fourni avec PySide6) plutôt que de renommer les boutons un par un. Le
renommage manuel aurait laissé de côté les questions Oui/Non, les fenêtres de choix de
fichier, et tout dialogue ajouté plus tard. Résultat vérifié sur une boîte réunissant huit
boutons standard : « Annuler », « Oui », « Non », « Enregistrer », « Fermer »,
« Appliquer », « Aide ».

Deux précautions qui comptent :
* le traducteur est rangé **sur l'objet application** pour rester vivant — ramassé par le
  garbage collector, il cesserait silencieusement de traduire, et le défaut serait
  déroutant à diagnostiquer ;
* trois chemins sont essayés, dont le dossier livré avec PySide6. **Vérifié dans l'exe déjà
  construit** que PyInstaller le recopie bien dans `_internal/PySide6/translations/` : la
  traduction vaudra donc aussi une fois l'application gelée. Si aucun chemin ne répond,
  l'application démarre quand même — quelques mots en anglais valent mieux qu'un refus de
  démarrer.

**Exe reconstruit et installé** en 1.27.0, pour qu'André profite tout de suite des deux
ajouts sans attendre une publication. Étapes 2 et 3 du `.bat` rejouées à la main, comme la
veille. Contrôles : empreinte identique entre `dist/` et l'installation, titre de la fenêtre
« Pécule — v1.27.0 — Compte courant », `comptes.db` inchangée au bit près (2 101 248 octets),
intégrité ok, 6 181 opérations et 33 récurrences intactes. Vérifié aussi que
`_internal/PySide6/translations/qtbase_fr.qm` est bien présent dans l'installation : sans ce
fichier, la francisation des boutons ne vaudrait qu'en développement. Ancien exécutable
conservé sous `Pecule.exe.avant-1.27.0`.

**Reste.** Version **1.27.0** installée localement mais **non publiée** : le site, Scoop et
la release restent en 1.26.0. À la publication :
relancer `outils/captures_promo.py` (le bouton est visible sur la capture de l'onglet
Catégories) et suivre la marche habituelle. Détail sans gravité relevé au passage : les
boutons des fenêtres affichent « OK / Cancel », Qt n'étant pas traduit — c'est le cas dans
**toute** l'application depuis toujours, pas une nouveauté de cette fenêtre.

---

## 2026-09-04 — Fiche Gratilog validée, et une seconde demande pour la description

**Fait.** Gratilog a mis la fiche à jour. Contrôle champ par champ : titre et version en
**1.26.0**, et surtout le **lien de téléchargement** suivi jusqu'au bout — il mène bien à
l'archive `v1.26.0`, 53 843 997 octets, celle publiée la veille. La phrase devenue fausse
(« ne gère qu'un compte courant ») a disparu, et l'administratrice a **ajouté d'elle-même**
un bloc « Changements » renvoyant à la page de release.

Mais **les trois nouveautés n'avaient pas été reprises** dans la description : ni le
multicompte, ni l'import OFX, ni l'archivage — celles-là mêmes que le titre annonce. La
taille du fichier était restée celle de la version précédente. Une seconde demande de
modification a donc été déposée, portant **uniquement** sur ces quatre points.

**Pourquoi.** Une fiche qui annonce la 1.26.0 sans dire ce qu'elle apporte laisse le
visiteur ignorer que le logiciel gère désormais plusieurs comptes — c'est justement la
demande d'un lecteur du forum en août.

**Point de méthode.** La seconde demande repart de la valeur **actuelle** du champ, celle
que l'administratrice a laissée, pour y insérer trois phrases — et non de ma propre
rédaction, qui aurait écrasé son travail, bloc « Changements » compris. Les trois ancres de
remplacement ont été vérifiées une à une avant d'écrire, et la présence du drapeau, du bloc
« Changements » et de la **loupe** contrôlée après coup : cette dernière ligne, invisible
dans le rendu, porte le lien vers la capture d'écran et se perd au moindre copier-coller
approximatif.

**Reste.** Attendre cette seconde validation. À faire alors : relire la fiche **champ par
champ**, la première fois ayant montré qu'une validation ne reprend pas nécessairement tout.
Bon signe au passage : le compteur de téléchargements de la fiche est passé de 64 à **87**
en une journée.

---

## 2026-09-03 (captures) — Les images de la vitrine refaites pour la 1.26.0

**Fait.** Les quatre captures de `docs/media/` dataient du 9 août : elles montraient
l'interface d'avant le multicomptes, l'archivage et l'import OFX — menu de gauche encore
en colonne uniforme, sans « Mes comptes » ni « Archiver », bouton « Importer CSV » au lieu
d'« Importer un relevé ». Refaites avec `outils/captures_promo.py`, qui invente ses
données dans une base temporaire : aucune opération réelle n'y figure jamais.

**Hauteur de capture portée de 913 à 1080.** À l'ancienne valeur, la légende du graphique
d'évolution (« Revenus / Dépenses ») se retrouvait **coupée** en bas de l'image. Vérifié
que l'application n'y est pour rien en rendant la même vue à deux hauteurs : à 1200 px la
légende revient entière. C'est le contenu qui a grandi — le menu de gauche porte désormais
ses titres de sections, et les bandeaux d'information du Bilan tiennent plus de place.

**Pourquoi.** Ces images sont la première chose que voit un visiteur, et `promo_1_bilan`
sert aussi d'image de partage (`og:image`) et de vignette agrandissable sur la fiche
Gratilog. Montrer une interface qui n'existe plus dessert la version qu'on vient de
publier. La fiche Gratilog pointe vers l'URL de la vitrine : elle se met donc à jour
d'elle-même, sans rien à redéposer.

Contrôle après publication : la page sert bien la nouvelle image (`Content-Length` égal à
la taille du fichier commité).

**La couverture refaite dans la foulée.** `docs/media/promo_cover_630x500.png` portait
encore « Comptes et Budget », l'ancien nom, près d'un mois après le renommage — et un sac
d'argent frappé d'un **dollar**, alors que le logiciel ne connaît que l'euro. Personne ne
l'avait vue : elle n'est référencée nulle part, vestige de la couverture itch.io,
plateforme abandonnée en août.

Elle est désormais **fabriquée par `outils/couverture.py`** au lieu d'être composée à la
main, et reprend le logo du projet (le sac frappé d'un €). C'est la vraie leçon de
l'épisode : **un fichier qu'on ne sait pas refabriquer vieillit en silence**. Les quatre
captures, elles, avaient leur script — c'est pour cela qu'il a suffi de le relancer.

**Puis la couverture est devenue l'image de partage.** `og:image` pointait jusqu'ici vers
la **capture du tableau de bord**. Réduite à la vignette qu'affichent les messageries, les
réseaux et les forums, une capture de 1668 pixels de large devient une grille de chiffres
illisible — et le nom du logiciel n'y apparaît nulle part. C'est le rôle d'une couverture,
pas d'une capture.

Une variante **1200 x 630** a donc été ajoutée, dans le rapport 1,91:1 que ces sites
attendent : avec un autre, l'image est recadrée sur les côtés ou rétrogradée en petite
vignette carrée. `og:image:width` et `og:image:height` sont déclarées, ce qui évite aux
sites de deviner. Le 630 x 500 est inchangé et `outils/couverture.py` produit les deux à
partir de la même composition.

Détail de composition : sur l'image large, le bloc est posé **un peu au-dessus du centre
géométrique**. L'œil place le milieu plus haut qu'il n'est ; centré à la règle, l'ensemble
paraissait tomber — 74 pixels de marge en haut contre 152 en bas au premier essai.

Contrôlé après publication : la page déclare bien la nouvelle image et celle-ci répond en
200. Ce qui n'a **pas** été retenu : une bannière en tête du README, qui repousserait la
description sous la ligne de flottaison alors que trois badges et trois appels à l'action
occupent déjà le haut.

**Défaut vu par André, et confirmé par le calcul : le haut du sac disparaissait.** Le lien
du sac, dans le logo, est un `#2d4fb3` ; le haut du dégradé était un `#2B4EAE`. Rapport de
contraste : **1,03** — la même couleur, à un cheveu près. Le nœud se fondait dans le fond
et le logo paraissait amputé.

Les couleurs du logo ont été **mesurées** (comptage des pixels opaques) plutôt que
supposées, et le contraste calculé sur plusieurs fonds candidats avant d'en retenir un.
Le fond passe à un bleu marine profond (`#0F2050` → `#0A1740`) : le lien du sac remonte à
2,15 puis 2,38, et le texte blanc ressort mieux.

Recolorer le logo était l'autre voie ; elle a été écartée parce que **le € est de la même
couleur que le lien** et doit, lui, rester foncé pour se lire sur la panse claire. Un
remplacement de couleur les aurait touchés tous les deux.

**Défaut vu par André : le multicompte n'apparaissait toujours pas.** Les captures refaites
portaient bien le bouton « Mes comptes », mais rien n'y **montrait** la fonction. La cause
est dans `main_window._fill_comptes` : le sélecteur de comptes reste caché tant qu'il n'y
en a qu'un seul, et le titre de la fenêtre ne porte alors aucun nom de compte. La base de
démonstration n'ayant qu'un compte, la vitrine annonçait une nouveauté qu'aucune image
n'illustrait.

La base de démonstration ouvre désormais un **« Livret A »** à côté du compte courant,
alimenté de 150 € par mois. Le sélecteur apparaît, et le choix montre au passage que chaque
compte garde son propre solde de départ. Les captures restent prises sur le compte courant
(`set_compte_courant` y ramène après la création) : aucun de ses chiffres ne bouge, ce qui
a été vérifié en comparant les deux séries.

**Leçon.** Une capture ne prouve une fonction que si le jeu de données la déclenche. Le
bouton dans le menu ne suffisait pas : il fallait deux comptes pour que l'interface montre
qu'elle en gère plusieurs. À vérifier de la même façon pour toute fonction qui ne s'affiche
que sous condition.

**Puis André a demandé de regarder les trois autres captures — à raison.** Le sélecteur y
était bien, mais le passage à 1080 px, décidé pour la légende du Bilan, avait **agrandi
d'autant le vide** sous leurs tableaux : la capture du Budget montrait huit lignes dans une
fenêtre aux deux tiers vide. Corriger un défaut sur une vue en avait créé un sur trois
autres, faute de les avoir regardées après coup.

Le script utilise désormais **une hauteur par onglet** : 1080 px pour le Bilan, 984 pour les
autres — la hauteur minimale de la fenêtre, sous laquelle Qt refuse de descendre. Le vide
qui subsiste sur le Budget est **structurel** et non corrigeable : le menu de gauche
descend plus bas que le tableau, et c'est exactement ce que voit l'utilisateur.

**Deuxième leçon, plus large :** après un réglage qui vaut pour tout le lot, revoir **tout
le lot**, pas seulement la vue qui avait motivé le réglage.

**Contrôle du site, à la demande d'André.** Les six images ont été retéléchargées depuis
l'adresse publique : empreintes **identiques au bit près** aux fichiers du dépôt. Les six
images référencées par la page répondent 200. Et les dimensions réellement chargées par le
navigateur ont été relevées — 1668 × 1080 pour le Bilan, 1668 × 984 pour les trois autres :
ce sont les nouvelles, l'ancienne capture du Bilan faisait 1700 × 984. Un cache qui aurait
servi l'ancienne se serait vu immédiatement.

**Enfin, le cache de Facebook a été vidé pour la page.** Facebook garde l'aperçu d'une
adresse pendant des semaines : sans cela, il aurait continué de montrer l'ancienne image de
partage — la capture du tableau de bord — malgré le changement. Passage par le Débogueur de
partage (`developers.facebook.com/tools/debug/`), bouton « Re-collecter » : « Dernière
analyse » repasse à deux secondes, et Facebook a bien retenu `promo_share_1200x630.png`.

Deux avertissements y sont **sans gravité** et ne doivent pas inquiéter : l'alerte
« il manque `fb:app_id` » ne concerne que les statistiques Facebook, pas l'affichage de
l'aperçu ; et le « code de réponse 206 » est une particularité de GitHub Pages, acceptée
sans problème.

Le lien à partager est celui de la **vitrine**, pas celui de GitHub, qui imposerait son
propre habillage.

**La publication a été faite dans la foulée**, et son texte remplacé : André avait d'abord
laissé l'adresse nue en guise de message. Une adresse seule n'explique pas pourquoi on
partage — trois courts paragraphes à la place (la version, les trois nouveautés, les
garanties : gratuit, français, open source, données locales). L'aperçu reste attaché quand
on modifie le texte : il n'y a rien à craindre de ce côté.

À savoir pour la prochaine fois : **la page « Statistiques de la publication » ne permet
pas de modifier quoi que ce soit** — c'est là qu'André s'était arrêté. Il faut ouvrir la
publication sur le profil, menu « ⋯ » → « Modifier la publication ».

**Reste.** Rien d'ouvert sur les images. Une idée en réserve : une signature illustrée sur
le forum Gratilog, visible sous chaque message — à condition que le site l'autorise, ce qui
n'a pas été vérifié.

---

## 2026-09-03 (Gratilog) — La fiche et le fil mis à jour pour la 1.26.0

**Fait.** Deux gestes sur Gratilog, seul annuaire encore vivant où Pécule est référencé.
La **fiche du catalogue** : demande de modification déposée (titre, version, adresse de
l'archive, taille en octets, description). La fiche reste affichée en 1.23.2 tant que
l'administratrice ne l'a pas validée — c'est le fonctionnement normal. Le **fil du forum** :
une réponse dans le sujet existant plutôt que dans la rubrique « Mises à jour », parce que
c'est là que suivent ceux qui avaient commenté en août.

**Pourquoi.** La description de la fiche ne se contentait pas d'être périmée sur le numéro :
elle affirmait encore « Le logiciel ne gère qu'un compte courant », faux depuis la 1.24.0.
Une fiche fausse sur le fond est plus gênante qu'un numéro en retard. Le message du forum
répond directement à un lecteur à qui il avait été répondu en août que le multicomptes ne
viendrait jamais — autant l'assumer.

**Le piège, évité de justesse.** La description se termine par une ligne BBCode qui
n'apparaît pas dans le rendu et qui porte la **loupe d'agrandissement de la capture
d'écran**. La réécrire sans la recopier l'aurait supprimée sans que rien ne le signale.
C'est la relecture de la *valeur précédente* renvoyée par le formulaire qui l'a montrée.
Même chose pour le drapeau en tête. À noter aussi : un champ annoncé « vide » par la
lecture de page ne l'était pas — l'adresse de l'ancienne archive s'y trouvait bien.

**Signature du forum ajoutée, en texte et non en image.** Aucune règle écrite n'encadre les
signatures sur Gratilog, mais **aucun membre n'y met d'image** — pas même la webmestre,
7 806 messages au compteur : ce sont des configurations matérielles ou des citations. Le
champ est d'ailleurs un simple textarea, sans la barre BBCode qu'ont les messages. Une
bannière du logiciel sous chaque message y aurait détonné et ressemblé à de l'affichage
publicitaire de la part de l'auteur. Deux lignes de texte à la place, dans le ton du site,
avec le lien vers la page de présentation.

L'option **« Toujours attacher ma signature » était sur Non** : sans elle, le champ ne sert
à rien. Passée sur Oui, et vérifié que la signature apparaît bien sous les messages — y
compris les anciens, XOOPS l'appliquant à l'affichage et non à l'enregistrement.

Méthode retenue pour ce genre de question : **quand aucune règle écrite n'existe, regarder
ce que font les membres les plus actifs, et le webmestre en premier.** L'usage tient lieu
de règle, et il était ici sans ambiguïté.

**Reste.** Attendre la validation de la fiche. Framalibre, en revanche, n'a rien à recevoir :
son formulaire crée une notice et n'en modifie aucune, et une notice n'y porte pas de
numéro de version.

---

## 2026-09-03 (publication) — La 1.26.0 est sortie, le gel levé

**Fait.** Publication de la **1.26.0** : multicomptes (1.24.0), archivage (1.25.x),
import OFX et la correction du pointage faite le matin même. Les cinq porteurs du
numéro remontés ensemble — `APP_VERSION` et l'historique de `constants.py` y étaient
déjà, restaient l'en-tête de `Lisez-moi.txt`, la ligne de version du README, le
`softwareVersion` du JSON-LD et le manifeste Scoop. Les deux encadrés ⏳ « en
développement » retirés du README, en français et en anglais.

Archive construite avec `outils/faire_archive.py` (jamais `Compress-Archive`) : 182
fichiers, aucune entrée de dossier. Release `v1.26.0` créée sur le tag du commit de
préparation.

**Pourquoi.** Le gel décidé la veille visait à ne pas déplacer la cible pendant la revue
Winget. Mais la PR #416272 est en revue manuelle **depuis le 22 août**, la relance du
29 août est restée sans réponse, et ces revues durent souvent des mois. Priver les
utilisateurs du multicomptes, de l'archivage et de l'import OFX pendant une durée
inconnue coûtait plus cher que le risque, qui est réparable : si un modérateur demande
la version courante, mettre la PR à jour est courant chez `winget-pkgs`, et le CLA, la
politique de confidentialité et l'échange sur Policy 1.8 sont acquis.

**Ce qui protège la PR, vérifié et non supposé.** Son manifeste déclare une adresse et
une empreinte figées, celles de l'archive `v1.23.0`. Publier une nouvelle release ne les
touche pas : contrôle fait après coup en téléchargeant l'archive `v1.23.0` depuis
l'adresse publique — son empreinte correspond **au bit près** à celle du manifeste
soumis. Les manifestes Winget du dépôt sont restés en 1.23.0, et le `git status` du
dossier `winget/` a été vérifié vide avant le commit.

**Contrôles après publication.** Archive `v1.26.0` retéléchargée depuis l'adresse
publique : son empreinte correspond à celle du manifeste Scoop. Les deux badges — celui
du README qui lit le dernier *tag*, celui de la page qui lit la dernière *release* —
affichent 1.26.0. La page de présentation, interrogée avec une chaîne de requête pour
contourner les deux caches, sert bien le nouveau JSON-LD. L'archive contient l'exécutable
reconstruit le matin, empreinte identique à celle installée sur le poste.

**Contrôle Scoop de bout en bout**, fait après coup : `scoop update` — le bucket ne se
rafraîchit pas tout seul — puis `scoop install pecule`, qui télécharge l'archive depuis
l'adresse publique et **vérifie lui-même son empreinte** (« Checking hash … ok »). Le
`pre_install` a bien créé `comptes.db` comme **fichier** vide et non comme dossier, le
piège qui faisait mourir l'application sur « unable to open database file ». Exe installé
en 1.26.0, empreinte identique à celle du poste. Puis
`scoop uninstall pecule --purge` **aussitôt** : cette copie est vide et son raccourci du
menu Démarrer masquerait l'installation réelle. Vérifié après coup qu'il ne reste ni
dossier, ni données persistées, ni raccourci, et que l'installation de `F:udget-app` est
intacte.

**Reste.** Ne **jamais** supprimer la release `v1.23.0` ni son archive tant que la PR
Winget n'est pas soldée : l'empreinte du manifeste en dépend, et la casser condamnerait
la demande. À la clôture de la PR seulement, remonter les manifestes Winget.

---

## 2026-09-03 (nettoyage) — Purge des données réelles restées dans le dépôt public

**Fait.** Passe complète sur tous les fichiers versionnés, à la recherche de ce qui
identifie André ou son argent. Le journal a d'abord été nettoyé de ses montants (solde,
encours de carte, prix d'un abonnement) et d'un nom de commerce. Mais la recherche élargie
a trouvé bien pire, dans les **tests de l'import OFX** écrits le 1er septembre : le
fixture était un extrait **littéral** d'un relevé, avec le **numéro de compte** (répété
dans l'identifiant de carte, et un second compte dans le test multi-comptes), le montant
d'une pension et le nom de sa caisse, une **référence de mandat SEPA**, les **quatre
derniers chiffres de la carte**, un **numéro de prêt**, l'encours et le solde. Tout est
remplacé par des valeurs rondes ou nulles, manifestement inventées.

Trois autres endroits corrigés au passage : la docstring d'en-tête de `ofx_import.py`, qui
illustrait le format OFX avec la même référence SEPA réelle ; un montant réel dans
`test_csv_import.py` et dans `test_recurring.py` ; et surtout **`docs/import-csv-bpce.html`,
page publiée du site**, dont l'exemple de nom de fichier portait le vrai numéro de compte.

**Pourquoi.** Le dépôt est public : page GitHub Pages, releases, manifeste Scoop. Le même
nettoyage avait été fait en août 2026 ; les tests écrits depuis ont réintroduit des données
réelles, parce qu'ils partent de cas vécus et en gardent les chiffres. **Ce n'est donc pas
un incident isolé mais un risque récurrent** : tout fixture recopié d'un relevé est à
neutraliser avant le commit, pas après.

Deux pièges rencontrés dans le nettoyage lui-même :
1. **Changer une valeur Python sans changer la ligne CSV correspondante casse les tests** —
   c'est arrivé, un test est tombé aussitôt. Un montant vit souvent en trois écritures :
   valeur Python, chaîne du fichier de relevé, et format français `-125,00`.
2. Neutraliser un **libellé** oblige à revoir ce qui s'y accroche : le motif d'une règle de
   catégorisation visait « bouygues », devenu inutile une fois le libellé remplacé.

227 tests au vert après coup.

**Reste.** Les données neutralisées **restent dans l'historique git** et sur GitHub :
retirer une valeur d'un fichier ne l'efface pas des commits antérieurs. Les effacer
vraiment demanderait de réécrire l'historique et de forcer la publication — opération
destructrice, et GitHub conserve un temps les objets devenus orphelins. Décidé de s'en
tenir au nettoyage du contenu actuel, qui est ce que lisent les visiteurs.

---

## 2026-09-03 (fin) — Audit des récurrences contre douze mois de relevés

**Fait.** Chaque récurrence du compte courant confrontée aux opérations réellement passées
en banque sur douze mois (montant médian, jour, régularité), puis recherche inverse : les
opérations mensuelles qu'aucune récurrence ne déclare, via `detect_recurring_candidates`.
Trois corrections appliquées — deux montants revalorisés sans que la récurrence suive, et
un abonnement mensuel que rien ne déclarait. Le script d'audit est conservé dans
`outils/audit_recurrences.py`.

**Pourquoi.** Une récurrence fausse ne se voit pas : le prévisionnel reste plausible. Seule
la confrontation aux relevés la débusque. Le rapprochement de l'audit se fait sur
`_recurring_norm_label`, la même clé que l'application, pour raisonner comme elle.

Quatre pièges méthodologiques rencontrés, à retenir pour un prochain audit :

1. **La médiane sur douze mois ment quand un montant vient de changer** — elle garde
   l'ancien. Regarder les trois ou quatre derniers passages, pas la moyenne.
2. **Un libellé bancaire peut couvrir plusieurs contrats.** Un assureur en portait quatre
   sous le même libellé : l'audit criait « montant instable » alors que la récurrence, qui
   n'en vise qu'un, est juste. C'est la **sous-catégorie** qui sépare les contrats, pas le
   libellé.
3. **« N mois sur 12 » ne veut rien dire sans regarder si ces N mois sont consécutifs.**
   Une récurrence couvrant six mois sur douze semblait sporadique ; ces six-là étaient
   consécutifs et tous le même jour — un abonnement récent. La supprimer aurait creusé un
   trou mensuel dans le prévisionnel. Un compteur de couverture ne distingue pas les deux ;
   seules les dates le font.
4. **Les tranches futures créées volontairement** (voir l'entrée sur les prêts ci-dessous)
   n'ont par construction aucune contrepartie dans le passé : les écarter du rapport avant
   de conclure.

**Le compte secondaire n'avait aucune récurrence** — son prévisionnel était vide. Une seule
lui a été créée, la seule qu'il ait. Son libellé reprend exactement celui de son relevé, qui
diffère d'un caractère de celui du compte courant : les deux clés de rapprochement ne
coïncident pas, et reprendre le libellé d'un compte sur l'autre aurait cassé le pointage.
Vérifié que la nouvelle récurrence ne fait pas doublon avec les échéances déjà saisies
d'avance sur ce compte : elles ressortent « déjà couvertes ».

**Les saisies anticipées vérifiées ensuite.** Quatre opérations étaient à la fois `prevue=1`
et `pointee=1` — combinaison contradictoire, puisque le solde bancaire réel se calcule sur
les opérations **pointées** (`bilan.py`), drapeau `prevue` indifférent : deux d'entre elles
pesaient donc déjà sur le solde sans être confirmées.

**Cause trouvée dans le code, ce n'était pas une fausse manœuvre** : le prévisionnel crée
bien ses échéances avec `pointee: 0` (`previsionnel.py`), et `toggle_pointee`
(`operations.py`) **ne retirait pas le drapeau `prevue`** quand on pointe. Une prévision
confirmée à la main restait donc éternellement affichée comme prévision — et se retrouvait
exclue des candidates au rattachement à l'import (`csv_import.py`, qui exige `prevue and
not pointee`), ne laissant contre les doublons que les filets d'identité.

Trois de ces opérations étaient bien passées : drapeau `prevue` retiré. La quatrième est un
achat par carte **en cours** — fait, pas encore débité : laissée telle quelle, et c'est le
bon état, sa date de valeur au 4 du mois suivant faisant qu'elle n'entrera dans le solde
qu'au débit différé, exactement comme la banque le fera.

**Puis la correction dans l'application.** `toggle_pointee` (`database.py`) retire désormais
le drapeau `prevue` quand on pointe : pointer, c'est dire « la banque l'a passée », donc
l'échéance cesse d'être une prévision. Le retour en arrière ne le rend pas — en dépointant,
rien ne permettrait de deviner que l'opération avait été saisie d'avance.

Fait dans l'ordre : **deux tests écrits d'abord**, vus échouer
(`test_pointer_une_prevision_la_confirme`, `test_depointer_ne_recree_pas_une_prevision`),
puis la correction. Le `CASE WHEN pointee = 0` lit la valeur d'AVANT la bascule — c'est ce
qui distingue « on est en train de pointer » de « on dépointe ». 227 tests passent, et le
comportement a été vérifié sur une **copie** de la base réelle.

Entrée ajoutée au journal de version **sous la 1.26.0**, non publiée et donc encore ouverte,
plutôt que d'ouvrir une 1.26.1 avant même que la précédente soit sortie.

**Exe reconstruit et installé dans la foulée.** `Construire-Exe.bat` n'a pas été lancé
(interactif, et son étape 4 écrase l'installation réelle sans contrôle) : ses étapes 2 et 3
ont été rejouées à la main — `outils/version_exe.py`, puis PyInstaller `--onedir
--windowed` avec chemins **absolus** pour `--icon`, `--version-file` et `--add-data`,
résolus depuis le `--specpath` et non depuis le dossier courant. Mise à jour de
l'installation à l'identique de l'étape 4 : `Pecule.exe` copié et `_internal` synchronisé
par `robocopy /MIR`, rien d'autre — ni la base, ni `sauvegardes/`, qui vivent à la racine
de l'installation et non dans `_internal`. Ancien exécutable conservé.

Contrôles : empreinte SHA-256 identique entre `dist/` et l'installation, titre de la
fenêtre « Pécule — v1.26.0 », base de données inchangée au bit près, intégrité ok.

Note : chercher la chaîne SQL corrigée dans l'exe ne prouve rien — PyInstaller compresse les
`.pyc` dans son archive, les littéraux n'y sont pas en clair. La preuve tient à la chaîne
source → build : les 227 tests passent sur le source, et PyInstaller a lu ce source-là.

**Reste.** Rien d'ouvert.

---

## 2026-09-03 (suite) — Rachat de crédits : des échéances manquaient au prévisionnel

**Fait.** Le tableau d'amortissement d'un rachat de crédits à la consommation confronté à la
récurrence correspondante : elle s'arrêtait **neuf mois trop tôt**, autant d'échéances
absentes du prévisionnel. Corrigé, et la dernière échéance — celle qui solde le prêt, d'un
montant légèrement différent — modélisée à part comme pour les prêts immobiliers.
L'assurance externalisée de ce rachat n'avait **aucune date de fin** : bornée à la dernière
échéance du prêt, une assurance emprunteur ne survivant pas à son crédit.

**Pourquoi.** Le prélèvement a changé de jour en cours de route : fin de mois d'abord, puis
le 10, avec un mois qui n'a rien vu passer — l'échéance avait glissé au mois suivant. Le
tableau, antérieur de huit mois, raisonne encore en fin de mois. Tout le calendrier a donc
été décalé d'un cran. Contrôle : le prévisionnel génère désormais **exactement** le nombre
d'échéances restantes du tableau, et leur total tombe au centime.

**Reste.** Deux points à confirmer sur pièce, le tableau utilisé datant de huit mois : le
**glissement d'un mois** est déduit des relevés, pas d'un document — un tableau réédité
trancherait ; et la date de fin de l'assurance est une hypothèse (fin du prêt), qui tombera
plus tôt si ce contrat porte une limite d'âge.

---

## 2026-09-03 — Prévisionnel : deux prêts immobiliers remis d'aplomb

**Fait.** Lecture des certificats et des tableaux d'amortissement de deux prêts immobiliers
souscrits ensemble, puis mise à jour des récurrences. La mensualité du prêt principal était
juste ; les deux autres non. L'assurance du prêt à taux zéro courait jusqu'à la fin de
celui-ci alors qu'elle s'arrête bien plus tôt, et le **remboursement du PTZ lui-même**
n'était pas déclaré du tout.

**Pourquoi.** Un PTZ est un long différé suivi d'une phase d'amortissement : il ne coûte que
son assurance pendant des années, puis prend le relais du prêt principal qui vient de
s'éteindre. Le prévisionnel modélisait donc une assurance qui ne sera plus prélevée et
ignorait tout le capital à rembourser ensuite. Deux erreurs qui se compensaient à peu près
en montant mensuel, jamais dans le temps. L'assurance s'arrête le même mois sur les deux
prêts : c'est l'âge limite du contrat.

**Trois échéances sortent du rythme** (deux au mois de bascule de l'assurance, une au solde
final). Chaque récurrence a été **découpée en tranches** plutôt que complétée par une ligne
d'ajustement, pour qu'un mois ne porte jamais qu'une seule échéance attendue, du bon
montant : sinon le rapprochement du mois de bascule aurait soldé l'échéance ordinaire et
laissé traîner un complément. Les libellés restent identiques d'une tranche à l'autre, sans
quoi la clé de rapprochement change et la passe 1 (libellé **et** montant) ne joue plus.

Contrôle : aucun mois en double, aucun trou dans les trois familles, et le capital du PTZ
tombe désormais au centime exact.

**Reste.** Rien d'ouvert sur ces prêts.

---

## 2026-09-02 — Audit des notices : l'intégrée est juste, la copie déployée était en retard

**Fait.** Les trois documents d'aide ont été confrontés au code, pas à leur date.
La **notice intégrée** (`comptesbudget/ui/views/notice.py`, bouton 📖 Notice) est
**exacte** : ses 14 outils du menu de gauche sont exactement les 14 `add_btn` de
`main_window.py`, ses 7 onglets les 7 onglets réels, et les nouveautés des trois
dernières versions y figurent — « Plusieurs comptes » (1.24.0) en section 2,
« Archiver » (1.25.0) en section 7, l'import OFX (1.26.0) avec ses deux versions
de format. Le `Lisez-moi.txt` du dépôt était déjà juste depuis le matin. Seule la
copie déployée dans `F:\budget-app\Pecule\` était restée à l'en-tête
« version 1.26.0 » d'avant le gel : elle a été remplacée par la version du dépôt.
La sauvegarde prise au passage a été supprimée dans la foulée, une fois vérifié
que le fichier en place était identique à celui du dépôt : son contenu vit de
toute façon dans l'historique git.

**Pourquoi.** Un audit par mots-clés m'avait d'abord fait conclure à tort que le
multicomptes n'était pas documenté : je cherchais « multicompte », quand la
notice écrit « **Plusieurs comptes** » — le vocabulaire de l'utilisateur, pas
celui du code. Leçon : comparer des **listes** (boutons réels contre boutons
décrits), jamais la présence d'un mot choisi par moi.

**Reste.** Rien d'ouvert. À noter pour les publications futures : la notice
intégrée **ne porte aucun numéro de version**, ce qui la met à l'abri de
vieillir toute seule — c'est un bon choix, à conserver.

## 2026-09-02 — Audit README + manifeste : gel de publication à 1.23.2

**Fait.** Audit du README et du manifeste Scoop (`bucket/pecule.json`). Manifeste
vérifié intègre : son empreinte SHA-256 correspond au bit près à l'archive
`v1.23.2` en ligne, et l'URL d'installation `…/main/…` du README est valide
(branche par défaut = `main`). La ligne d'en-tête du README, qui affichait
« Version applicative : 1.26.0 », devient « Version publiée : **1.23.2**. La
**1.26.0** … est en cours de développement et n'est pas encore téléchargeable ».
Commité (`2b2b140`) et poussé sur `main` — le push a aussi emporté le commit
local « Journal » `96038bc` qui n'était pas encore en ligne. Puis, dans la
foulée, `Lisez-moi.txt` (en-tête ramené à 1.23.2 + note « 1.26.0 en
developpement ») et deux encadrés ⏳ (FR / EN) en tête des fonctionnalités du
README — commit `9162664`.

**Pourquoi.** Le code est monté à 1.26.0 (multicomptes 1.24, archivage 1.25, OFX
1.26) sans être publié : le README promettait donc une version que personne ne
peut télécharger. Décision : **geler la publication à la 1.23.2 tant que la PR
winget-pkgs #416272 n'est pas soldée**, pour ne pas déplacer la cible pendant la
revue Microsoft — même logique que les manifestes Winget laissés en 1.23.0.

**Reste.** À la publication de la 1.26.0 (PR acceptée) : retirer les deux
encadrés ⏳ du README et remonter d'un bloc README + `Lisez-moi.txt` + manifeste
Scoop + JSON-LD + `APP_VERSION`, puis tagguer la release.

## 2026-09-01 — Import des relevés au format OFX (1.26.0)

**Fait.** Nouveau module `comptesbudget/ofx_import.py` et son jeu de 33 tests.
Pécule lit désormais les relevés OFX (et leur variante `.qfx`), en plus du CSV
et du QIF : même bouton, même glisser-déposer, notice et README à jour.
Au passage, un remboursement de marchand du 06/08/2026 est repassé de « Carte
bancaire » à « Virement reçu », rejoignant les quatorze autres remboursements
d'achat. Et le compte rendu d'import ne montre plus de rectangle noir à la
ligne du débit différé : le pictogramme de carte bancaire ne fait pas partie
de Segoe UI, la police des boîtes de dialogue — mesuré avec
`QFontMetrics.inFont()` sur la police réellement rendue, celle du mode hors
écran ne valant rien pour ça (elle remplace tout par « Sans Serif » et
prétend qu'aucun symbole n'existe). Les trois autres symboles du message,
eux, sont bien dans la police et restent.

**Pourquoi.** La banque d'André propose le relevé en quatre formats — CSV,
PDF, QIF, OFX — et il a téléchargé celui d'août en OFX. Le CSV reste
disponible, mais autant lire les trois formats de données sur quatre.

Trois décisions méritent d'être retenues :

- **L'OFX est traduit en lignes de relevé, puis confié à l'import CSV**, comme
  le fait déjà le QIF. Une seule mécanique d'import à maintenir : dédoublonnage,
  règles, pointage automatique et rattachement des échéances prévues sont
  hérités tels quels.
- **Le type d'opération est déduit du libellé**, l'OFX ne le transportant pas :
  le relevé de compte de la BPCE n'écrit que DEBIT ou CREDIT, alors que le
  mémo annonce « PRLV », « VIR SEPA », « ECH PRET ». Les motifs sont cherchés
  comme des **mots entiers** — sans cela, « ASSURANCE RETRAITE » faisait
  partir une pension de retraite en retrait d'espèces. Et sur un relevé de
  compte, une somme **reçue** n'est jamais un paiement par carte : c'est ce
  qui range un remboursement de marchand au crédit en remboursement, comme
  André le fait.
- **La date de débit d'un achat carte vient de la FIN DU RELEVÉ**, pas de la
  date de l'achat. Un achat du 31/07 que la banque ne comptabilise qu'en août
  est prélevé le 4 septembre avec les autres, et non le 4 août.

**Vérifié.** Sur une **copie** de la base : les deux vrais relevés d'août
n'ajoutent rien (57 doublons reconnus, 1 récapitulatif de débit différé
écarté, solde inchangé). Puis, août effacé de la copie et reconstruit à partir
des seuls relevés : 57 opérations restituées, solde **identique au centime**,
les 25 achats carte tous datés du 04/09. Les deux seules
différences de type avec la saisie d'André étaient des corrections. L'import a
enfin été rejoué **par la fenêtre principale** elle-même, hors écran, pour
contrôler le branchement du bouton et du glisser-déposer. 225 tests au vert.

**Reste.** Rien n'est publié : GitHub, Scoop et le site restent en 1.23.2, et
c'est voulu. L'exécutable de `F:\budget-app\Pecule` a été reconstruit en
1.26.0 pour qu'André s'en serve tout de suite (l'ancien est conservé sous
`Pecule.exe.avant-1.26.0`) — il devance donc la version publiée, comme
déjà en août. Le commentaire de `qif_import.py` qui affirme que Pécule « suit
un seul compte par base de données » date d'avant le multicomptes : à corriger
un jour.

---

## 2026-09-01 — L'abonnement Claude AI en récurrence mensuelle

**Fait.** Ajout de l'opération récurrente « Anthropique (Claude AI) » sur le
Compte courant, le 1er de chaque mois, catégorie Abonnements,
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

**Puis.** André a signalé que l'échéance de septembre n'était pas encore
en banque et devait donc apparaître non pointée. Il avait raison, et le
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
« Budget 2026.xlsx » par Excel COM : l'abonnement porté à l'encours CB de
septembre, et un achat non pointé reporté de l'encours d'août vers celui de
septembre — la banque ne l'ayant pas rattaché au lot du 4/09, il partira au
suivant. Le prélèvement du 4 septembre diminue d'autant. Contrôle après coup
en comparant le XML du fichier à celui de sa
sauvegarde : graphiques, graphiques miniatures, tableaux et validations
intacts ; une seule mise en forme conditionnelle a bougé, étendue d'une ligne
pour suivre le tableau.

Restait un désaccord entre les deux outils : Pécule datait ce débit
au 04/09, le classeur au 04/10. Sa date de valeur a été
décalée d'un lot (`date_debit_differe` appliqué à la date de valeur, pas à la
date d'achat). Les deux disent maintenant la même chose — lot du 4 septembre
sur 26 opérations, une seule reportée au 4 octobre. Le prévisionnel
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

- Le correctif est **commité et poussé** sur `main`. Rien n'est **publié**
  pour autant : ni release, ni tag, et `APP_VERSION` reste à 1.25.3 — la page
  de présentation ne bougera qu'à la prochaine version.
- ~~Aucune règle de catégorisation pour « Anthropique »~~ — **ajoutée** :
  motif `ANTHROPIQUE`, sens `debit`, vers Abonnements / Abonnements, sans
  montant figé (le tarif d'un abonnement bouge). Simulée sur toute la base
  avant insertion : elle reconnaît les trois opérations existantes, n'en
  reclasse aucune et n'entre en conflit avec aucune des 73 autres règles.
  Vérifiée ensuite par le vrai moteur `apply_rules_to_tx` sur cinq libellés,
  dont un suffixe bancaire et un tarif différent, tous classés — et un
  remboursement (crédit), qui reste bien non classé. Cette règle vit dans la
  base d'André, pas dans le dépôt : elle n'est pas concernée par le commit.
- ~~Les appels dupliqués du critère « carte »~~ — **faits**. Ils étaient
  trois, non deux : `is_cb` et `est_carte`, deux noms pour la même chose dans
  le même fichier (`bilan.py`), plus une expression en clair dans
  `previsionnel.py`. Les trois définitions locales tombent, tout passe par
  `est_paiement_carte()` : le critère n'est plus écrit qu'à un seul endroit du
  projet, et sous un seul nom. Deux lignes devenues trop longues ont été
  repliées — l'une atteignait 110 caractères, la plus longue du fichier.

  Contrôle du remaniement : `BilanView` construit hors écran sur une copie des
  vraies données, indicateurs et bandeaux relevés, puis le même relevé sur le
  code d'avant (`git stash`). **Aucune différence** — mêmes six indicateurs,
  mêmes bandeaux. 192 tests, `ruff --select F` propre. L'exécutable n'a pas
  été reconstruit : à comportement identique, il n'y avait rien à y porter.

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
