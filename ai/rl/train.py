"""RL Training pipeline — trains goal-conditioned PPO agents."""
from __future__ import annotations

import os
import time
from pathlib import Path

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from stable_baselines3.common.callbacks import (
    CheckpointCallback, EvalCallback, BaseCallback
)

from ai.rl.environment import ArenaEnv, GOAL_NAMES


class TrainingLogger(BaseCallback):
    """Logs training progress to console."""

    def __init__(self, log_interval: int = 5000, verbose=1):
        super().__init__(verbose)
        self.log_interval = log_interval
        self.episode_rewards = []
        self.episode_lengths = []

    def _on_step(self) -> bool:
        if self.n_calls % self.log_interval == 0:
            if len(self.episode_rewards) > 0:
                avg_reward = sum(self.episode_rewards[-100:]) / min(len(self.episode_rewards), 100)
                avg_length = sum(self.episode_lengths[-100:]) / min(len(self.episode_lengths), 100)
                print(f"Step {self.num_timesteps:>8d} | "
                      f"Avg Reward: {avg_reward:>7.2f} | "
                      f"Avg Length: {avg_length:>6.0f} | "
                      f"Episodes: {len(self.episode_rewards)}")
        # Collect episode info
        for info in self.locals.get("infos", []):
            if "episode" in info:
                self.episode_rewards.append(info["episode"]["r"])
                self.episode_lengths.append(info["episode"]["l"])
        return True


def make_env(npc_type: str, goal: str | None = None, rank: int = 0):
    """Create a function that returns an env instance."""
    def _init():
        env = ArenaEnv(npc_type=npc_type, max_steps=1800)
        if goal:
            env.set_goal(goal)
        return env
    return _init


def train(
    npc_type: str = "zombie",
    total_timesteps: int = 500_000,
    n_envs: int = 4,
    save_dir: str = "models",
    learning_rate: float = 3e-4,
    batch_size: int = 64,
    n_steps: int = 2048,
    device: str = "auto",
):
    """Train a PPO agent for an NPC type.

    Args:
        npc_type: "zombie" or "skeleton"
        total_timesteps: total training steps
        n_envs: number of parallel environments
        save_dir: where to save model checkpoints
        learning_rate: PPO learning rate
        batch_size: PPO minibatch size
        n_steps: steps per rollout
        device: "auto", "cuda", or "cpu"
    """
    save_path = Path(save_dir) / npc_type
    save_path.mkdir(parents=True, exist_ok=True)

    print(f"=== Training {npc_type.upper()} agent ===")
    print(f"Timesteps: {total_timesteps:,}")
    print(f"Parallel envs: {n_envs}")
    print(f"Device: {device}")
    print()

    # Create vectorized environment
    env_fns = [make_env(npc_type, rank=i) for i in range(n_envs)]
    vec_env = SubprocVecEnv(env_fns)
    vec_env = VecMonitor(vec_env)

    # Create eval env
    eval_env = VecMonitor(SubprocVecEnv([make_env(npc_type, rank=99)]))

    # Create PPO model
    model = PPO(
        "MlpPolicy",
        vec_env,
        learning_rate=learning_rate,
        batch_size=batch_size,
        n_steps=n_steps,
        n_epochs=10,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        vf_coef=0.5,
        max_grad_norm=0.5,
        verbose=0,
        device=device,
        tensorboard_log=str(save_path / "tb_logs"),
        policy_kwargs=dict(
            net_arch=dict(pi=[256, 256], vf=[256, 256]),
        ),
    )

    print(f"Policy network: {model.policy}")
    print(f"Observation space: {vec_env.observation_space}")
    print(f"Action space: {vec_env.action_space}")
    print()

    # Callbacks
    checkpoint_cb = CheckpointCallback(
        save_freq=max(total_timesteps // 10, 10000),
        save_path=str(save_path / "checkpoints"),
        name_prefix=npc_type,
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(save_path / "best"),
        log_path=str(save_path / "eval_logs"),
        eval_freq=max(total_timesteps // 20, 5000),
        n_eval_episodes=10,
        deterministic=True,
    )
    logger_cb = TrainingLogger(log_interval=5000)

    # Train!
    start = time.time()
    model.learn(
        total_timesteps=total_timesteps,
        callback=[checkpoint_cb, eval_cb, logger_cb],
        progress_bar=True,
    )
    elapsed = time.time() - start

    # Save final model
    final_path = str(save_path / f"{npc_type}_final")
    model.save(final_path)

    print(f"\nTraining complete in {elapsed:.1f}s")
    print(f"Final model saved to: {final_path}")

    vec_env.close()
    eval_env.close()

    return model


def load_model(npc_type: str, model_dir: str = "models") -> PPO:
    """Load a trained model."""
    # Try best model first, then final
    best_path = Path(model_dir) / npc_type / "best" / "best_model.zip"
    final_path = Path(model_dir) / npc_type / f"{npc_type}_final.zip"

    if best_path.exists():
        print(f"Loading best model from {best_path}")
        return PPO.load(str(best_path))
    elif final_path.exists():
        print(f"Loading final model from {final_path}")
        return PPO.load(str(final_path))
    else:
        raise FileNotFoundError(
            f"No trained model found for {npc_type} in {model_dir}/"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train RL agents")
    parser.add_argument("--npc-type", default="zombie", choices=["zombie", "skeleton"])
    parser.add_argument("--timesteps", type=int, default=500_000)
    parser.add_argument("--n-envs", type=int, default=4)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--lr", type=float, default=3e-4)
    args = parser.parse_args()

    train(
        npc_type=args.npc_type,
        total_timesteps=args.timesteps,
        n_envs=args.n_envs,
        device=args.device,
        learning_rate=args.lr,
    )
