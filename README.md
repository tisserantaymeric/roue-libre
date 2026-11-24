# Roue Libre — cyclisme virtuel sur Linux

Une application de cyclisme d'intérieur minimaliste, gratuite et sans compte :
vous pédalez sur home trainer, l'application affiche un **monde 3D animé**
(votre coureur pédale dans le paysage, la caméra le suit), vos données et gère
la résistance automatiquement.

Fonctions essentielles :

- **Vue 3D** : terrain en relief avec virages doux et pente réelle, coureur
  qui pédale au rythme de votre cadence, caméra de suivi (Qt Quick 3D, rendu
  GPU). Si l'ordinateur ne gère pas la 3D, repli automatique sur une vue
  animée 2D, et toutes les fonctions restent disponibles
- **Home trainer connecté** en Bluetooth (standard FTMS : Wahoo, Elite, Tacx,
  Zwift Hub, Magene…), avec puissance, vitesse et cadence
- **Cardiomètre Bluetooth** en option
- **Panneau de données complet** + profil du parcours
- **Parcours intégrés** : quatre mondes fictifs (Lac, Toscane, Atlantique,
  Montagne) et le **col de la Chapelotte depuis Badonviller** (Vosges, profil
  réel : 5,8 km à 2,4 % — pente ponctuelle 6,8 % — puis descente)
- **Import de cols réels** en fichiers GPX (traces téléchargeables sur les
  sites de randonnée et de cyclisme, ou exportées depuis un GPS)
- **Résistance automatique** : le home trainer adapte la difficulté à la pente
- **Entraînements guidés** : endurance, fractionné 30/30, côtes progressives,
  en mode ERG (le home trainer impose la puissance cible)
- **Historique** des séances, sauvegardé sur votre ordinateur

Utilisation personnelle uniquement, aucune donnée n'est collectée.

---

## Installation (une seule fois, puis `./run.sh`)

Testé sur Debian 13, Ubuntu 24.04 et dérivés (Mint…). Ouvrez un terminal dans
le dossier du projet :

```sh
sh install.sh
```

Le script installe les dépendances système (via `sudo`), crée l'environnement
Python et prépare le lanceur. Pour lancer l'application ensuite :

```sh
sh run.sh
```

Après la première installation, `./run.sh` fonctionne aussi.

Sans matériel sous la main, cliquez sur **« Mode démo »** : un home trainer
virtuel permet d'essayer tout le logiciel (touches ↑ / ↓ pour moduler
l'effort).

## Brancher le matériel

1. Allumez le home trainer et le Bluetooth de l'ordinateur.
2. Mettez le home trainer en mode appairage (LED bleue clignotante, ou bouton
   Bluetooth de l'appareil).
3. Dans l'application, cliquez sur **« Rechercher mon matériel Bluetooth »**.
4. Sélectionnez votre home trainer, ajoutez un cardiomètre si vous en avez un,
   puis **« Se connecter et continuer »**.

> Conseil : si la recherche ne voit rien, ajoutez votre utilisateur au groupe
> bluetooth : `sudo usermod -aG bluetooth $USER`, puis déconnectez/reconnectez
> votre session.

## Dérouler une séance

1. Choisissez un **parcours** (fictif ou GPX) ou un **entraînement guidé**.
2. Cliquez **« Commencer la séance »** — la première fois, le monde 3D est
   généré (~3 secondes par parcours, ensuite instantané grâce au cache).
3. Pédalez ! En sortie libre, la résistance suit la pente ; en entraînement,
   le home trainer impose la puissance cible de chaque intervalle.
4. `Espace` : pause, `Échap` : terminer. Le résumé est enregistré
   automatiquement et consultable dans l'historique.

## Gérer son FTP

Le menu **Réglages…** permet de renseigner votre prénom, votre poids et votre
**FTP** (puissance de référence). C'est lui qui étalonne les entraînements :
une bonne estimation est la puissance maximale que vous pouvez tenir pendant
20 minutes, moins 5 %. Vous pouvez aussi laisser 200 W pour débuter.

## Ajouter un parcours GPX

Bouton **« Importer un GPX… »** — le fichier est copié dans vos parcours
(~/.local/share/roue-libre/parcours) et un monde 3D correspondant est généré
automatiquement.

## Roadmap

- **Palier 1 (fait)** : monde 3D procédural + coureur animé + caméra suivi
- **Palier 2 (fait)** : coureur articulé (genoux, bras, casque, pédalage
  réaliste calculé par liaison de segments) + couleurs personnalisées
  (maillot et vélo, dans Réglages…)
- **Palier 2 bis (à venir)** : coureur réaliste (modèle GLTF animé de qualité)
- **Palier 3** : terrains réels IGN — relief haute précision et arbres à partir
  du nuage de points LiDAR HD (haute précision), service altitude IGN pour les
  GPX légers, option texture photo aérienne (BD ORTHO), et données mondiales
  (SRTM/Copernicus) hors France

## Prototype Godot en parallèle

Un second chantier explore le même jeu sur le moteur 3D open source **Godot**
(coureur GLTF animé par cinématique, boucle 3D, HUD) : voir
[`godot-prototype/README.md`](godot-prototype/README.md). L'application PyQt
ci-dessus reste le produit principal ; les deux partagent les mêmes modèles
(physique, cinématique du pédalage).

## Arborescence du code

```
main.py                     point d'entrée
rouelib/
  physics.py                modèle puissance → vitesse
  routes.py                 parcours GPX + fictifs
  workouts.py               intervalles guidés
  session.py                moteur d'une séance
  world3d.py                génération du monde 3D (terrain, texture, cache)
  ble.py                    Bluetooth FTMS / cardio (bleak)
  trainers.py               matériel + simulateur de démo
  storage.py                historique et réglages locaux
  ui/                       interface graphique (PyQt6) et vue 3D (Qt Quick 3D)
  assets/                   parcours, entraînements et scène QML intégrés
tests/                      tests automatiques du moteur
```

## Dépannage

- **Rien ne s'affiche / pas de fenêtre** : relancez `sh install.sh` pour
  installer les bibliothèques graphiques Qt.
- **Écran noir ou pas de 3D** : installez/actualisez les pilotes graphiques
  (paquet `mesa-utils` recommandé) ; l'application bascule alors seule sur la
  vue 2D, toutes les fonctions restent utilisables.
- **Aucun matériel détecté** : vérifiez que le home trainer est découvrable
  (fermez l'application du téléphone qui pourrait le monopoliser), activez le
  Bluetooth, patientez 30 secondes puis relancez la recherche.
- **La résistance ne change pas** : certains anciens modèles ne gèrent pas le
  contrôle FTMS. L'application fonctionne quand même en affichage simple.
