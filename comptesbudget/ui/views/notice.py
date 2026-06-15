"""Vue Notice (mode d'emploi + glossaire)."""


from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget,
    QTextBrowser,
)


NOTICE_HTML = """
<style>
  body { font-family: 'Segoe UI', sans-serif; font-size: 11pt; color: #222; }
  h1 { color: #1F3A6B; border-bottom: 2px solid #1F3A6B; padding-bottom: 4px; }
  h2 { color: #1F3A6B; margin-top: 22px; }
  h3 { color: #2E5C9E; margin-top: 16px; }
  .tip { background: #FFFBE6; border-left: 4px solid #E8C77B;
         padding: 8px 12px; margin: 8px 0; }
  .warn { background: #FDECEA; border-left: 4px solid #E74C3C;
          padding: 8px 12px; margin: 8px 0; }
  code { background: #F4F4F4; padding: 1px 5px; border-radius: 3px;
         font-family: 'Consolas', monospace; }
  ul li { margin-bottom: 4px; }
  table { border-collapse: collapse; margin: 8px 0; }
  th, td { border: 1px solid #CCC; padding: 4px 8px; }
  th { background: #E8EEF7; }
  kbd { background: #F4F4F4; border: 1px solid #BBB; border-radius: 3px;
        padding: 1px 6px; font-family: 'Consolas', monospace; font-size: 10pt; }
</style>

<h1>📖 Notice d'utilisation</h1>

<p>Bienvenue dans <b>Comptes et Budget</b>, votre outil de gestion bancaire personnelle.
Cette notice vous guide à travers les principales fonctionnalités.</p>

<h2>1. Premier démarrage</h2>
<ol>
  <li><b>Configurer le solde de départ</b> : cliquez sur <code>⚙️ Paramètres</code> dans le ruban
      en haut. Indiquez la date à laquelle vous commencez votre suivi (ex. 01/01/2025) et le solde
      que vous aviez en banque à cette date. Cette valeur sert de base pour calculer votre solde
      réel à toute date ultérieure.</li>
  <li><b>Importer vos relevés bancaires</b> en CSV : trois moyens possibles
      <ul>
        <li>Bouton <code>📥 Importer CSV</code> dans le ruban</li>
        <li><b>Glisser-déposer</b> un ou plusieurs fichiers CSV directement sur la fenêtre</li>
        <li>Saisie manuelle via <code>➕ Nouvelle opération</code></li>
      </ul>
      L'app gère les CSV des principales banques françaises (BPCE, Crédit Mutuel, Crédit Agricole)
      au format Windows-1252, séparateur point-virgule, dates JJ/MM/AAAA.
  </li>
</ol>

<h2>2. Les onglets</h2>

<h3>🏠 Bilan (tableau de bord)</h3>
<p>Vue d'ensemble avec 6 indicateurs clés, l'évolution mensuelle revenus/dépenses,
la répartition des dépenses par catégorie, et les listes top dépenses / sources de revenus /
plus grosses dépenses individuelles.</p>
<p>Le KPI <b>« Solde compte fin de période »</b> donne le solde réel du compte
(solde initial + toutes les opérations jusqu'à la fin de la période choisie).</p>

<h3>📋 Opérations</h3>
<p>Liste complète des transactions avec filtres (recherche, catégorie, type, pointage).
La colonne <b>P</b> permet de pointer chaque opération d'un simple clic
(<code>○</code> non pointée / <code>✔</code> pointée et vérifiée sur le relevé).
Les colonnes <b>Date opér.</b> et <b>Date valeur</b> sont affichées séparément, avec
indication ⏱ orange si elles diffèrent (débit différé).</p>
<ul>
  <li><b>Double-clic</b> sur une ligne → ouvre le formulaire de modification</li>
  <li><b>Touche <kbd>Suppr</kbd></b> → supprime l'opération sélectionnée</li>
  <li><b>Touche <kbd>Inser</kbd></b> → nouvelle opération</li>
</ul>

<h3>🎯 Budget</h3>
<p>Définissez un budget mensuel par catégorie. Les barres de progression
deviennent vertes (< 80 %), oranges (< 100 %) ou rouges (dépassement)
selon votre consommation pour la période sélectionnée.</p>
<p>Double-cliquez sur une catégorie pour modifier son budget mensuel.</p>

<h3>🏷️ Catégories</h3>
<p>Vue par catégorie avec drill-down : à gauche la liste des catégories
(nombre d'opérations et total), à droite les opérations détaillées de la
catégorie sélectionnée. Le bouton « Recatégoriser » permet de déplacer
en masse toutes les opérations d'une catégorie vers une autre.</p>

<h3>🧠 Règles auto</h3>
<p>Les règles automatisent la catégorisation des opérations futures.
Trois façons d'en créer :</p>
<ul>
  <li>Cocher <b>« Mémoriser »</b> dans le formulaire d'une opération</li>
  <li>Bouton <b>➕ Nouvelle règle</b> dans l'onglet</li>
  <li>Bouton <b>🔧 Harmoniser</b> du ruban (suggestions automatiques)</li>
</ul>
<p>Pour supprimer une règle : sélectionnez-la et utilisez le bouton 🗑,
la touche <kbd>Suppr</kbd> ou le clic droit. Pour la modifier : double-clic
ou bouton ✏️.</p>

<h3>🔮 Prévisionnel</h3>
<p>Déclarez vos opérations récurrentes (loyer, abonnements, salaire…) en
précisant la fréquence (hebdo, mensuelle, trimestrielle, annuelle) et la date
de début. L'app calcule automatiquement les <b>12 prochains mois</b> de
prévisions avec totaux recettes / dépenses / net.</p>

<h2>3. Période et mode date</h2>
<p>La barre <b>Période</b> en haut de l'app filtre toutes les vues (sauf Règles).
Vous pouvez choisir « Toutes périodes », une année entière, ou un mois précis.</p>
<p>Le sélecteur <b>Date</b> à côté contrôle la chronologie :</p>
<table>
  <tr><th>Mode</th><th>Quand l'utiliser</th></tr>
  <tr><td><b>Date d'opération</b></td>
      <td>Vision budget : l'achat compte le jour où il a eu lieu</td></tr>
  <tr><td><b>Date de valeur</b></td>
      <td>Solde réel : l'achat compte le jour où la banque débite</td></tr>
</table>
<p>Important pour les <b>cartes à débit différé</b> : un achat fait fin mai
peut n'être débité qu'en juin. Le mode « Date valeur » est nécessaire pour
retrouver à l'euro près le solde de votre relevé bancaire.</p>

<h2>4. Pointage et rapprochement</h2>
<div class="tip">💡 Le pointage est essentiel pour vérifier que vos opérations
correspondent bien à votre relevé bancaire (rapprochement bancaire).</div>
<p>Quand vous recevez votre relevé, ouvrez l'onglet Opérations et cliquez sur
la colonne <b>P</b> de chaque ligne présente sur le relevé. Le KPI
<b>« Solde pointé »</b> du Bilan vous indique alors le total des opérations
vérifiées. Si tout est pointé, ce solde doit correspondre exactement à votre
solde bancaire.</p>

<h2>5. Outils du ruban</h2>
<table>
  <tr><th>Bouton</th><th>Fonction</th></tr>
  <tr><td>➕ Nouvelle opération</td><td>Saisie manuelle d'une opération</td></tr>
  <tr><td>📥 Importer CSV</td><td>Import d'un relevé bancaire (ou drag&drop)</td></tr>
  <tr><td>🧹 Nettoyer catégories</td><td>Normalise les noms (accents, variantes)</td></tr>
  <tr><td>🔧 Harmoniser</td><td>Suggère des catégorisations d'après les libellés</td></tr>
  <tr><td>🔍 Doublons</td><td>Détecte et supprime les opérations en doublon</td></tr>
  <tr><td>💾 Exporter (JSON)</td><td>Sauvegarde complète (transactions, règles, budgets)</td></tr>
  <tr><td>⚙️ Paramètres</td><td>Solde de départ et date initiale</td></tr>
</table>

<h2>6. Sauvegarde des données</h2>
<p>Toutes vos données sont stockées localement dans le fichier
<code>comptes.db</code> à côté de l'application (ou de l'exécutable).
Pour faire une sauvegarde : copiez ce fichier ailleurs (clé USB, OneDrive…).
Pour restaurer : remettez-le à sa place.</p>
<div class="warn">⚠️ Le bouton « 💾 Exporter (JSON) » crée un export lisible mais
ne remplace pas la sauvegarde du fichier <code>comptes.db</code>.</div>
"""

GLOSSAIRE_HTML = """
<style>
  body { font-family: 'Segoe UI', sans-serif; font-size: 11pt; color: #222; }
  h1 { color: #1F3A6B; border-bottom: 2px solid #1F3A6B; padding-bottom: 4px; }
  dt { font-weight: bold; color: #1F3A6B; margin-top: 12px; font-size: 12pt; }
  dd { margin-left: 16px; margin-bottom: 6px; color: #333; }
  code { background: #F4F4F4; padding: 1px 5px; border-radius: 3px;
         font-family: 'Consolas', monospace; }
</style>

<h1>📚 Glossaire</h1>

<dl>

<dt>Catégorie</dt>
<dd>Classement principal d'une opération (Alimentation, Transports, Logement…)
utilisé pour les statistiques et le budget. Chaque opération a exactement
une catégorie.</dd>

<dt>Date d'opération</dt>
<dd>Date à laquelle vous avez fait l'achat ou l'opération. C'est la date
« budget » : utile pour savoir <i>quand</i> vous avez dépensé.</dd>

<dt>Date de valeur</dt>
<dd>Date à laquelle la banque débite (ou crédite) effectivement le compte.
Pour une carte à débit immédiat, c'est la même que la date d'opération.
Pour une carte à débit différé, elle peut être plusieurs semaines plus tard.</dd>

<dt>Débit différé</dt>
<dd>Mode de fonctionnement de certaines cartes bancaires où tous les achats
du mois sont regroupés et débités en une seule fois (souvent le 5 ou le 6 du
mois suivant). Reconnu par l'icône ⏱ orange dans la colonne Date valeur.</dd>

<dt>Doublon</dt>
<dd>Opération qui apparaît deux fois dans la base (même date, même montant,
même libellé). L'outil 🔍 Doublons les détecte et propose de les supprimer.</dd>

<dt>Encours</dt>
<dd>Ensemble des opérations en attente de débit, typiquement les achats à
débit différé pas encore prélevés par la banque.</dd>

<dt>Harmonisation</dt>
<dd>Outil qui propose automatiquement des catégorisations basées sur des motifs
prédéfinis (ex : tout ce qui contient « Carrefour » → Alimentation).
Distinct des règles : c'est une suggestion ponctuelle, pas une règle persistante.</dd>

<dt>Importer</dt>
<dd>Charger un fichier CSV bancaire dans l'application. Les opérations
déjà présentes (mêmes ID) sont ignorées pour éviter les doublons.</dd>

<dt>Libellé</dt>
<dd>Texte descriptif de l'opération tel qu'apparu sur le relevé bancaire
(« CARREFOUR MARKET 5012 », « VIR SEPA SALAIRE », etc.).</dd>

<dt>Motif</dt>
<dd>Texte qu'une règle cherche dans le libellé pour déterminer si elle
s'applique. Sensible à la longueur : <code>CARREFOUR</code> matche toutes
les opérations Carrefour ; <code>CARREFOUR MARKET 5012</code> ne matche
que ce magasin précis.</dd>

<dt>Mouvement net</dt>
<dd>Somme algébrique des opérations sur la période : revenus moins dépenses.
S'il est positif vous avez épargné, s'il est négatif vous avez puisé dans
le solde.</dd>

<dt>Opération récurrente</dt>
<dd>Opération qui se répète automatiquement à intervalle fixe (loyer mensuel,
abonnement, salaire…). Définie dans l'onglet Prévisionnel.</dd>

<dt>Pointage</dt>
<dd>Action de cocher une opération comme « vérifiée sur le relevé bancaire ».
Symbolisée par ✔ dans la colonne P. Une opération pointée est verrouillée
mentalement : elle est confirmée par la banque.</dd>

<dt>Période</dt>
<dd>Filtre temporel appliqué aux vues : « Toutes », une année (« 2025 »),
ou un mois précis (« Mai 2026 »).</dd>

<dt>Prévisionnel</dt>
<dd>Projection des opérations à venir basée sur les opérations récurrentes
déclarées. Permet d'anticiper le solde futur.</dd>

<dt>Rapprochement bancaire</dt>
<dd>Procédure consistant à comparer ligne à ligne ses opérations enregistrées
avec celles du relevé bancaire. Réalisée via le <i>pointage</i>.</dd>

<dt>Règle automatique</dt>
<dd>Affectation automatique d'une catégorie et sous-catégorie aux opérations
dont le libellé correspond à un motif donné. Appliquée à chaque import CSV
et accessible depuis l'onglet Règles auto.</dd>

<dt>Solde compte</dt>
<dd>Montant total disponible sur le compte. Calculé comme :
<code>solde initial + somme des opérations depuis la date initiale</code>.
Affiché dans le Bilan en KPI principal.</dd>

<dt>Solde de départ (solde initial)</dt>
<dd>Valeur de référence du compte à une date donnée, saisie dans Paramètres.
Sert de base pour tous les calculs de solde.</dd>

<dt>Solde pointé</dt>
<dd>Somme des opérations marquées comme pointées sur la période. Indicateur
de cohérence avec le relevé bancaire.</dd>

<dt>Sous-catégorie</dt>
<dd>Précision facultative à l'intérieur d'une catégorie
(Alimentation > Restauration rapide, Transports > Carburant…).</dd>

<dt>Taux d'épargne</dt>
<dd>Part des revenus non dépensée : <code>mouvement net / revenus × 100</code>.
Indicateur de santé financière sur la période.</dd>

<dt>Transaction exclue</dt>
<dd>Catégorie spéciale pour les opérations qui ne doivent pas compter dans
les statistiques (ex : virements internes entre vos propres comptes,
cumuls de débit différé).</dd>

</dl>
"""


class NoticeView(QWidget):
    """Onglet contenant la notice et le glossaire."""

    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)

        sub_tabs = QTabWidget()
        sub_tabs.setDocumentMode(True)

        # Notice
        notice = QTextBrowser()
        notice.setOpenExternalLinks(True)
        notice.setStyleSheet("QTextBrowser { background:#FFFFFF; padding:14px }")
        notice.setHtml(NOTICE_HTML)
        sub_tabs.addTab(notice, "📖 Notice d'utilisation")

        # Glossaire
        gloss = QTextBrowser()
        gloss.setOpenExternalLinks(True)
        gloss.setStyleSheet("QTextBrowser { background:#FFFFFF; padding:14px }")
        gloss.setHtml(GLOSSAIRE_HTML)
        sub_tabs.addTab(gloss, "📚 Glossaire")

        v.addWidget(sub_tabs)

    def refresh(self):
        # Pas de données dynamiques, mais expose la méthode pour cohérence
        pass
