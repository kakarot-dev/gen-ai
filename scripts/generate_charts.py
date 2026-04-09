"""Generate all charts for the project report.

Charts produced:
    1. training_curves.png      — eval reward over timesteps (both models)
    2. zombie_strategy.png      — pie chart of learned goal distribution
    3. skeleton_strategy.png    — pie chart of learned goal distribution
    4. strategy_comparison.png  — bar chart comparing both roles
    5. reward_components.png    — stacked bar of reward breakdown
    6. architecture_diagram.png — system architecture
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = Path("charts")
OUT.mkdir(exist_ok=True)

# Style
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['font.size'] = 11


def load_eval(npc_type):
    path = f'models/{npc_type}_goal/eval_logs/evaluations.npz'
    if not os.path.exists(path):
        return None, None
    d = np.load(path)
    return d['timesteps'], d['results'].mean(axis=1)


def chart_training_curves():
    """Training reward curves for both models."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for npc, color in [('zombie', '#4CAF50'), ('skeleton', '#E0E0E0')]:
        steps, rewards = load_eval(npc)
        if steps is None:
            continue
        ax.plot(steps / 1000, rewards, 'o-', linewidth=2.5, markersize=8,
                color=color, label=f'{npc.capitalize()} (melee)' if npc=='zombie' else f'{npc.capitalize()} (ranged)',
                markeredgecolor='black', markeredgewidth=1)

    ax.set_xlabel('Training Timesteps (thousands)', fontsize=12)
    ax.set_ylabel('Mean Episode Reward', fontsize=12)
    ax.set_title('RL Training Curves — Eval Reward vs Timesteps',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=11, loc='lower right')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.5)

    plt.tight_layout()
    plt.savefig(OUT / 'training_curves.png', dpi=150)
    plt.close()
    print("Saved training_curves.png")


def get_strategy(npc_type, n_episodes=200):
    """Run trained model and measure goal distribution."""
    from stable_baselines3 import PPO
    from ai.rl.goal_env import GoalSelectionEnv, GOAL_NAMES

    path = f'models/{npc_type}_goal/best/best_model.zip'
    if not os.path.exists(path):
        return None

    model = PPO.load(path, device='cpu')
    env = GoalSelectionEnv(npc_type=npc_type)
    obs, _ = env.reset()
    counts = {g: 0 for g in GOAL_NAMES}

    for _ in range(n_episodes):
        action, _ = model.predict(obs, deterministic=True)
        counts[GOAL_NAMES[int(action)]] += 1
        obs, r, t, tr, _ = env.step(int(action))
        if t or tr:
            obs, _ = env.reset()

    return counts


def chart_strategy_pie(npc_type):
    """Pie chart of learned strategy."""
    counts = get_strategy(npc_type)
    if not counts:
        print(f"No model for {npc_type}")
        return

    # Filter zeros and sort
    items = [(k, v) for k, v in counts.items() if v > 0]
    items.sort(key=lambda x: -x[1])

    labels = [k.replace('_', ' ').title() for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(9, 7))
    colors = plt.cm.Set3(np.linspace(0, 1, len(items)))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.0f%%',
        colors=colors, startangle=90,
        textprops={'fontsize': 11, 'fontweight': 'bold'},
        wedgeprops={'edgecolor': 'black', 'linewidth': 1.2},
    )
    for at in autotexts:
        at.set_color('black')
        at.set_fontsize(10)

    title = f'{npc_type.capitalize()} — Learned Goal Distribution'
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(OUT / f'{npc_type}_strategy.png', dpi=150)
    plt.close()
    print(f"Saved {npc_type}_strategy.png")


def chart_strategy_comparison():
    """Side-by-side bar chart comparing both roles."""
    zombie = get_strategy('zombie')
    skeleton = get_strategy('skeleton')
    if not zombie or not skeleton:
        return

    all_goals = sorted(set(zombie.keys()) | set(skeleton.keys()),
                       key=lambda g: -(zombie.get(g, 0) + skeleton.get(g, 0)))
    all_goals = [g for g in all_goals if zombie.get(g,0)+skeleton.get(g,0) > 0]

    z_pct = [zombie.get(g, 0) / 2 for g in all_goals]
    s_pct = [skeleton.get(g, 0) / 2 for g in all_goals]

    x = np.arange(len(all_goals))
    w = 0.38

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - w/2, z_pct, w, label='Zombie (Melee)', color='#4CAF50', edgecolor='black')
    ax.bar(x + w/2, s_pct, w, label='Skeleton (Ranged)', color='#BDBDBD', edgecolor='black')

    ax.set_xticks(x)
    ax.set_xticklabels([g.replace('_', '\n') for g in all_goals], fontsize=9)
    ax.set_ylabel('Goal Selection %', fontsize=12)
    ax.set_title('Learned Strategy Comparison: Zombie vs Skeleton',
                 fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11)
    ax.grid(True, axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUT / 'strategy_comparison.png', dpi=150)
    plt.close()
    print("Saved strategy_comparison.png")


def chart_reward_components():
    """Bar chart showing reward components for different scenarios."""
    scenarios = [
        'Healthy\n+ Melee Hit',
        'Healthy\n+ Retreat',
        'Hurt (30%)\n+ Melee Hit',
        'Hurt (30%)\n+ Retreat',
        'Critical (15%)\n+ Melee Hit',
        'Critical (15%)\n+ Retreat',
    ]
    # Approx values from reward function
    rewards = [
        1.5 + 0.3 + 0.3*15,   # healthy melee hit: base + close + damage
        -1.5 - 0.05,           # healthy retreat penalty
        1.5 + 0.3 + 0.3*15,    # hurt melee hit (still valuable)
        0.8 + 0.3*0 - 0.05,    # hurt retreat
        -3.0 - 2.0 + 0.3*15,   # critical melee
        3.0 + 0.8,             # critical retreat
    ]
    colors = ['#4CAF50' if r > 0 else '#E57373' for r in rewards]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.bar(scenarios, rewards, color=colors, edgecolor='black')
    ax.axhline(y=0, color='black', linewidth=1)
    ax.set_ylabel('Reward Value', fontsize=12)
    ax.set_title('Zombie Reward Function — Action Evaluation by Scenario',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, axis='y', alpha=0.3)

    for bar, val in zip(bars, rewards):
        y = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, y + (0.2 if y >= 0 else -0.5),
                f'{val:+.2f}', ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()
    plt.savefig(OUT / 'reward_components.png', dpi=150)
    plt.close()
    print("Saved reward_components.png")


def chart_architecture():
    """System architecture diagram."""
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    def box(x, y, w, h, text, color='#E3F2FD', fontsize=11):
        rect = FancyBboxPatch((x, y), w, h,
                              boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor='black', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', wrap=True)

    def arrow(x1, y1, x2, y2, label=''):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.5))
        if label:
            ax.text((x1+x2)/2 + 0.2, (y1+y2)/2, label, fontsize=9, style='italic')

    # Layer 1: AI Brain
    box(0.5, 6.3, 11, 1.3, 'Layer 1: AI Brain (Python)', color='#FFF9C4', fontsize=12)
    box(1, 5, 3, 1, 'GOAP Planner\n(A* search)', color='#FFECB3')
    box(4.5, 5, 3, 1, 'PPO Policy\n(Trained Model)', color='#FFECB3')
    box(8, 5, 3, 1, 'World State\nBuilder', color='#FFECB3')

    # Layer 2: Bridge
    box(0.5, 3.2, 11, 1.3, 'Layer 2: Mineflayer Bridge (Node.js)', color='#C8E6C9', fontsize=12)
    box(1, 2.1, 3, 0.8, 'HTTP API', color='#A5D6A7')
    box(4.5, 2.1, 3, 0.8, 'PvP Combat\nExecution', color='#A5D6A7')
    box(8, 2.1, 3, 0.8, 'Pathfinder\n+ Cover Points', color='#A5D6A7')

    # Layer 3: Minecraft
    box(0.5, 0.4, 11, 1.3, 'Layer 3: Minecraft Server (Paper 1.21.4)', color='#BBDEFB', fontsize=12)

    # Arrows
    arrow(6, 5, 6, 4.5, 'Goal')
    arrow(6, 3.2, 6, 1.7, 'Actions')
    arrow(6, 0.4, 6, -0.1, '')
    ax.annotate('', xy=(6, 3.2), xytext=(6, 1.7),
                arrowprops=dict(arrowstyle='->', color='black', lw=1.5))
    ax.text(6.3, 2.4, 'State', fontsize=9, style='italic')

    ax.set_title('GOAP + RL Minecraft AI System Architecture',
                 fontsize=14, fontweight='bold', pad=10)

    plt.tight_layout()
    plt.savefig(OUT / 'architecture_diagram.png', dpi=150)
    plt.close()
    print("Saved architecture_diagram.png")


def chart_decision_flow():
    """Flow diagram showing how a decision is made."""
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')

    def box(x, y, w, h, text, color='#E3F2FD'):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                              facecolor=color, edgecolor='black', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=10, fontweight='bold')

    def arrow(x1, y1, x2, y2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='black', lw=2))

    box(0.3, 5.5, 2.5, 1.5, 'Minecraft\nGame State', '#FFE0B2')
    box(3.5, 5.5, 2.5, 1.5, '15-Float\nObservation', '#FFF9C4')
    box(6.7, 5.5, 2.5, 1.5, 'PPO Neural Net\n(128x128 MLP)', '#C8E6C9')
    box(9.9, 5.5, 3.5, 1.5, 'Goal: "melee_attack"\n(from 12 options)', '#B3E5FC')

    box(0.3, 2.5, 2.5, 1.5, 'Mineflayer\nBridge', '#E1BEE7')
    box(3.5, 2.5, 2.5, 1.5, 'Native Combat\nExecution', '#E1BEE7')
    box(6.7, 2.5, 2.5, 1.5, 'Bot Action\n(attack, move)', '#E1BEE7')
    box(9.9, 2.5, 3.5, 1.5, 'Player Sees\nAction in Game', '#FFCDD2')

    arrow(2.8, 6.25, 3.5, 6.25)
    arrow(6, 6.25, 6.7, 6.25)
    arrow(9.2, 6.25, 9.9, 6.25)
    arrow(11.65, 5.5, 11.65, 4.0)
    arrow(9.9, 3.25, 9.2, 3.25)
    arrow(6.7, 3.25, 6.0, 3.25)
    arrow(3.5, 3.25, 2.8, 3.25)
    arrow(1.55, 2.5, 1.55, -0.2)  # loop back

    ax.text(7, 0.2, 'Every 250ms: observe → predict → act → repeat',
            ha='center', fontsize=11, style='italic')
    ax.set_title('RL Decision Flow — From Game State to Bot Action',
                 fontsize=14, fontweight='bold', pad=10)

    plt.tight_layout()
    plt.savefig(OUT / 'decision_flow.png', dpi=150)
    plt.close()
    print("Saved decision_flow.png")


if __name__ == "__main__":
    print("Generating charts...")
    chart_training_curves()
    chart_strategy_pie('zombie')
    chart_strategy_pie('skeleton')
    chart_strategy_comparison()
    chart_reward_components()
    chart_architecture()
    chart_decision_flow()
    print(f"\nAll charts saved to {OUT}/")
