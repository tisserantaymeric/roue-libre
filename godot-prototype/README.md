# Roue Libre 3D — prototype Godot (palier « coureur GLTF »)

Second chantier du projet Roue Libre : une application de cyclisme
d'intérieur construite sur **Godot 4**, moteur 3D open source (licence MIT),
en parallèle de l'application PyQt existante à la racine du dépôt
(les deux mondes sont indépendants et peuvent cohabiter).

Ce prototype couvre le **jalon 1** : un coureur stylisé sur son vélo qui
pédale au rythme d'une puissance de démonstration, roulant sur une boucle
de route 3D, avec HUD (puissance, vitesse, cadence, distance) et caméra de
suivi. Compatible **Windows et Linux** (rendu `gl_compatibility`, peu
exigeant pour le GPU).

## Lancer le prototype (2 minutes)

1. Installez **Godot 4.4 ou plus récent** (version standard, pas .NET) :
   - Windows : https://godotengine.org/download/windows/ — téléchargez le
     ZIP, décompressez, lancez `Godot_v4.x.x-stable_win64.exe`.
   - Linux : https://godotengine.org/download/linux/ — téléchargez le ZIP,
     décompressez, puis :

     ```sh
     chmod +x Godot_v4.x.x-stable_linux.x86_64
     ./Godot_v4.x.x-stable_linux.x86_64
     ```

2. Dans le gestionnaire de projets Godot, boutons **Importer**, puis
   sélectionnez `godot-prototype/godot/project.godot`.
3. Ouvrez le projet, puis appuyez sur **F5** (ou ▶ en haut à droite).

Commandes dans le jeu :

| Touche | Action |
|---|---|
| `↑` / `↓` | augmenter / diminuer la puissance (0–450 W) |
| `F` | basculer caméra poursuite / caméra drone |
| `Échap` | quitter |

L'asset 3D (`godot/assets/rider.glb`) est déjà généré et versionné : aucun
passage par Blender n'est nécessaire pour essayer.

## Regénérer l'asset 3D (optionnel)

Le coureur est construit **paramétriquement** par le script Blender
`blender/build_rider.py` (dimensions, couleurs et géométrie dans le dict
`PARAMS` en tête de fichier). Pour regénérer :

```sh
sh tools/build_rider.sh        # Linux / macOS
tools\build_rider.bat          # Windows (Blender doit être dans le PATH)
```

Le fichier `godot/assets/rider.glb` est réécrit. Blender 4.x et 5.x sont
supportés. Aucune connaissance de Blender n'est nécessaire ; pour modifier
le rendu (couleurs du maillot, du vélo, géométrie du cadre…), éditez les
valeurs de `PARAMS` et relancez le script.

## Architecture

```
godot-prototype/
  blender/build_rider.py      construction paramétrique coureur + vélo,
                              export glTF 2.0 (pivots nommés, animations
                              calculées côté Godot)
  tools/build_rider.sh|bat    commande unique de régénération
  godot/
    project.godot             projet Godot 4.4 (rendu gl_compatibility)
    scenes/main.tscn          scène racine (tout est construit en code)
    scripts/main.gd           monde (route courbe, terrain, arbres),
                              boucle de jeu, caméra, HUD, mode démo
    scripts/rider_rig.gd      port GDScript de rouelib/rider.py :
                              pédalage articulé (cuisse + tibia par
                              intersection de cercles), roues, manivelles
    scripts/speed_model.gd    port GDScript de rouelib/physics.py :
                              intégration puissance -> vitesse
    tests/kinematics_test.gd  test de parité avec les valeurs générées
                              depuis le code Python original
```

La **physique** et la **cinématique** sont les mêmes que celles de
l'application PyQt (`rouelib/physics.py`, `rouelib/rider.py`) : les deux
mondes partagent le même modèle. Le test de parité le garantit :

```sh
godot --headless --path godot -s tests/kinematics_test.gd
```

## Étapes suivantes (roadmap du prototype)

1. **Jalon 2** : raccordement aux capteurs réels (home trainer FTMS +
   capteurs BLE) via un module natif (GDExtension Rust/C++), avec mode
   démo conservé.
2. **Jalon 3** : pente réelle (relief le long de la courbe) et résistance
   automatique du home trainer.
3. **Jalon 4** : coureur entraîné par squelette GLTF (animations mixées),
   multiples avatars, multijoueur.

## Artefacts ignorés

Le dossier `godot/.godot/` (cache d'import de Godot) est régénéré
automatiquement à la première ouverture du projet.
