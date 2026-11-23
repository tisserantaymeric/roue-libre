import QtQuick
import QtQuick3D

View3D {
    id: viewRoot
    anchors.fill: parent

    function legAngle(phase) {
        var th = (viewRoot.crank + phase) * Math.PI / 180.0
        var fx = 0.17 * Math.cos(th) + 0.17
        var fy = -0.72 + 0.17 * Math.sin(th)
        return Math.atan2(fx, -fy) * 180.0 / Math.PI
    }

    property real crank: 0

    environment: SceneEnvironment {
        backgroundMode: SceneEnvironment.Color
        clearColor: worldBridge.skyColor
    }

    Timer {
        interval: 50
        running: viewRoot.visible
        repeat: true
        onTriggered: {
            if (worldBridge.cadence > 0)
                viewRoot.crank = (viewRoot.crank + worldBridge.cadence / 60.0 * 18.0) % 360
        }
    }

    DirectionalLight { eulerRotation.x: -42; eulerRotation.y: -25; brightness: 1.35 }
    DirectionalLight { eulerRotation.x: 15; eulerRotation.y: 140; brightness: 0.5 }

    PerspectiveCamera {
        id: camera
        fieldOfView: 55
        position: Qt.vector3d(worldBridge.cx, worldBridge.cy, worldBridge.cz)
        eulerRotation.y: worldBridge.camYaw
        eulerRotation.x: worldBridge.camPitch
    }

    DefaultMaterial {
        id: terrainMaterial
        cullMode: Material.NoCulling
        specularAmount: 0.05
        diffuseColor: "#ffffff"
        diffuseMap: Texture {
            source: worldBridge.textureUrl
            generateMipmaps: true
        }
    }

    Model {
        source: worldBridge.terrainUrl
        material: terrainMaterial
    }

    Component { id: frameMatRef
        DefaultMaterial { diffuseColor: worldBridge.frameColor; specularAmount: 0.2 } }
    Component { id: darkMatRef
        DefaultMaterial { diffuseColor: "#23262b"; specularAmount: 0.1 } }
    Component { id: skinMatRef
        DefaultMaterial { diffuseColor: "#d9b070"; specularAmount: 0.05 } }

    // -- coureur -----------------------------------------------------------
    Node {
        id: rider
        position: Qt.vector3d(worldBridge.px, worldBridge.py, worldBridge.pz)
        eulerRotation.y: worldBridge.yaw
        eulerRotation.x: worldBridge.pitch

        Model { // roue arrière
            source: "#Cylinder"
            position: Qt.vector3d(-0.53, 0.34, 0)
            eulerRotation.x: 90
            scale: Qt.vector3d(0.68, 0.035, 0.68)
            material: darkMatRef
        }
        Model { // roue avant
            source: "#Cylinder"
            position: Qt.vector3d(0.53, 0.34, 0)
            eulerRotation.x: 90
            scale: Qt.vector3d(0.68, 0.035, 0.68)
            material: darkMatRef
        }
        Model { // cadre
            source: "#Cube"
            position: Qt.vector3d(0, 0.50, 0)
            eulerRotation.z: -20
            scale: Qt.vector3d(1.0, 0.08, 0.05)
            material: frameMatRef
        }
        Model { // tube de selle
            source: "#Cube"
            position: Qt.vector3d(-0.25, 0.62, 0)
            eulerRotation.z: 18
            scale: Qt.vector3d(0.36, 0.06, 0.05)
            material: darkMatRef
        }
        Model { // guidon
            source: "#Cube"
            position: Qt.vector3d(0.36, 0.78, 0)
            eulerRotation.z: -40
            scale: Qt.vector3d(0.40, 0.05, 0.05)
            material: darkMatRef
        }

        Node { // boîtier de pédalier
            position: Qt.vector3d(0, 0.30, 0)
            eulerRotation.z: viewRoot.crank
            Model { source: "#Cube"; position: Qt.vector3d(0, 0.085, 0)
                    scale: Qt.vector3d(0.04, 0.17, 0.03); material: darkMatRef }
            Model { source: "#Cube"; position: Qt.vector3d(0, -0.085, 0)
                    scale: Qt.vector3d(0.04, 0.17, 0.03); material: darkMatRef }
        }

        Node { // jambes
            property real phaseA: 0
            property real phaseB: 180
            Model { source: "#Cylinder"
                    position: Qt.vector3d(0, -0.36, 0.10)
                    eulerRotation.z: viewRoot.legAngle(0)
                    scale: Qt.vector3d(0.12, 0.72, 0.12)
                    material: frameMatRef }
            Model { source: "#Cylinder"
                    position: Qt.vector3d(0, -0.36, -0.10)
                    eulerRotation.z: viewRoot.legAngle(180)
                    scale: Qt.vector3d(0.12, 0.72, 0.12)
                    material: frameMatRef }
        }

        Model { // torse
            source: "#Sphere"
            position: Qt.vector3d(-0.30, 1.12, 0)
            eulerRotation.z: 32
            scale: Qt.vector3d(0.17, 0.30, 0.13)
            material: frameMatRef
        }
        Model { // tête
            source: "#Sphere"
            position: Qt.vector3d(-0.16, 1.34, 0)
            scale: Qt.vector3d(0.12, 0.12, 0.12)
            material: skinMatRef
        }
    }
}
