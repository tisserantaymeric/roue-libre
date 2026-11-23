import QtQuick
import QtQuick3D
import QtQuick3D.AssetUtils

View3D {
    id: viewRoot
    anchors.fill: parent

    environment: SceneEnvironment {
        backgroundMode: SceneEnvironment.Color
        clearColor: worldBridge.skyColor
    }

    DirectionalLight { eulerRotation.x: -42; eulerRotation.y: -25; brightness: 1.35 }
    DirectionalLight { eulerRotation.x: 15; eulerRotation.y: 140; brightness: 0.5 }

    PerspectiveCamera {
        id: camera
        fieldOfView: 55
        clipNear: 0.1
        clipFar: 30000
        position: Qt.vector3d(worldBridge.cx, worldBridge.cy, worldBridge.cz)
        eulerRotation.y: worldBridge.camYaw
        eulerRotation.x: worldBridge.camPitch
    }

    // -- terrain (GLB, matériau et texture intégrés) --------------------------
    RuntimeLoader {
        id: terrainLoader
        source: worldBridge.terrainUrl
        onStatusChanged: {
            if (status === RuntimeLoader.Error)
                worldBridge.terrainFailed(errorString)
        }
    }

    // -- coureur --------------------------------------------------------------
    // Primitives Qt : #Cube / #Cylinder / #Sphere font 100 unités, d'où les
    // échelles en /100 pour obtenir des mesures réelles en mètres.
    Node {
        id: rider
        position: Qt.vector3d(worldBridge.px, worldBridge.py, worldBridge.pz)
        eulerRotation.y: worldBridge.yaw

        Node { // tangage : suit la pente autour de l'axe latéral
            eulerRotation.z: worldBridge.pitch

            Model { // roue arrière
                source: "#Cylinder"
                position: Qt.vector3d(-0.53, 0.34, 0)
                eulerRotation.x: 90
                scale: Qt.vector3d(0.0068, 0.00035, 0.0068)
                materials: DefaultMaterial { diffuseColor: "#23262b" }
            }
            Model { // roue avant
                source: "#Cylinder"
                position: Qt.vector3d(0.53, 0.34, 0)
                eulerRotation.x: 90
                scale: Qt.vector3d(0.0068, 0.00035, 0.0068)
                materials: DefaultMaterial { diffuseColor: "#23262b" }
            }
            Model { // fourche
                source: "#Cube"
                position: Qt.vector3d(0.465, 0.53, 0)
                eulerRotation.z: 19
                scale: Qt.vector3d(0.0006, 0.0040, 0.0004)
                materials: DefaultMaterial { diffuseColor: worldBridge.bikeColor }
            }
            Model { // cadre
                source: "#Cube"
                position: Qt.vector3d(0, 0.50, 0)
                eulerRotation.z: -20
                scale: Qt.vector3d(0.010, 0.0008, 0.0005)
                materials: DefaultMaterial { diffuseColor: worldBridge.bikeColor }
            }
            Model { // tube de selle
                source: "#Cube"
                position: Qt.vector3d(-0.25, 0.62, 0)
                eulerRotation.z: 18
                scale: Qt.vector3d(0.0036, 0.0006, 0.0005)
                materials: DefaultMaterial { diffuseColor: worldBridge.bikeColor }
            }
            Model { // selle
                source: "#Cube"
                position: Qt.vector3d(-0.30, 0.85, 0)
                scale: Qt.vector3d(0.0024, 0.0004, 0.0008)
                materials: DefaultMaterial { diffuseColor: "#22262c" }
            }
            Model { // guidon (barre latérale)
                source: "#Cube"
                position: Qt.vector3d(0.36, 0.78, 0)
                eulerRotation.y: 90
                scale: Qt.vector3d(0.0044, 0.0004, 0.0004)
                materials: DefaultMaterial { diffuseColor: worldBridge.bikeColor }
            }

            Node { // pédalier (manivelles tournent avec la cadence)
                position: Qt.vector3d(0, 0.30, 0)
                eulerRotation.z: worldBridge.crank
                Model { source: "#Cube"; position: Qt.vector3d(0, 0.085, 0)
                        scale: Qt.vector3d(0.0005, 0.0017, 0.0003)
                        materials: DefaultMaterial { diffuseColor: "#23262b" } }
                Model { source: "#Cube"; position: Qt.vector3d(0, -0.085, 0)
                        scale: Qt.vector3d(0.0005, 0.0017, 0.0003)
                        materials: DefaultMaterial { diffuseColor: "#23262b" } }
            }

            Node { // jambe arrière (vis-à-vis)
                position: Qt.vector3d(-0.15, 1.00, -0.09)
                eulerRotation.z: worldBridge.thighZ1
                Model { // cuisse (cuissard)
                    source: "#Cylinder"
                    position: Qt.vector3d(0, -0.23, 0)
                    scale: Qt.vector3d(0.0012, 0.0046, 0.0012)
                    materials: DefaultMaterial { diffuseColor: "#22262c" }
                }
                Model { // genou
                    source: "#Sphere"
                    position: Qt.vector3d(0, -0.46, 0)
                    scale: Qt.vector3d(0.0007, 0.0007, 0.0007)
                    materials: DefaultMaterial { diffuseColor: "#22262c" }
                }
                Node {
                    position: Qt.vector3d(0, -0.46, 0)
                    eulerRotation.z: worldBridge.kneeZ1
                    Model { // tibia
                        source: "#Cylinder"
                        position: Qt.vector3d(0, -0.23, 0)
                        scale: Qt.vector3d(0.0009, 0.0046, 0.0009)
                        materials: DefaultMaterial { diffuseColor: "#d9b070" }
                    }
                    Model { // chaussure
                        source: "#Cube"
                        position: Qt.vector3d(0.05, -0.45, 0)
                        scale: Qt.vector3d(0.0026, 0.0008, 0.0010)
                        materials: DefaultMaterial { diffuseColor: "#e8e8ec" }
                    }
                }
            }

            Node { // jambe avant
                position: Qt.vector3d(-0.15, 1.00, 0.09)
                eulerRotation.z: worldBridge.thighZ0
                Model { // cuisse (cuissard)
                    source: "#Cylinder"
                    position: Qt.vector3d(0, -0.23, 0)
                    scale: Qt.vector3d(0.0012, 0.0046, 0.0012)
                    materials: DefaultMaterial { diffuseColor: "#22262c" }
                }
                Model { // genou
                    source: "#Sphere"
                    position: Qt.vector3d(0, -0.46, 0)
                    scale: Qt.vector3d(0.0007, 0.0007, 0.0007)
                    materials: DefaultMaterial { diffuseColor: "#22262c" }
                }
                Node {
                    position: Qt.vector3d(0, -0.46, 0)
                    eulerRotation.z: worldBridge.kneeZ0
                    Model { // tibia
                        source: "#Cylinder"
                        position: Qt.vector3d(0, -0.23, 0)
                        scale: Qt.vector3d(0.0009, 0.0046, 0.0009)
                        materials: DefaultMaterial { diffuseColor: "#d9b070" }
                    }
                    Model { // chaussure
                        source: "#Cube"
                        position: Qt.vector3d(0.05, -0.45, 0)
                        scale: Qt.vector3d(0.0026, 0.0008, 0.0010)
                        materials: DefaultMaterial { diffuseColor: "#e8e8ec" }
                    }
                }
            }

            Model { // torse (maillot + buste penché en avant)
                source: "#Sphere"
                position: Qt.vector3d(-0.28, 1.02, 0)
                eulerRotation.z: -8
                scale: Qt.vector3d(0.0034, 0.0044, 0.0026)
                materials: DefaultMaterial { diffuseColor: worldBridge.jerseyColor }
            }
            Node { // bras (tombent vers le guidon)
                position: Qt.vector3d(-0.28, 1.20, 0.12)
                eulerRotation.z: 58
                Model { source: "#Cylinder"
                        position: Qt.vector3d(0, -0.36, 0)
                        scale: Qt.vector3d(0.0008, 0.0072, 0.0008)
                        materials: DefaultMaterial { diffuseColor: worldBridge.jerseyColor } }
                Model { source: "#Cube" // main
                        position: Qt.vector3d(0, -0.72, 0)
                        scale: Qt.vector3d(0.0009, 0.0008, 0.0014)
                        materials: DefaultMaterial { diffuseColor: "#d9b070" } }
            }
            Node {
                position: Qt.vector3d(-0.28, 1.20, -0.12)
                eulerRotation.z: 58
                Model { source: "#Cylinder"
                        position: Qt.vector3d(0, -0.36, 0)
                        scale: Qt.vector3d(0.0008, 0.0072, 0.0008)
                        materials: DefaultMaterial { diffuseColor: worldBridge.jerseyColor } }
                Model { source: "#Cube"
                        position: Qt.vector3d(0, -0.72, 0)
                        scale: Qt.vector3d(0.0009, 0.0008, 0.0014)
                        materials: DefaultMaterial { diffuseColor: "#d9b070" } }
            }
            Model { // tête
                source: "#Sphere"
                position: Qt.vector3d(-0.20, 1.32, 0)
                scale: Qt.vector3d(0.0011, 0.0013, 0.0011)
                materials: DefaultMaterial { diffuseColor: "#d9b070" }
            }
            Model { // casque
                source: "#Sphere"
                position: Qt.vector3d(-0.20, 1.35, 0)
                scale: Qt.vector3d(0.0013, 0.0008, 0.0013)
                materials: DefaultMaterial { diffuseColor: worldBridge.jerseyColor }
            }
        }
    }
}
