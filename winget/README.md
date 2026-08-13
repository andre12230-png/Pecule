# Manifestes Winget

Paquet Winget pour Pecule. **La demande d'intégration à
[`microsoft/winget-pkgs`](https://github.com/microsoft/winget-pkgs) est ouverte :
[#416272](https://github.com/microsoft/winget-pkgs/pull/416272)**, déposée le
12 août 2026 pour la version 1.23.0.

Tant qu'elle n'est pas fusionnée, `winget install` ne connaît pas encore le
paquet. Pour installer en ligne de commande dès aujourd'hui, utilisez **Scoop** —
voir le README à la racine du dépôt.

## L'obstacle qui a longtemps bloqué la soumission

Un test d'installation réel avait montré qu'une **mise à jour Winget effaçait
`comptes.db`** : l'application rangeait sa base à côté de son exécutable, or
Winget supprime puis recrée son dossier d'installation à chaque montée de
version. Pour un logiciel de comptes, c'était disqualifiant — et Winget n'offre
aucun équivalent au `persist` du manifeste Scoop (`bucket/pecule.json`).

**La cause a disparu en 1.22.0.** `_data_dir()` (`comptesbudget/constants.py`)
range désormais la base dans `%LOCALAPPDATA%\Pecule`, un dossier auquel Winget
ne touche jamais. Le mode « portable » est préservé : si un `comptes.db` existe
déjà à côté de l'exécutable, c'est lui qui sert.

### Le test de bout en bout, refait le 12 août 2026

C'est un test réel qui avait révélé le problème ; il fallait un test réel pour
le clore. Refait sur la 1.23.0, avec Winget lui-même :

1. base de départ contenant un repère identifiable ;
2. `winget install --manifest` de la 1.22.1 ;
3. `winget upgrade --manifest` vers la 1.23.0 ;
4. `winget list` confirme bien la 1.23.0.

Résultat : `comptes.db` **identique au bit près** (empreinte SHA-256 inchangée),
repère relu intact, et aucun `comptes.db` créé à côté de l'exécutable.

## Où en est la demande d'intégration

État au 13 août 2026 :

| | |
|---|---|
| Contrat de contribution (CLA) | signé |
| Validation automatique | `Azure-Pipeline-Passed` |
| En attente de | une revue humaine, sur l'étiquette `Policy-Test-1.8` (Financial Transactions) |

Cette étiquette est posée automatiquement. Pécule est un outil de tenue de
comptes **hors ligne** : aucun achat intégré, aucun abonnement, aucun traitement
de paiement, aucune connexion à une banque ou à un service en ligne —
l'application n'effectue aucune requête réseau. Une précision en ce sens a été
ajoutée à la demande ; il n'y a plus qu'à attendre la réponse.

## Note pour qui reprendrait ces fichiers

Ne retirez pas `ArchiveBinariesDependOnPath: true` de
`andre12230-png.Pecule.installer.yaml`. Sans ce réglage, Winget crée
un raccourci vers l'exécutable dans un dossier séparé, et l'application s'arrête
au démarrage sur « Failed to load Python DLL » : elle cherche son dossier
`_internal` à côté du raccourci, où il ne se trouve pas.

Pour tester un manifeste local, il faut d'abord l'autoriser en administrateur
(`winget settings --enable LocalManifestFiles`), puis penser à remettre
`--disable` ensuite. La désinstallation ne répond ni à `--id` ni à `--exact` :
la commande qui fonctionne est
`winget uninstall --product-code andre12230-png.Pecule__DefaultSource`.
