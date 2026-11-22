#!/bin/sh
# Installation de Roue Libre (Debian/Ubuntu/Mint).
set -e

echo "== Roue Libre : installation =="

if command -v apt-get >/dev/null 2>&1; then
    echo "-- Installation des dépendances système (mot de passe demandé)"
    sudo apt-get install -y python3-venv python3-pip bluetooth bluez \
        libxkbcommon0 libxkbcommon-x11-0 libgl1 libegl1 \
        libxcb-cursor0 libglib2.0-0t64 libdbus-1-3 libfontconfig1
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y python3-pip bluez libxkbcommon libxcb fontconfig
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -S --needed --noconfirm python-pip bluez libxkbcommon-x11
else
    echo "Distribution non reconnue : installez bluetooth/bluez et les"
    echo "bibliothèques Qt de votre distribution, puis relancez ce script."
fi

echo "-- Création de l'environnement Python"
python3 -m venv .venv
. ./.venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cat > run.sh <<'EOF'
#!/bin/sh
cd "$(dirname "$0")"
. ./.venv/bin/activate
exec python3 main.py
EOF
chmod +x run.sh

echo
echo "== Installation terminée =="
echo "Pour lancer l'application :  ./run.sh"
echo "(Pour le Bluetooth, ajoutez votre utilisateur au groupe bluetooth si besoin :"
echo "  sudo usermod -aG bluetooth $USER   puis déconnectez/reconnectez votre session.)"
