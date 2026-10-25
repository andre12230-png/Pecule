# Pécule 1.41.28

## Nouveautés

- **Mode sombre** : Paramètres › Apparence, Clair ou Sombre. Au tout premier lancement, Pécule vous demande lequel vous préférez.
- **🖨 Imprimer…** remplace « Rapport mensuel » dans le menu de gauche : rapport du mois, opérations affichées (période et filtres de l’écran, non pointées comprises) et Bilan avec ses graphiques, avec aperçu et enregistrement en PDF. L’impression reste toujours en clair.
- **Sauter une échéance « cette fois-ci »** dans le Prévisionnel (bouton du Prévisionnel, ou question à la suppression de la ligne prévue) : elle n’est plus attendue ni comptée dans les sorties à venir. Le bandeau du mois nomme aussi les échéances en retard.
- Les relevés CSV de **LCL sans ligne de titres** s’importent ; les deux lignes de solde du fichier sont écartées.
- La saisie conserve les **majuscules et minuscules** des catégories : taper « Alimentation » ne redonne plus une ancienne « ALIMENTATION ».
- Le Bilan rappelle de faire une **sauvegarde externe** lorsque la dernière copie date de plus de 30 jours.
- Bilan, « Plus grosses dépenses » : un même libellé sur une seule ligne, avec son total.
- Le numéro de version figure en pied du menu de gauche, et chaque onglet dit au survol ce qu’il contient.

## Corrections

- **« 🔄 Appliquer aux opérations existantes »** (Règles auto) ne range plus que les opérations « Non classé » : une catégorie déjà choisie, par exemple corrigée à la main, n’est plus jamais remplacée.
- Le Bilan, ses graphiques et le rapport comptent les revenus et les dépenses **remboursements déduits**, comme le Budget ; l’alerte de découvert compte ce qui doit encore passer aujourd’hui.
- Aucun export (CSV, JSON, PDF) ne peut plus écraser le fichier de comptes. La fusion d’un export JSON vérifie le fichier d’abord, refuse un montant ou une date illisible, puis se fait en tout ou rien.
- Reprendre un ancien fichier de données passe par une copie vérifiée : une copie interrompue ou abîmée laisse la base intacte, et le fichier source n’est jamais modifié.
- Réimporter un relevé dont une ligne est archivée ne bloque plus tout le relevé ; une année sur deux chiffres dans un QIF est lue selon la convention du format.
- Une base abîmée est annoncée en clair au démarrage ; les messages d’import donnent la cause d’un refus.
- Contrastes revus pour les thèmes clair et sombre ; le nom complet des mois et l’astérisque du mois en cours restent visibles dans « Évolution sur 12 mois ».
