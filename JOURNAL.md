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
