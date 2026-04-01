# Experiment Findings

## Training Results (Zombie, 500K steps, PPO)

| Steps | Train Reward | Eval Reward | Behavior |
|-------|-------------|-------------|----------|
| 20K   | -5.26       | —           | Random actions |
| 100K  | -3.01       | **8.07**    | Aggressive melee (80% sword) |
| 200K  | 1.55        | 4.13        | Mixed combat |
| 300K  | 7.30        | 4.30        | Stable fighter |
| 400K  | 9.48        | -15.68      | Overfit — dies in eval |
| 500K  | 9.24        | 0.70        | Cautious ranged (55% move, 36% bow) |

**Key finding**: Best eval performance at 100K steps, not 500K. Agent overfits to training opponent with more steps.

## Mode Comparison (Observed in Minecraft)

### GOAP Mode
- **Behavior**: Switches goals dynamically every few seconds
- **Strengths**: Reactive — adapts to health changes, distance changes
- **Weakness**: Switches too often, looks "indecisive"
- **Example log**: chase → melee_attack → retreat → chase → melee_attack (loops)

### RL Mode
- **Behavior**: Picks one strategy and commits to it
- **Strengths**: Consistent, learned from experience
- **Weakness**: Doesn't adapt mid-fight — stuck on one goal (maintain_distance)
- **Reason**: Deterministic policy outputs same action for similar observations
- **Note**: Both bots used zombie model — skeleton needs its own trained model

### Hybrid Mode (Expected)
- GOAP provides reactive goal switching
- RL overrides when it has learned a better choice
- Should combine reactivity of GOAP with learned strategy of RL

## Issues Found
1. RL model trained only for zombie — skeleton reuses zombie model
2. RL deterministic mode = no variation in behavior
3. 500K steps not enough for robust policy — needs 2M+
4. Observation mismatch: simulation obs vs Minecraft obs (velocities missing)
5. Eval reward crashed at 400K — sign of overfitting

## Next Steps
- Train skeleton-specific model
- Train longer (2M steps) with entropy bonus for more exploration
- Use stochastic (not deterministic) prediction for variety
- Fix observation vector to better match Minecraft state
