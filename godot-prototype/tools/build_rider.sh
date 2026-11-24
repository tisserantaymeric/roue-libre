#!/bin/sh
# Regeneration de l'asset 3D du coureur (rider.glb) pour le prototype Godot.
# Requete : Blender 4.x ou 5.x installe (commande `blender`).
# Usage : sh tools/build_rider.sh
set -e
here="$(cd "$(dirname "$0")" && pwd)"
blender --background --python "$here/../blender/build_rider.py"
