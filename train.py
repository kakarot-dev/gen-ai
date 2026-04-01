"""Train RL agents.

Usage:
    python train.py --type goal --npc-type zombie --timesteps 500000
    python train.py --type goal --npc-type skeleton --timesteps 500000
"""
import argparse
import time
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback


def make_goal_env(npc_type, rank=0):
    def _init():
        from ai.rl.goal_env import GoalSelectionEnv
        return GoalSelectionEnv(npc_type=npc_type)
    return _init


def train_goal_selection(npc_type, timesteps, n_envs, device, lr):
    """Train a goal-selection policy — learns WHEN to pick which GOAP goal."""
    save_path = Path("models") / f"{npc_type}_goal"
    save_path.mkdir(parents=True, exist_ok=True)

    print(f"=== Training GOAL SELECTION for {npc_type.upper()} ===")
    print(f"  Timesteps: {timesteps:,}")
    print(f"  Envs: {n_envs}")
    print(f"  Device: {device}")
    print(f"  Action space: 12 GOAP goals")
    print(f"  Observation: 15 floats (health, dist, etc)")
    print()

    vec_env = VecMonitor(SubprocVecEnv([make_goal_env(npc_type, i) for i in range(n_envs)]))
    eval_env = VecMonitor(SubprocVecEnv([make_goal_env(npc_type, 99)]))

    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=lr,
        batch_size=64,
        n_steps=1024,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.05,   # higher entropy = more exploration of different goals
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=0,
        device=device,
        tensorboard_log=str(save_path / "tb_logs"),
        policy_kwargs=dict(net_arch=dict(pi=[128, 128], vf=[128, 128])),
    )

    print(f"Policy: {model.policy.__class__.__name__}")
    print(f"Obs: {vec_env.observation_space}")
    print(f"Act: {vec_env.action_space}")
    print()

    checkpoint_cb = CheckpointCallback(
        save_freq=max(timesteps // 10, 5000),
        save_path=str(save_path / "checkpoints"),
        name_prefix=f"{npc_type}_goal",
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(save_path / "best"),
        log_path=str(save_path / "eval_logs"),
        eval_freq=max(timesteps // 20, 2500),
        n_eval_episodes=10,
        deterministic=True,
    )

    start = time.time()
    model.learn(
        total_timesteps=timesteps,
        callback=[checkpoint_cb, eval_cb],
        progress_bar=True,
    )
    elapsed = time.time() - start

    final_path = str(save_path / f"{npc_type}_goal_final")
    model.save(final_path)

    print(f"\nTraining complete in {elapsed:.1f}s")
    print(f"Model saved to: {final_path}")

    vec_env.close()
    eval_env.close()
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train RL agents")
    parser.add_argument("--type", default="goal", choices=["goal"])
    parser.add_argument("--npc-type", default="zombie", choices=["zombie", "skeleton"])
    parser.add_argument("--timesteps", type=int, default=500_000)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--lr", type=float, default=3e-4)
    args = parser.parse_args()

    train_goal_selection(
        npc_type=args.npc_type,
        timesteps=args.timesteps,
        n_envs=args.n_envs,
        device=args.device,
        lr=args.lr,
    )
