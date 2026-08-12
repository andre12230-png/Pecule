# Manifestes Winget

Paquet Winget pour Pecule. **Il n'est pas encore soumis à
[`microsoft/winget-pkgs`](https://github.com/microsoft/winget-pkgs).**

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

Vérifié le 12 août 2026 sur la 1.23.0, en reproduisant le mécanisme exact de la
mise à jour : dossier du paquet entièrement supprimé puis réinstallé, base
retrouvée **au même octet près** (empreinte SHA-256 identique). Aucun
`comptes.db` n'est créé à côté de l'exécutable.

Reste à refaire le cycle avec Winget lui-même (`install` puis `upgrade` depuis
un manifeste local) avant d'ouvrir la demande d'intégration : c'est un test de
bout en bout qui avait révélé le problème, c'est un test de bout en bout qui
doit clore le sujet.

Pour installer en ligne de commande dès aujourd'hui, utilisez **Scoop** — voir
le README à la racine du dépôt.

## Note pour qui reprendrait ces fichiers

Ne retirez pas `ArchiveBinariesDependOnPath: true` de
`andre12230-png.Pecule.installer.yaml`. Sans ce réglage, Winget crée
un raccourci vers l'exécutable dans un dossier séparé, et l'application s'arrête
au démarrage sur « Failed to load Python DLL » : elle cherche son dossier
`_internal` à côté du raccourci, où il ne se trouve pas.

Pour tester un manifeste local, il faut d'abord l'autoriser en administrateur
(`winget settings --enable LocalManifestFiles`), puis penser à remettre
`--disable` ensuite.
