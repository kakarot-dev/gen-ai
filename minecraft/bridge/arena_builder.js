/**
 * Builds a CoD-style combat arena in Minecraft.
 * Bigger, tactical layout with cover, buildings, corridors.
 *
 * Usage: node arena_builder.js
 */
const mineflayer = require('mineflayer');

const HOST = process.env.MC_HOST || 'localhost';
const PORT = parseInt(process.env.MC_PORT || '25565');

const bot = mineflayer.createBot({
  host: HOST, port: PORT,
  username: 'ArenaBuilder',
  auth: 'offline',
  version: '1.21.4',
});

// Arena config — bigger, CoD style
const W = 50, H = 50;
const OX = -25, OZ = -25; // origin (centered)
const FY = -60; // floor Y

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function fill(x1, y1, z1, x2, y2, z2, block) {
  bot.chat(`/fill ${OX+x1} ${FY+y1} ${OZ+z1} ${OX+x2} ${FY+y2} ${OZ+z2} ${block}`);
  await sleep(150);
}

async function setblock(x, y, z, block) {
  bot.chat(`/setblock ${OX+x} ${FY+y} ${OZ+z} ${block}`);
  await sleep(30);
}

bot.once('spawn', async () => {
  console.log('ArenaBuilder connected. Building CoD-style arena...');
  await sleep(1000);

  // ── Game rules ──
  const rules = [
    '/gamerule doDaylightCycle false', '/gamerule doWeatherCycle false',
    '/gamerule keepInventory true', '/gamerule doMobSpawning false',
    '/gamerule doFireTick false', '/gamerule naturalRegeneration true',
    '/time set 6000', '/weather clear',
  ];
  for (const r of rules) { bot.chat(r); await sleep(100); }

  // ── Clear the area ──
  console.log('Clearing area...');
  for (let y = 0; y <= 8; y++) {
    await fill(0, y, 0, W-1, y, H-1, 'air');
  }

  // ── Floor ──
  console.log('Building floor...');
  await fill(0, 0, 0, W-1, 0, H-1, 'gray_concrete');
  // Floor details — dirt patches, gravel paths
  await fill(10, 0, 10, 14, 0, 14, 'cracked_stone_bricks');
  await fill(35, 0, 35, 39, 0, 39, 'cracked_stone_bricks');
  await fill(22, 0, 0, 27, 0, H-1, 'gravel'); // center road
  await fill(0, 0, 22, W-1, 0, 27, 'gravel'); // cross road
  await fill(23, 0, 23, 26, 0, 26, 'smooth_stone'); // center pad

  // ── Outer walls (tall, concrete) ──
  console.log('Building perimeter walls...');
  for (let y = 1; y <= 6; y++) {
    await fill(0, y, 0, W-1, y, 0, 'gray_concrete');      // north
    await fill(0, y, H-1, W-1, y, H-1, 'gray_concrete');  // south
    await fill(0, y, 0, 0, y, H-1, 'gray_concrete');      // west
    await fill(W-1, y, 0, W-1, y, H-1, 'gray_concrete');  // east
  }
  // Wall top trim
  await fill(0, 7, 0, W-1, 7, 0, 'stone_brick_slab');
  await fill(0, 7, H-1, W-1, 7, H-1, 'stone_brick_slab');
  await fill(0, 7, 0, 0, 7, H-1, 'stone_brick_slab');
  await fill(W-1, 7, 0, W-1, 7, H-1, 'stone_brick_slab');

  // ── Building A: NW corner — small house/bunker ──
  console.log('Building structures...');
  // Walls
  for (let y = 1; y <= 4; y++) {
    await fill(3, y, 3, 10, y, 3, 'stone_bricks');     // front
    await fill(3, y, 10, 10, y, 10, 'stone_bricks');   // back
    await fill(3, y, 3, 3, y, 10, 'stone_bricks');     // left
    await fill(10, y, 3, 10, y, 10, 'stone_bricks');   // right
  }
  await fill(10, 5, 3, 10, 5, 10, 'stone_brick_slab'); // roof edge
  await fill(3, 5, 3, 10, 5, 10, 'dark_oak_planks');   // roof
  // Doorways
  await fill(6, 1, 3, 7, 3, 3, 'air');   // front door
  await fill(10, 1, 6, 10, 3, 7, 'air');  // side door
  // Windows
  await fill(4, 3, 3, 5, 3, 3, 'glass_pane');
  await fill(8, 3, 3, 9, 3, 3, 'glass_pane');
  await fill(3, 3, 5, 3, 3, 6, 'glass_pane');

  // ── Building B: SE corner — warehouse ──
  for (let y = 1; y <= 4; y++) {
    await fill(38, y, 38, 47, y, 38, 'stone_bricks');
    await fill(38, y, 47, 47, y, 47, 'stone_bricks');
    await fill(38, y, 38, 38, y, 47, 'stone_bricks');
    await fill(47, y, 38, 47, y, 47, 'stone_bricks');
  }
  await fill(38, 5, 38, 47, 5, 47, 'dark_oak_planks');
  await fill(42, 1, 38, 43, 3, 38, 'air');  // front door
  await fill(38, 1, 42, 38, 3, 43, 'air');  // side door
  await fill(39, 3, 38, 41, 3, 38, 'glass_pane');
  await fill(44, 3, 38, 46, 3, 38, 'glass_pane');

  // ── Building C: NE — sniper tower ──
  for (let y = 1; y <= 6; y++) {
    await fill(40, y, 3, 45, y, 3, 'deepslate_bricks');
    await fill(40, y, 8, 45, y, 8, 'deepslate_bricks');
    await fill(40, y, 3, 40, y, 8, 'deepslate_bricks');
    await fill(45, y, 3, 45, y, 8, 'deepslate_bricks');
  }
  await fill(40, 7, 3, 45, 7, 8, 'deepslate_brick_slab');
  await fill(42, 1, 8, 43, 3, 8, 'air'); // door
  // Stairs inside
  for (let i = 0; i < 4; i++) {
    await setblock(41, 1+i, 4+i, 'oak_stairs[facing=south]');
    await setblock(44, 1+i, 4+i, 'oak_stairs[facing=south]');
  }
  // Sniper windows at top
  await fill(41, 6, 3, 44, 6, 3, 'air');
  await fill(41, 5, 3, 44, 5, 3, 'stone_brick_wall');

  // ── Building D: SW — garage ──
  for (let y = 1; y <= 3; y++) {
    await fill(3, y, 40, 12, y, 40, 'iron_block');
    await fill(3, y, 47, 12, y, 47, 'iron_block');
    await fill(3, y, 40, 3, y, 47, 'iron_block');
    await fill(12, y, 40, 12, y, 47, 'iron_block');
  }
  await fill(3, 4, 40, 12, 4, 47, 'iron_block');
  await fill(5, 1, 40, 10, 3, 40, 'air');  // garage opening
  await fill(12, 1, 43, 12, 2, 45, 'air'); // side door

  // ── Center structures — crates & half walls ──
  console.log('Building cover and obstacles...');

  // Crate clusters (scattered around center)
  const cratePositions = [
    [20,20,2,2], [28,20,2,2], [24,15,1,1], [24,33,1,1],
    [18,25,2,1], [30,24,1,2], [15,30,1,1], [33,18,1,1],
    [22,28,1,1], [27,21,1,1],
  ];
  for (const [cx, cz, cw, ch] of cratePositions) {
    const h = Math.random() > 0.5 ? 2 : 1;
    for (let y = 1; y <= h; y++) {
      await fill(cx, y, cz, cx+cw, y, cz+ch, 'barrel');
    }
  }

  // Half walls (concrete cover)
  const halfWalls = [
    [16, 12, 16, 16, 'x'], // horizontal
    [32, 12, 32, 16, 'x'],
    [16, 33, 16, 37, 'x'],
    [32, 33, 32, 37, 'x'],
    [12, 22, 12, 27, 'x'], // sides
    [37, 22, 37, 27, 'x'],
    [20, 8, 29, 8, 'z'],   // north mid
    [20, 41, 29, 41, 'z'], // south mid
  ];
  for (const [x1, z1, x2, z2, dir] of halfWalls) {
    for (let y = 1; y <= 2; y++) {
      await fill(x1, y, z1, x2, y, z2, 'light_gray_concrete');
    }
  }

  // Sandbag lines (low cover)
  const sandbags = [
    [18, 18, 21, 18], [28, 18, 31, 18],
    [18, 31, 21, 31], [28, 31, 31, 31],
  ];
  for (const [x1, z1, x2, z2] of sandbags) {
    await fill(x1, 1, z1, x2, 1, z2, 'sand');
  }

  // ── Lava hazard pit (center) ──
  console.log('Adding lava hazard...');
  await fill(23, -1, 23, 26, -1, 26, 'lava');
  await fill(23, 0, 23, 26, 0, 26, 'air');
  // Warning border
  await fill(22, 0, 22, 27, 0, 22, 'red_concrete');
  await fill(22, 0, 27, 27, 0, 27, 'red_concrete');
  await fill(22, 0, 22, 22, 0, 27, 'red_concrete');
  await fill(27, 0, 22, 27, 0, 27, 'red_concrete');

  // ── Lighting (glowstone in walls/ceiling) ──
  console.log('Adding lights...');
  const lights = [
    [6,4,6], [6,4,8], [42,4,42], [42,4,45],
    [24,1,5], [24,1,44], [5,1,24], [44,1,24],
    [15,3,15], [34,3,15], [15,3,34], [34,3,34],
    [24,1,24], // center
  ];
  for (const [x,y,z] of lights) {
    await setblock(x, y, z, 'lantern');
  }
  // Wall torches around perimeter
  for (let i = 5; i < W; i += 8) {
    await setblock(i, 3, 1, 'wall_torch[facing=south]');
    await setblock(i, 3, H-2, 'wall_torch[facing=north]');
  }
  for (let i = 5; i < H; i += 8) {
    await setblock(1, 3, i, 'wall_torch[facing=east]');
    await setblock(W-2, 3, i, 'wall_torch[facing=west]');
  }

  // ── Spawn point ──
  const sx = OX + 25, sz = OZ + 25;
  bot.chat(`/setworldspawn ${sx} ${FY + 1} ${sz}`);
  await sleep(200);

  console.log('');
  console.log('=== ARENA BUILT ===');
  console.log(`Size: ${W}x${H} blocks`);
  console.log(`Center: (${sx}, ${FY+1}, ${sz})`);
  console.log('Features:');
  console.log('  - 4 buildings (bunker, warehouse, sniper tower, garage)');
  console.log('  - Crate cover clusters');
  console.log('  - Half walls and sandbag lines');
  console.log('  - Lava hazard pit (center)');
  console.log('  - Gravel cross-roads');
  console.log('  - Torches and lanterns');
  console.log('');

  bot.quit();
  setTimeout(() => process.exit(0), 1000);
});

bot.on('error', err => {
  console.error('Error:', err.message);
  process.exit(1);
});
