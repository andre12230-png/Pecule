"""Cohérence des métadonnées publiques de distribution de la version courante."""

import json
from pathlib import Path
import re


def test_manifestes_winget_correspondent_a_scoop():
    """Scoop et Winget doivent proposer la même archive et son empreinte."""
    racine = Path(__file__).resolve().parents[1]
    scoop = json.loads((racine / "bucket" / "pecule.json").read_text(encoding="utf-8"))
    version = scoop["version"]
    archive = scoop["architecture"]["64bit"]
    dossier = racine / "winget" / "manifests" / "a" / "andre12230-png" / "Pecule" / version
    manifestes = sorted(dossier.glob("*.yaml"))
    assert len(manifestes) == 4, "Les quatre manifestes Winget sont attendus."

    def champ(texte, nom):
        # Ces champs sont des scalaires YAML simples, sans bloc ni liste.
        valeurs = re.findall(rf"^\s*{re.escape(nom)}:\s*([^\r\n]+?)\s*$", texte, re.MULTILINE)
        assert len(valeurs) == 1, f"Champ {nom} absent ou répété."
        return valeurs[0].strip("\"'")

    types = []
    for manifeste in manifestes:
        texte = manifeste.read_text(encoding="utf-8")
        assert champ(texte, "PackageVersion") == version
        type_manifeste = champ(texte, "ManifestType")
        types.append(type_manifeste)
        if type_manifeste == "installer":
            assert champ(texte, "InstallerUrl") == archive["url"]
            assert champ(texte, "InstallerSha256").lower() == archive["hash"].lower()
    assert sorted(types) == ["defaultLocale", "installer", "locale", "version"]
