"""Constantes et données de configuration (catégories, couleurs, règles)."""
import os
import re
import sys

def _app_dir() -> str:
    """Dossier de l'application : à côté du .exe en mode gelé, sinon le dossier
    racine du projet — celui du lanceur comptes_budget.py, où se trouvent
    comptes.db, Budget.ico et le dossier des sauvegardes."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # Ce module est dans comptesbudget/ ; on remonte d'un cran vers la racine.
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.join(_app_dir(), "comptes.db")

# Fichier d'échange JSON (historique). La synchronisation automatique avec
# l'application HTML a été retirée en 1.9.5 (l'app HTML est archivée dans
# archive/) ; le moteur de fusion plus bas est conservé : il permettrait de
# réimporter/fusionner un tel fichier si besoin.
SYNC_PATH = os.path.join(_app_dir(), "comptes_sync.json")
SYNC_VERSION = 2


# Version applicative — incrémentée à chaque amélioration
# 1.8.0 : onglet Sous-catégories, pré-remplissage du prévisionnel depuis
#         l'historique, harmonisation des libellés, autocomplétion et
#         pré-remplissage intelligent des formulaires, héritage de la
#         catégorie/sous-catégorie à l'import CSV.
# 1.9.0 : synchronisation automatique via fichier partagé (OneDrive) avec
#         fusion par enregistrement (dernière modification gagne), horodatage
#         et pierres tombales pour propager les suppressions.
# 1.9.1 : le solde initial et la date initiale sont aussi synchronisés
#         (fusion par horodatage).
# 1.9.2 : (app HTML) mise en page mobile responsive — version alignée.
# 1.9.4 : sauvegarde quotidienne automatique de la base dans « sauvegardes/ »
#         (au lancement, rotation sur 10 jours).
# 1.9.5 : retrait de l'application HTML et de la synchronisation automatique
#         (app HTML archivée dans archive/ ; moteur de fusion conservé dormant).
# 1.9.6 : alertes budget sur le Bilan — bandeau rouge/orange quand une
#         catégorie dépasse (ou approche à 85 %) son budget du mois en cours.
# 1.9.7 : rapport mensuel imprimable (🖨 dans la barre d'outils) — synthèse,
#         budgets, dépenses par catégorie, top dépenses ; aperçu, PDF, papier.
# 1.9.8 : recherche globale (🔎 / Ctrl+F) dans tout l'historique — libellé,
#         note, catégorie, montant, date ; double-clic pour modifier.
# 1.9.9 : correctif — la touche Entrée ne ferme plus la recherche globale
#         (et ne déclenche plus de bouton par accident dans le rapport).
# 1.10.0 : les règles distinguent débit/crédit (champ « Sens ») — un
#          remboursement ne retombe plus dans la catégorie de dépense ;
#          règles existantes reclassées (Revenus→crédit, autres→débit),
#          « Mémoriser » hérite du sens de l'opération.
# 1.10.1 : solde de départ non pré-rempli (invite au 1er lancement) ;
#          notice intégrée mise à jour (onglet Sous-catégories, recherche
#          globale, rapport mensuel, harmonisation des libellés).
# 1.11.0 : interface — les actions passent dans un menu vertical à gauche
#          (au lieu de la barre d'outils horizontale) ; raccourci Ctrl+F
#          conservé. Aligne la disposition sur les interfaces native et Qt.
# 1.12.0 : import CSV — encodage UTF-8 reconnu, montants illisibles signalés
#          (jamais enregistrés à 0 €), écritures groupées (~70× plus rapide) ;
#          recherche des montants et dates dans l'onglet Opérations, saisie
#          « comme à l'écran » (-45,30 €) acceptée partout ; Doublons avec
#          liste de vérification à cocher avant suppression ; export JSON
#          complet (réglages inclus) + nouveau bouton « Restaurer (JSON) » ;
#          budget annuel au prorata des mois couverts ; validation aussi à
#          la modification d'une opération ; notice et glossaire à jour.
# 1.12.1 : correctif IMPORTANT de l'import CSV — les opérations saisies à la
#          main (sans référence bancaire) étaient réimportées en double
#          depuis le relevé (la détection ne comparait que la référence).
#          Doublon désormais reconnu par référence OU par libellé nettoyé.
#          Les catégories des exports BPCE (« A categoriser… », « Revenus et
#          rentrees d'argent »…) sont ramenées aux catégories de l'app.
# 1.13.0 : pointage automatique à l'import — si le relevé contient une
#          colonne « Pointage » (« x » = passée en banque, format BPCE),
#          les nouvelles opérations arrivent pointées et les opérations
#          déjà enregistrées sont confirmées (jamais dépointées). L'import
#          annonce le nombre d'opérations pointées automatiquement.
# 1.13.1 : l'import reconnaît aussi les doublons des SAISIES MANUELLES dont
#          le libellé diffère de celui de la banque (« Omnishop » saisi à la
#          main vs « CREDIPLUS » sur le relevé) : face à une saisie manuelle,
#          même date + même montant suffisent. Limité aux saisies manuelles
#          pour ne jamais confondre deux opérations importées distinctes.
# 1.13.2 : correctif d'affichage — la tuile « Solde pointé » du Bilan restait
#          verte même quand le solde était négatif. Elle suit désormais le
#          signe du montant (vert si positif, rouge si négatif), comme les
#          tuiles « Solde bancaire », « Mouvement net » et « Taux d'épargne ».
# 1.13.3 : le liseré coloré en haut des tuiles du Bilan suit lui aussi le
#          signe du montant, et plus seulement le chiffre. Concerne les
#          quatre tuiles de solde (Solde bancaire, Mouvement net, Taux
#          d'épargne, Solde pointé) ; Revenus et Dépenses gardent leur
#          couleur fixe puisque leur signe ne change jamais.
# 1.14.0 : carte à débit différé — le KPI « Solde bancaire réel » du Bilan est
#          désormais TOUJOURS calculé en date de valeur, même quand l'affichage
#          est en « date d'opération » : l'encours carte du mois n'entre dans le
#          solde que le 4 du mois suivant, jour du prélèvement de la banque.
#          À la saisie, le type « Carte bancaire » propose automatiquement la
#          date de valeur au 4 du mois suivant l'achat (modifiable : dès que la
#          date est saisie à la main, l'app ne la recalcule plus).
# 1.14.1 : trois correctifs issus de l'audit du 31/07/2026.
#          • Import CSV — une opération du relevé pouvait DISPARAÎTRE sans
#            rien signaler : face à une saisie manuelle, le rapprochement
#            « même date + même montant » écartait la première ligne venue,
#            même sans rapport (une saisie « Café » -4,50 € masquait la
#            boulangerie du même jour au même montant). Ce rapprochement ne
#            s'applique désormais que s'il n'y a aucune ambiguïté ; sinon
#            tout est importé (un doublon visible se corrige, une opération
#            perdue ne se voit pas).
#          • Sélecteur de période — les mois proposés suivent le sélecteur
#            « Date ». En « date de valeur » (le mode par défaut), un achat
#            carte du 28/07 débité le 04/08 n'apparaissait dans AUCUN mois
#            tant qu'août n'existait pas côté date d'opération.
#          • Onglets Budget et Catégories — ils ignoraient le sélecteur
#            « Date » et comptaient toujours en date d'opération : le Bilan
#            pouvait annoncer 0 € de dépenses en juillet pendant que Budget
#            en affichait 100 €. Les quatre vues comptent maintenant les
#            mêmes opérations (l'alerte budget du Bilan comprise).
# 1.15.0 : suite de l'audit du 31/07/2026 — le reste des anomalies relevées.
#          • Encours carte : le bandeau du Bilan reprend désormais les DEUX
#            chiffres de l'espace bancaire (« prochain prélèvement confirmé »
#            = achats pointés, « achats en cours » = pas encore rattachés par
#            la banque, et leur somme). Les trois tuiles précédentes mêlaient
#            mois d'opération et pointage sans correspondre à aucun chiffre
#            vérifiable ; les opérations au-delà du prochain prélèvement sont
#            annoncées à part. Le bandeau affiche aussi le « solde incluant
#            les opérations carte en cours », chiffre mis en avant par la
#            banque : les deux écrans se rapprochent d'un coup d'œil. Une
#            opération en cours peut être un REMBOURSEMENT (crédit) — il vient
#            en déduction de l'encours, d'où « opérations » et non « achats ».
#          • Règles automatiques : comparaison sans accents, comme partout
#            ailleurs (une règle « Café » reconnaît « CAFE »).
#          • « Mémoriser » n'applique plus QUE la règle créée, et demande
#            confirmation en annonçant combien d'opérations changent et
#            lesquelles étaient déjà classées (ce n'est pas annulable).
#            Auparavant toutes les règles étaient rejouées sur toute la base
#            sans prévenir, ce qui pouvait défaire un classement manuel.
#          • « Recatégoriser toutes ces opérations » agit sur la période
#            affichée — ce que l'écran montre — et le rappelle dans la
#            confirmation ; il déplaçait toute la base.
#          • Harmonisation : motifs qui se chevauchaient corrigés —
#            TotalEnergies (facture) ne part plus dans Transports, Boulanger
#            (électroménager) n'est plus de l'Alimentation, « BP » n'attrape
#            plus la Banque Populaire, et « remboursement » ne bascule plus
#            en Revenus (convention : catégorie de la dépense d'origine).
#          • Récurrences : une échéance au 31 ne dérive plus au 28 après
#            février, la fréquence annuelle respecte le jour du mois, et une
#            date de début illisible n'empêche plus l'ouverture.
#          • Libellés : « VIR 123456 » n'est plus réduit à « Vir » — deux
#            virements sans rapport ne peuvent plus être pris l'un pour
#            l'autre, y compris par la détection de doublons.
#          • Rapport mensuel du mois en cours arrêté à aujourd'hui (et non au
#            31), pour annoncer le même solde que le Bilan.
#          • Graphique d'évolution : les mois sans opération apparaissent à
#            zéro au lieu d'être masqués (l'axe du temps était trompeur).
# 1.16.0 : nouveau bandeau « 📅 Ce qui est prévu » sur le Bilan — projection
#          du compte sur 15 jours. Il additionne les opérations déjà
#          enregistrées dont le débit est à venir (l'encours carte) et les
#          échéances du Prévisionnel sans opération correspondante (pas de
#          double compte), et affiche prélèvements attendus, rentrées
#          attendues et SOLDE PRÉVU. Répond à « où en sera mon compte dans
#          quinze jours ? », ce que ni le Bilan ni le Prévisionnel ne
#          disaient : le premier ignorait l'avenir, le second listait les
#          échéances sans les rapprocher du solde.
#          À ne pas confondre avec le « X € d'opérations prévues
#          prochainement » de l'espace bancaire : la banque n'annonce que les
#          prélèvements dont elle a reçu l'avis, ce bandeau les couvre tous —
#          son montant est donc normalement plus élevé.
# 1.16.1 : correctif du bandeau « Ce qui est prévu » — le débit carte annoncé
#          était FAUX. Il additionnait toutes les opérations carte à venir,
#          y compris celles encore « en cours » : un achat de 120 € déjà
#          rattaché au prélèvement et un remboursement de 15 € pas encore
#          traité donnaient 105 € annoncés, alors que la banque prélève bien
#          120 € (le remboursement ira au prélèvement suivant). Seules les
#          opérations POINTÉES (celles que la banque a intégrées au
#          prélèvement) sont désormais comptées ; les autres sont annoncées
#          à part en fin de ligne. Le solde prévu s'en trouve corrigé d'autant.
# 1.16.2 : un REMBOURSEMENT par carte ne suit pas le débit différé — la banque
#          le porte directement au compte courant, il ne vient jamais réduire
#          l'encours de la carte.
#          • À la saisie, le type « Carte bancaire » ne proposait le 4 du mois
#            suivant qu'en regardant le TYPE, sans le sens : un remboursement
#            se retrouvait daté au prochain prélèvement, donc absent du solde
#            pendant des semaines. La date de valeur ne se décale plus que
#            pour les débits, et le rappel « 💳 débit différé » suit le sens.
#          • Bandeau encours : la 3ᵉ tuile devient « Total des achats à
#            débiter » (les crédits n'y entrent plus, ils ne sont pas
#            prélevables). Les opérations en cours restent affichées, achats
#            comme remboursements, pour correspondre à la liste de la banque.
#          • Correctif d'affichage : le rappel du débit différé restait
#            visible après un passage en crédit (isVisible() vaut toujours
#            False tant que la fenêtre n'est pas ouverte → isVisibleTo).
# 1.17.0 : tri des tableaux par clic sur le titre d'une colonne (Opérations,
#          Catégories, Budget, Prévisionnel et recherche globale ; les
#          Sous-catégories l'avaient déjà). Second clic = ordre inverse.
#          Le tri porte sur les VALEURS et non sur le texte affiché : sans
#          cela « 09/01 » passerait après « 10/01 » et « -1 000 € » avant
#          « -90 € ». Chaque cellule range donc sa valeur de tri à part
#          (dates en ISO, montants en nombre, texte sans accents ni casse).
#          Le tri survit aux rechargements — changer de filtre, de période ou
#          pointer une opération ne le remet pas à zéro — et, sur une colonne
#          de date, il suit le sélecteur « Date » de la barre du haut.
#          Cas particulier du Budget : ses barres de progression sont des
#          widgets posés dans les cellules et ne suivraient pas un tri fait
#          par Qt ; les catégories y sont donc triées avant construction des
#          lignes, ce qui garde chaque barre en face de la sienne.
# 1.18.0 : les montants sont écrits sur les graphiques du Bilan.
#          • Évolution mensuelle : le montant figure en blanc dans chaque
#            barre. Deux pièges de QtCharts contournés — la précision compte
#            les chiffres SIGNIFICATIFS (à 0, « 5076 » sortait en « 5e+03 »),
#            et une étiquette posée au-dessus de la barre la plus haute sort
#            de la zone de tracé et disparaît, d'où le placement à
#            l'intérieur. Au-delà de 6 mois affichés les barres sont trop
#            étroites pour rester lisibles : les chiffres sont alors masqués.
#          • Répartition des dépenses : le montant de chaque catégorie passe
#            dans la LÉGENDE (« Alimentation — -320,00 € ») plutôt qu'autour des
#            parts. Le libellé d'une part sert aussi de texte à la légende :
#            y mettre le seul montant faisait disparaître les noms de
#            catégories, et les textes longs se faisaient tronquer. Police de
#            la légende réduite pour que toutes les catégories tiennent.
# 1.19.0 : la ligne récapitulative du débit différé de la carte (« DEBIT
#          DIFFERE N° ...1234 » / « CUMUL DES DEBITS DIFFERES ») n'est plus
#          importée. La banque la met dans le relevé du compte alors que les
#          achats carte y figurent déjà un par un : elle faisait donc doublon.
#          Elle arrivait jusque-là en catégorie « Transaction exclue », donc
#          hors du solde et des dépenses, mais restait visible dans la liste
#          des opérations et gonflait le total affiché en bas de l'onglet.
#          L'import annonce désormais combien de récapitulatifs il a écartés.
# 1.20.0 : deux corrections de saisie.
#          • Les champs de montant acceptent le POINT du pavé numérique
#            autant que la virgule (« 12.50 » = « 12,50 ») — widget partagé
#            MontantSpinBox, utilisé aussi par la boîte « Budget mensuel ».
#          • Changer le TYPE ou le SENS d'une opération déjà enregistrée
#            recalcule sa date de valeur. Un prélèvement saisi par erreur en
#            « Carte bancaire » gardait sinon la date du 4 du mois suivant :
#            l'opération sortait du solde bancaire réel sans rien signaler
#            (cas d'une prime d'assurance, d'où un écart avec la banque).
# 1.21.0 : saisir d'avance ce qui doit être débité (ou encaissé) dans le mois.
#          • Onglet Prévisionnel, bouton « 📅 Générer les échéances du mois » :
#            crée en une fois, pour le mois choisi, les opérations attendues
#            d'après les récurrences. Elles sont enregistrées NON pointées et
#            marquées « prévue » (⏳ dans la liste, filtre dédié) : visibles
#            dans « ce qui est prévu », sans effet sur le solde en banque.
#            L'assistant grise les échéances auxquelles une opération
#            correspond déjà : on peut le relancer sans créer de doublon. Le
#            rapprochement tolère les libellés rallongés par la banque
#            (« SECURIDOM » / « SECURIDOM SAS »), accepte n'importe quel jour du
#            MÊME mois (échéance du 17 payée le 30) mais pas le mois voisin
#            au-delà de 5 jours — sinon le prélèvement du 31 juillet soldait
#            l'échéance du 31 août. Quand deux échéances portent le même nom
#            (« Echeance De Credit » désigne aussi bien la mensualité d'un
#            prêt que sa petite assurance), c'est le montant qui les
#            départage ; à défaut, une SOUS-CATÉGORIE
#            contradictoire suffit (chez le même assureur, « Assurance Auto »
#            et « Assurance Habitation » sont deux contrats). Ce dernier
#            critère n'intervient qu'en dernier recours : la banque réécrit
#            parfois la sous-catégorie d'une opération (« eau » devient
#            « Energie eau, gaz, electricite, fioul ») sans que ce soit une
#            autre opération.
#          • À l'import, une échéance prévue est COMPLÉTÉE par la ligne réelle
#            du relevé (date, montant, libellé d'origine, référence, pointage)
#            au lieu d'être doublonnée — jusqu'à 7 jours d'écart, sur le même
#            montant ou sur un libellé concordant (factures à montant
#            variable). Le libellé et la catégorie choisis sont conservés.
#            Sans cela, une échéance passée un autre jour que prévu faisait
#            deux lignes (incident du 06/08/2026, remboursement Omnishop).
#          • Bilan, nouveau bandeau « 🗓 CE MOIS-CI » : reste à débiter, reste
#            à encaisser et solde prévu au dernier jour du mois. Sa fenêtre
#            part du 1er (une échéance du 5 toujours pas passée reste due),
#            là où le bandeau des 15 jours ne regarde que devant. Ce qui est
#            pointé et passé en est exclu : c'est déjà dans le solde.
#          • Correction du bandeau « CE QUI EST PRÉVU » : il annonçait une
#            seconde fois une échéance déjà encaissée quand la banque avait
#            employé un libellé un peu différent ou payé un autre jour que
#            prévu : des pensions déjà encaissées étaient re-comptées quelques
#            jours plus tard. Les deux bandeaux partagent désormais le
#            rapprochement tolérant de echeances_du_mois.
#          • Nouvelle colonne « prevue » dans transactions : ajoutée
#            automatiquement à l'ouverture des bases antérieures, à 0 — les
#            données existantes ne changent pas.
APP_VERSION = "1.21.0"

CATEGORIES_DEFAUT = [
    "Alimentation", "Transports", "Logement - maison", "Santé",
    "Loisirs", "Shopping", "Abonnements", "Banque et assurances",
    "Impôts et taxes", "Famille", "Cadeaux et dons",
    "Revenus", "Épargne", "Retraits / dépôts", "Virements internes",
    "Transaction exclue", "Non classé",
]

CATEGORY_COLORS = {
    "Alimentation":          "#E67E22",
    "Transports":            "#3498DB",
    "Logement - maison":     "#8B4513",
    "Santé":                 "#E91E63",
    "Loisirs":               "#9B59B6",
    "Shopping":              "#1ABC9C",
    "Abonnements":           "#2980B9",
    "Banque et assurances":  "#34495E",
    "Impôts et taxes":       "#7F0000",
    "Famille":               "#FF69B4",
    "Cadeaux et dons":       "#E74C3C",
    "Revenus":               "#27AE60",
    "Épargne":               "#16A085",
    "Retraits / dépôts":     "#95A5A6",
    "Virements internes":    "#BDC3C7",
    "Transaction exclue":    "#7F8C8D",
    "Non classé":            "#8A877F",
}

# Normalisation : variantes / catégories des banques → forme canonique.
# Les clés sont comparées SANS accents (cf. utils.canonical_cat, qui applique
# deaccent) : inutile d'ajouter ici des variantes accentuées, elles ne
# seraient jamais consultées.
CANONICAL_CATS = {
    "alimentation": "Alimentation",
    "alimentation et restauration": "Alimentation",
    "transports": "Transports",
    "transport": "Transports",
    "transports et deplacements": "Transports",
    "logement": "Logement - maison",
    "logement - maison": "Logement - maison",
    "maison": "Logement - maison",
    "sante": "Santé",
    "loisirs": "Loisirs",
    "loisirs et culture": "Loisirs",
    "shopping": "Shopping",
    "achats": "Shopping",
    "abonnements": "Abonnements",
    "banque": "Banque et assurances",
    "banque et assurances": "Banque et assurances",
    "assurances": "Banque et assurances",
    "impots": "Impôts et taxes",
    "impots et taxes": "Impôts et taxes",
    "famille": "Famille",
    "cadeaux": "Cadeaux et dons",
    "cadeaux et dons": "Cadeaux et dons",
    "revenus": "Revenus",
    "salaire": "Revenus",
    "epargne": "Épargne",
    "retraits": "Retraits / dépôts",
    "retraits / depots": "Retraits / dépôts",
    "virements internes": "Virements internes",
    "transaction exclue": "Transaction exclue",
    "non classe": "Non classé",
    # Catégories des exports BPCE : sans correspondance, elles créaient des
    # catégories parasites (« A categoriser - sortie d'argent »…) à l'import.
    # Ramenées à « Non classé », elles laissent les règles et les profils de
    # libellés faire la catégorisation.
    "a categoriser - sortie d'argent": "Non classé",
    "a categoriser - rentree d'argent": "Non classé",
    "revenus et rentrees d'argent": "Revenus",
    "loisirs et vacances": "Loisirs",
    "shopping et services": "Shopping",
}

TYPES_OPERATION = [
    "", "Carte bancaire", "Virement", "Virement recu", "Prelevement",
    "Pret", "Cheque", "Retrait d'especes", "Depot d'especes",
    "Frais bancaires", "Autre",
]

# Règles d'harmonisation : on lit (libellé + sous-catégorie) sans accents,
# première regex qui matche → catégorie canonique.
HARMONIZE_RULES = [
    # Logement
    # « totalenergies » AVANT la règle Transports : sans cela, la facture
    # d'électricité TotalEnergies partait dans Transports (motif « total »
    # des stations-service).
    (r"\b(loyer|edf|engie|enedis|gdf|veolia|suez|eau|gaz|electric|chauffage|copropriete|syndic|sfr|orange|free|bouygues|telephon|internet|fibre|adsl|mobile|totalenergies|total energies)\b", "Logement - maison"),
    (r"\b(brico|leroy[\s-]?merlin|castorama|ikea|conforama|but|maison|ameublement|mobilier|jardin)\b", "Logement - maison"),
    # Transports
    # « bp » (2 lettres) retiré : il attrapait aussi la Banque Populaire.
    (r"\b(carburant|station|essence|total|shell|esso|avia|intermarche carburant|gazole|sp95|sp98|peage|autoroute|sncf|ratp|tcl|tan|tisseo|stationnement|parking|garage|controle technique|garagiste|entretien vehicule|reparation auto|peugeot|renault|citroen|ford|fiat|vw|volkswagen|assurance auto)\b", "Transports"),
    # Santé
    (r"\b(pharmacie|medecin|docteur|dentist|opticien|hopital|clinique|cpam|mutuelle|harmonie|mgen|laboratoire|kine|kinesi|ostheo|psychologue)\b", "Santé"),
    # Alimentation
    # « boulangerie » et non « boulanger » : Boulanger est l'enseigne
    # d'électroménager (elle reste couverte par la règle Shopping).
    (r"\b(carrefour|leclerc|auchan|intermarche|lidl|aldi|casino|monoprix|super[\s-]?u|hyper[\s-]?u|coop|biocoop|naturalia|grand frais|picard|marche|boulangerie|patisser|boucher|primeur)\b", "Alimentation"),
    (r"\b(mcdo|mc[\s-]?donald|kfc|burger|quick|subway|pizza|restaur|brasserie|bar|cafe|kebab|sushi|chez|brunch)\b", "Alimentation"),
    # Loisirs
    (r"\b(cinema|cine|netflix|spotify|deezer|prime video|disney|amazon prime|canal|playstation|nintendo|xbox|steam|fnac|cultura|micromania|jeu|cinema|gaumont|ugc|pathe|theatre|concert|musee)\b", "Loisirs"),
    # Shopping — « fnac » n'y figure plus : il est déjà pris par Loisirs
    # (culture) juste au-dessus, la première règle qui correspond l'emporte.
    (r"\b(amazon|cdiscount|darty|boulanger|zalando|asos|kiabi|h&m|zara|uniqlo|decathlon|intersport|go sport)\b", "Shopping"),
    # Impôts
    (r"\b(dgfip|tresor public|impot|tva|taxe|cfe|tfh)\b", "Impôts et taxes"),
    # Banque / assurances
    (r"\b(bpce|cic|credit agricole|banque postale|caisse epargne|societe generale|sg|bnp|hsbc|lcl|cotisation|frais|agios|commission|maaf|matmut|maif|axa|gmf|allianz|maif|assurance habitation|assurance accident)\b", "Banque et assurances"),
    # Revenus — « remboursement » volontairement ABSENT : la convention est de
    # classer un remboursement dans la catégorie de la dépense d'origine
    # (Samse → Logement, Cofidis → Banque et assurances…), pas en Revenus, où
    # il gonflerait à tort les revenus et le taux d'épargne. Sans motif, ces
    # opérations restent « Non classé » et c'est vous qui tranchez.
    (r"\b(salaire|paie|paye|caf|pole emploi|chomage|retraite|pension|virement recu)\b", "Revenus"),
    # Épargne
    (r"\b(virement epargne|livret a|ldds|pel|cel|assurance vie|pea|opcvm)\b", "Épargne"),
]
_HARMONIZE_COMPILED = [(re.compile(p, re.IGNORECASE), c) for p, c in HARMONIZE_RULES]


FREQUENCIES = [
    ("weekly", "Hebdomadaire"),
    ("biweekly", "Bi-mensuelle (toutes les 2 semaines)"),
    ("monthly", "Mensuelle"),
    ("quarterly", "Trimestrielle"),
    ("yearly", "Annuelle"),
]
