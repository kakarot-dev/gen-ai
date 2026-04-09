#!/usr/bin/env bash
# Start Minecraft server + Mineflayer bridge together.
# Ctrl+C stops both.

set -e
cd "$(dirname "$0")/.."

# Cleanup on exit
cleanup() {
    echo ""
    echo "Stopping infrastructure..."
    [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null || true
    [ -n "$BRIDGE_PID" ] && kill $BRIDGE_PID 2>/dev/null || true
    fuser -k 3001/tcp 2>/dev/null || true
    exit 0
}
trap cleanup EXIT INT TERM

# Kill any leftover processes
fuser -k 3001/tcp 2>/dev/null || true
pkill -f "paper.jar" 2>/dev/null || true
sleep 1

# Start Minecraft server
echo "=== Starting Minecraft server ==="
cd minecraft/server
bash start.sh > /tmp/mc_server.log 2>&1 &
SERVER_PID=$!
cd ../..

# Wait for server ready
echo "Waiting for server to be ready..."
for i in {1..120}; do
    if grep -q "For help, type" /tmp/mc_server.log 2>/dev/null; then
        echo "Server ready!"
        break
    fi
    sleep 1
done

if ! grep -q "For help, type" /tmp/mc_server.log 2>/dev/null; then
    echo "ERROR: Server failed to start in 120s. Check /tmp/mc_server.log"
    exit 1
fi

# Start bridge
echo ""
echo "=== Starting Mineflayer bridge ==="
cd minecraft/bridge
node server.js > /tmp/mc_bridge.log 2>&1 &
BRIDGE_PID=$!
cd ../..

sleep 3

# Check bridge is up
if curl -s http://localhost:3001/state > /dev/null 2>&1 || [ $? -eq 22 ]; then
    echo "Bridge running on port 3001"
else
    echo "Waiting for bridge..."
    sleep 2
fi

# Spawn bots
echo ""
echo "=== Spawning bots ==="
curl -s -X POST http://localhost:3001/bots/spawn
echo ""
sleep 4

echo ""
echo "============================================"
echo "  Infrastructure ready!"
echo "  MC Server: localhost:25565"
echo "  Bridge:    localhost:3001"
echo "============================================"
echo ""
echo "  In another terminal, run:"
echo "    just play-goap    # GOAP only"
echo "    just play-rl      # Trained RL"
echo "    just play-hybrid  # GOAP + RL"
echo ""
echo "  Logs:"
echo "    tail -f /tmp/mc_server.log"
echo "    tail -f /tmp/mc_bridge.log"
echo ""
echo "  Ctrl+C to stop everything."
echo ""

# Keep script alive, stream bridge output
wait $BRIDGE_PID
