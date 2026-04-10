"""Deploy AI bots in Minecraft.

Usage:
    python play.py --mode goap      # GOAP only (hand-crafted rules)
    python play.py --mode rl        # RL only (trained model)
    python play.py --mode hybrid    # GOAP + RL combined
"""
import argparse
import time
import sys
import math
from minecraft.mc_controller import MCGameState, MCNPCController

MODE_LABELS = {
    "goap": "GOAP Only (hand-crafted rules)",
    "rl": "RL Only (trained model)",
    "hybrid": "GOAP + RL Hybrid",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="goap", choices=["goap", "rl", "hybrid"])
    parser.add_argument("--model", default="models/zombie/best/best_model.zip")
    args = parser.parse_args()

    print("=" * 50)
    print(f"  Mode: {MODE_LABELS[args.mode]}")
    print("=" * 50)
    print()

    # Spawn bots
    print("Connecting bots...")
    try:
        result = MCGameState.spawn_bots()
        print(f"  Bots: {result.get('bots', [])}")
    except Exception:
        print("ERROR: Bridge not running. Run: just bridge")
        sys.exit(1)

    # Tell bridge which mode we're running
    import requests
    try:
        requests.post("http://localhost:3001/mode", json={"mode": args.mode}, timeout=2)
    except Exception:
        pass

    # Use the old aggressive 42-obs/76-action model (pre-tactical)
    # This is the working baseline that actually engages combat
    old_model = "models/zombie/best/best_model.zip" if args.mode in ("rl", "hybrid") else None

    zombie = MCNPCController("zombie", "zombie", mode=args.mode, model_path=old_model)
    skeleton = MCNPCController("skeleton", "skeleton", mode=args.mode, model_path=old_model)
    controllers = [zombie, skeleton]

    print()
    print(f"AI [{args.mode.upper()}] is LIVE. Join localhost:25565.")
    print("Press Ctrl+C to stop.")
    print()
    print(f"{'Bot':>10s}  {'Goal':>20s}  {'HP':>6s}  {'Dist':>5s}")
    print("-" * 50)

    prev_goals = {}
    tick_count = 0

    try:
        while True:
            start = time.time()
            tick_count += 1

            try:
                state = MCGameState.get()
            except Exception:
                time.sleep(1)
                continue

            players = state.get("players", {})
            if not players:
                if tick_count % 30 == 0:
                    print("  Waiting for player...")
                time.sleep(0.5)
                continue

            for ctrl in controllers:
                bs = state.get("bots", {}).get(ctrl.bot_id, {})
                if not bs:
                    continue
                if not bs.get("alive", False):
                    try:
                        ctrl.client.set_goal("idle")
                    except Exception:
                        pass
                    continue

                try:
                    ctrl.tick(state)
                except Exception as e:
                    if tick_count % 30 == 0:
                        print(f"  [{ctrl.bot_id}] Error: {e}")

                goal = ctrl._prev_goal
                hp = bs.get("health", 0)
                prev = prev_goals.get(ctrl.bot_id)
                if goal != prev:
                    tp = list(players.values())[0]["position"]
                    bp = bs["position"]
                    dist = math.hypot(tp["x"]-bp["x"], tp["z"]-bp["z"])
                    print(f"  {ctrl.bot_id:>8s}  {goal:>20s}  {hp:>5.0f}  {dist:>5.0f}")
                    prev_goals[ctrl.bot_id] = goal

            elapsed = time.time() - start
            time.sleep(max(0, 0.25 - elapsed))

    except KeyboardInterrupt:
        print("\nStopping bots...")
        for ctrl in controllers:
            try:
                ctrl.client.set_goal("idle")
            except Exception:
                pass
        print("Done.")


if __name__ == "__main__":
    main()
