# Manifestes Winget

Paquet Winget pour Comptes et Budget. **Il n'est pas encore soumis à
[`microsoft/winget-pkgs`](https://github.com/microsoft/winget-pkgs), et ne doit
pas l'être en l'état.**

Les manifestes sont complets et validés (`winget validate`), mais un test
d'installation réel a montré qu'une **mise à jour Winget efface `comptes.db`** :
l'application range sa base à côté de son exécutable, or Winget supprime puis
recrée son dossier d'installation à chaque montée de version. Pour un logiciel
de comptes, c'est disqualifiant. Winget n'offre pas d'équivalent au `persist`
du manifeste Scoop (`bucket/comptes-budget.json`), qui, lui, préserve les
données.

La soumission attend donc que l'emplacement de la base change.

En attendant, pour installer proprement en ligne de commande, utilisez
**Scoop** — voir le README à la racine du dépôt.

## Note pour qui reprendrait ces fichiers

Ne retirez pas `ArchiveBinariesDependOnPath: true` de
`andre12230-png.ComptesEtBudget.installer.yaml`. Sans ce réglage, Winget crée
un raccourci vers l'exécutable dans un dossier séparé, et l'application s'arrête
au démarrage sur « Failed to load Python DLL » : elle cherche son dossier
`_internal` à côté du raccourci, où il ne se trouve pas.

Pour tester un manifeste local, il faut d'abord l'autoriser en administrateur
(`winget settings --enable LocalManifestFiles`), puis penser à remettre
`--disable` ensuite.
