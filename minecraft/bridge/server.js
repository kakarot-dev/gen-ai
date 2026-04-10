const express = require('express');
const mineflayer = require('mineflayer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const pvp = require('mineflayer-pvp').plugin;

const app = express();
app.use(express.json());

const PORT = 3001;
const MC_HOST = process.env.MC_HOST || 'localhost';
const MC_PORT = parseInt(process.env.MC_PORT || '25565');

const ARENA = { minX: 202, maxX: 248, minZ: 202, maxZ: 248, y: -59 };

const COVER_POINTS = [
  { x: 205, z: 206, name: 'bunker' },
  { x: 208, z: 208, name: 'bunker' },
  { x: 241, z: 241, name: 'warehouse' },
  { x: 244, z: 244, name: 'warehouse' },
  { x: 242, z: 205, name: 'tower' },
  { x: 206, z: 243, name: 'garage' },
  { x: 209, z: 245, name: 'garage' },
  { x: 216, z: 214, name: 'wall_nw' },
  { x: 232, z: 214, name: 'wall_ne' },
  { x: 216, z: 235, name: 'wall_sw' },
  { x: 232, z: 235, name: 'wall_se' },
  { x: 221, z: 221, name: 'crate_nw' },
  { x: 229, z: 221, name: 'crate_ne' },
];

function findCover(botPos, playerPos) {
  let best = null;
  let bestScore = -Infinity;
  for (const cp of COVER_POINTS) {
    const distFromPlayer = Math.sqrt((cp.x - playerPos.x)**2 + (cp.z - playerPos.z)**2);
    const distFromBot = Math.sqrt((cp.x - botPos.x)**2 + (cp.z - botPos.z)**2);
    const score = distFromPlayer - distFromBot * 0.5;
    if (score > bestScore) {
      bestScore = score;
      best = cp;
    }
  }
  return best || { x: ARENA.minX + 5, z: ARENA.minZ + 5 };
}

const bots = {};
const BOT_CONFIGS = [
  { id: 'zombie',   username: 'Zombie_NPC',   role: 'melee' },
  { id: 'skeleton', username: 'Skeleton_NPC', role: 'ranged' },
];

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

function getTargetPlayer(bot) {
  for (const [name, player] of Object.entries(bot.players)) {
    if (BOT_CONFIGS.some(c => c.username === name)) continue;
    if (!player.entity) continue;
    return player;
  }
  return null;
}

function distTo(bot, entity) {
  return bot.entity.position.distanceTo(entity.position);
}

let hudInterval = null;
function startHUD() {
  if (hudInterval) return;
  hudInterval = setInterval(() => {
    const parts = [];

    const modeColor = currentMode === 'GOAP' ? 'gold' :
                      currentMode === 'RL' ? 'light_purple' : 'aqua';
    parts.push(
      { text: '[', color: 'dark_gray' },
      { text: currentMode, color: modeColor, bold: true },
      { text: '] ', color: 'dark_gray' },
    );

    for (const [id, entry] of Object.entries(bots)) {
      const display = GOAL_DISPLAY[entry.currentGoal] || { text: entry.currentGoal, color: 'white' };
      const hp = Math.round(entry.bot.health || 0);
      const nameColor = id === 'zombie' ? 'green' : 'gray';
      const hpColor = hp < 6 ? 'red' : hp < 12 ? 'yellow' : 'white';
      parts.push(
        { text: id.toUpperCase(), color: nameColor, bold: true },
        { text: ':' + display.text, color: display.color },
        { text: '(' + hp + 'hp) ', color: hpColor },
      );
    }
    if (parts.length <= 3) return;

    for (const entry of Object.values(bots)) {
      if (entry.bot.health > 0) {
        entry.bot.chat('/title @a actionbar ' + JSON.stringify({ text: '', extra: parts }));
        break;
      }
    }
  }, 500);
}

function runBehavior(entry) {
  const { bot, config } = entry;
  startHUD();

  if (entry.behaviorInterval) clearInterval(entry.behaviorInterval);

  const MELEE_REACH = 2.8;
  const BOW_REACH = 25;
  let lastAttackTime = 0;
  const ATTACK_COOLDOWN = 600;

  function canAttack() {
    const now = Date.now();
    if (now - lastAttackTime < ATTACK_COOLDOWN) return false;
    lastAttackTime = now;
    return true;
  }

  entry.behaviorInterval = setInterval(() => {
    if (!bot.entity || bot.health <= 0) return;

    const target = getTargetPlayer(bot);
    if (!target || !target.entity) {
      bot.clearControlStates();
      return;
    }

    const dist = distTo(bot, target.entity);
    const goal = entry.currentGoal || 'idle';

    bot.lookAt(target.entity.position.offset(0, 1.6, 0));

    switch (goal) {
      case 'chase_target':
      case 'dash_attack':
        if (dist > MELEE_REACH) {
          bot.pathfinder.setGoal(new goals.GoalFollow(target.entity, 2), true);
          bot.setControlState('sprint', true);
        } else if (canAttack()) {
          bot.attack(target.entity);
        }
        break;

      case 'melee_attack':
        if (dist <= MELEE_REACH && canAttack()) {
          bot.attack(target.entity);
        } else if (dist > MELEE_REACH) {
          bot.pathfinder.setGoal(new goals.GoalFollow(target.entity, 2), true);
          bot.setControlState('sprint', true);
        }
        break;

      case 'flank_target': {
        const cover = findCover(bot.entity.position, target.entity.position);
        bot.pathfinder.setGoal(new goals.GoalNear(cover.x, ARENA.y, cover.z, 1), true);
        bot.setControlState('sprint', true);
        if (dist <= MELEE_REACH && canAttack()) bot.attack(target.entity);
        break;
      }

      case 'ranged_attack':
        if (dist < 6) {
          const coverR = findCover(bot.entity.position, target.entity.position);
          bot.pathfinder.setGoal(new goals.GoalNear(coverR.x, ARENA.y, coverR.z, 1), true);
        } else if (dist > 20) {
          bot.pathfinder.setGoal(new goals.GoalFollow(target.entity, 15), true);
        }
        if (canAttack()) bot.attack(target.entity);
        break;

      case 'find_vantage_point': {
        const cover = findCover(bot.entity.position, target.entity.position);
        bot.pathfinder.setGoal(new goals.GoalNear(cover.x, ARENA.y, cover.z, 2), true);
        bot.setControlState('sprint', true);
        if (dist < 25 && canAttack()) bot.attack(target.entity);
        break;
      }

      case 'maintain_distance':
      case 'kite_target':
      case 'control_space': {
        if (dist < 8) {
          const cover = findCover(bot.entity.position, target.entity.position);
          bot.pathfinder.setGoal(new goals.GoalNear(cover.x, ARENA.y, cover.z, 1), true);
          bot.setControlState('sprint', true);
        } else if (dist > 22) {
          bot.pathfinder.setGoal(new goals.GoalFollow(target.entity, 10), true);
        } else {
          bot.setControlState('left', true);
          setTimeout(() => {
            bot.setControlState('left', false);
            bot.setControlState('right', true);
            setTimeout(() => bot.setControlState('right', false), 400);
          }, 400);
        }
        if (canAttack()) bot.attack(target.entity);
        break;
      }

      case 'retreat':
      case 'dash_away': {
        bot.pvp.stop();
        const cover = findCover(bot.entity.position, target.entity.position);
        bot.pathfinder.setGoal(new goals.GoalNear(cover.x, ARENA.y, cover.z, 1), true);
        bot.setControlState('sprint', true);
        if (Math.random() < 0.15) {
          bot.setControlState('jump', true);
          setTimeout(() => bot.setControlState('jump', false), 200);
        }
        if (bot.health < 14 && bot.health > 0) {
          bot.chat('/effect give ' + config.username + ' minecraft:regeneration 2 0');
        }
        break;
      }

      case 'heal': {
        bot.pvp.stop();
        const healCover = findCover(bot.entity.position, target.entity.position);
        console.log(`[${config.id}] Healing at ${healCover.name} (${healCover.x}, ${healCover.z})`);
        bot.pathfinder.setGoal(new goals.GoalNear(healCover.x, ARENA.y, healCover.z, 1), true);
        bot.setControlState('sprint', true);
        break;
      }

      default:
        bot.clearControlStates();
        bot.pvp.stop();
        bot.pathfinder.stop();
        break;
    }
  }, 250);
}

function createBot(config) {
  return new Promise((resolve, reject) => {
    console.log(`[${config.id}] Connecting as ${config.username}...`);

    const bot = mineflayer.createBot({
      host: MC_HOST, port: MC_PORT,
      username: config.username,
      auth: 'offline', version: '1.21.4',
    });

    bot.loadPlugin(pathfinder);
    bot.loadPlugin(pvp);

    bot.once('spawn', () => {
      console.log(`[${config.id}] Spawned at ${bot.entity.position}`);

      const mcData = require('minecraft-data')(bot.version);
      const movements = new Movements(bot, mcData);
      movements.allowFreeMotion = true;
      movements.canDig = false;
      movements.canOpenDoors = false;
      bot.pathfinder.setMovements(movements);

      const entry = {
        bot, config, mcData,
        currentGoal: 'idle',
      };
      bots[config.id] = entry;

      runBehavior(entry);

      resolve(bot);
    });

    bot.on('error', err => {
      console.error(`[${config.id}] Error:`, err.message);
      reject(err);
    });
    bot.on('kicked', reason => console.log(`[${config.id}] Kicked:`, reason));
    bot.on('death', () => {
      console.log(`[${config.id}] Died — will re-equip on respawn`);
    });
    bot.on('spawn', () => {
      if (!bots[config.id]) return;
      console.log(`[${config.id}] Respawned — re-equipping`);
      setTimeout(() => {
        if (config.role === 'melee') {
          bot.chat('/give ' + config.username + ' iron_sword');
        } else {
          bot.chat('/give ' + config.username + ' bow');
          bot.chat('/give ' + config.username + ' arrow 64');
        }
        const rx = config.role === 'melee' ? 212 : 238;
        const rz = config.role === 'melee' ? 217 : 233;
        bot.chat('/tp ' + config.username + ' ' + rx + ' -59 ' + rz);
        bots[config.id].currentGoal = 'idle';
      }, 1000);
    });
  });
}

app.post('/bots/spawn', async (req, res) => {
  try {
    for (const config of BOT_CONFIGS) {
      if (!bots[config.id]) {
        await createBot(config);
        await new Promise(r => setTimeout(r, 1000));
      }
    }
    res.json({ status: 'ok', bots: Object.keys(bots) });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const GOAL_DISPLAY = {
  chase_target:      { text: 'CHASING',           color: 'red' },
  melee_attack:      { text: 'ATTACKING',         color: 'dark_red' },
  dash_attack:       { text: 'DASH ATTACK',       color: 'red' },
  flank_target:      { text: 'FLANKING',          color: 'gold' },
  ranged_attack:     { text: 'SHOOTING',          color: 'yellow' },
  find_vantage_point:{ text: 'REPOSITIONING',     color: 'aqua' },
  maintain_distance: { text: 'KEEPING DISTANCE',  color: 'aqua' },
  kite_target:       { text: 'KITING',            color: 'aqua' },
  control_space:     { text: 'CONTROLLING SPACE',  color: 'blue' },
  retreat:           { text: 'RETREATING',         color: 'green' },
  dash_away:         { text: 'DASHING AWAY',       color: 'green' },
  heal:              { text: 'HEALING',            color: 'light_purple' },
  idle:              { text: 'IDLE',               color: 'gray' },
};

let currentMode = 'GOAP';

app.post('/mode', (req, res) => {
  currentMode = (req.body.mode || 'goap').toUpperCase();
  console.log(`AI Mode set to: ${currentMode}`);
  res.json({ status: 'ok', mode: currentMode });
});

app.post('/bots/:id/goal', (req, res) => {
  const entry = bots[req.params.id];
  if (!entry) return res.status(404).json({ error: 'Bot not found' });

  const { goal } = req.body;
  const prev = entry.currentGoal;
  entry.currentGoal = goal || 'idle';

  if (goal !== prev) {
    console.log(`[${entry.config.id}] ${currentMode}: ${prev} → ${goal}`);
  }

  res.json({ status: 'ok', goal: entry.currentGoal });
});

app.get('/bots/:id/state', (req, res) => {
  const entry = bots[req.params.id];
  if (!entry) return res.status(404).json({ error: 'Bot not found' });
  const bot = entry.bot;
  const pos = bot.entity.position;

  res.json({
    id: entry.config.id,
    username: entry.config.username,
    role: entry.config.role,
    position: { x: pos.x, y: pos.y, z: pos.z },
    health: bot.health,
    food: bot.food,
    alive: bot.health > 0,
    yaw: bot.entity.yaw,
    onGround: bot.entity.onGround,
    currentGoal: entry.currentGoal,
  });
});

app.get('/state', (req, res) => {
  const gameState = { bots: {}, players: {}, timestamp: Date.now() };

  for (const [id, entry] of Object.entries(bots)) {
    const bot = entry.bot;
    const pos = bot.entity.position;
    gameState.bots[id] = {
      username: entry.config.username,
      role: entry.config.role,
      position: { x: pos.x, y: pos.y, z: pos.z },
      health: bot.health,
      food: bot.food,
      alive: bot.health > 0,
      yaw: bot.entity.yaw,
      onGround: bot.entity.onGround,
      currentGoal: entry.currentGoal,
    };

    for (const [name, player] of Object.entries(bot.players)) {
      if (BOT_CONFIGS.some(c => c.username === name)) continue;
      if (!player.entity) continue;
      const ppos = player.entity.position;
      gameState.players[name] = {
        position: { x: ppos.x, y: ppos.y, z: ppos.z },
        yaw: player.entity.yaw,
      };
    }
  }
  res.json(gameState);
});

app.post('/reset', (req, res) => {
  for (const [id, entry] of Object.entries(bots)) {
    entry.currentGoal = 'idle';
    entry.bot.pvp.stop();
    entry.bot.pathfinder.stop();
    entry.bot.clearControlStates();
  }
  res.json({ status: 'reset' });
});

app.listen(PORT, () => {
  console.log(`Bridge v2 running on http:
  console.log(`MC server: ${MC_HOST}:${MC_PORT}`);
  console.log('');
  console.log('Python sends GOAP goals → JS executes combat natively');
});
