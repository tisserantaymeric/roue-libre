@echo off
rem Regeneration de l'asset 3D du coureur (rider.glb) pour le prototype Godot.
rem Requete : Blender 4.x ou 5.x installe (commande `blender`).
blender --background --python "%~dp0..\blender\build_rider.py"
