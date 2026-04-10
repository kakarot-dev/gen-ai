const mineflayer = require('mineflayer');

const bot = mineflayer.createBot({
  host: 'localhost', port: 25565,
  username: 'GameSetup', auth: 'offline', version: '1.21.4',
});

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

bot.on('message', msg => console.log('>', msg.toString()));

bot.once('spawn', async () => {
  console.log('Setting up game...');
  await sleep(3000);

  const rules = [
    '/gamerule doDaylightCycle false',
    '/gamerule doWeatherCycle false',
    '/gamerule keepInventory true',
    '/gamerule doMobSpawning false',
    '/gamerule doFireTick false',
    '/gamerule naturalRegeneration true',
    '/difficulty normal',
    '/time set 6000',
    '/weather clear',
    '/difficulty normal',
  ];
  for (const r of rules) { bot.chat(r); await sleep(80); }
  console.log('Game rules set');

  bot.chat('/clear axelbolston');
  bot.chat('/gamemode survival axelbolston');
  await sleep(500);

  bot.chat('/give axelbolston diamond_sword[minecraft:enchantments={levels:{"minecraft:sharpness":5,"minecraft:fire_aspect":2,"minecraft:knockback":2}}] 1');
  await sleep(150);
  bot.chat('/give axelbolston bow[minecraft:enchantments={levels:{"minecraft:power":5,"minecraft:flame":1,"minecraft:infinity":1}}] 1');
  await sleep(150);
  bot.chat('/give axelbolston crossbow[minecraft:enchantments={levels:{"minecraft:quick_charge":3,"minecraft:multishot":1}}] 1');
  await sleep(150);
  bot.chat('/give axelbolston shield 1');
  await sleep(150);
  bot.chat('/give axelbolston golden_apple 16');
  await sleep(150);
  bot.chat('/give axelbolston ender_pearl 8');
  await sleep(150);
  bot.chat('/give axelbolston splash_potion[minecraft:potion_contents={potion:"minecraft:strong_healing"}] 5');
  await sleep(150);
  bot.chat('/give axelbolston arrow 64');
  await sleep(150);
  bot.chat('/give axelbolston cooked_beef 16');
  await sleep(150);

  bot.chat('/give axelbolston diamond_helmet[minecraft:enchantments={levels:{"minecraft:protection":4}}] 1');
  bot.chat('/give axelbolston diamond_chestplate[minecraft:enchantments={levels:{"minecraft:protection":4}}] 1');
  bot.chat('/give axelbolston diamond_leggings[minecraft:enchantments={levels:{"minecraft:protection":4}}] 1');
  bot.chat('/give axelbolston diamond_boots[minecraft:enchantments={levels:{"minecraft:protection":4}}] 1');
  await sleep(300);

  bot.chat('/effect give axelbolston instant_health 1 100');
  bot.chat('/effect give axelbolston saturation 9999 1 true');
  await sleep(300);
  console.log('Player maxed out');

  bot.chat('/clear Zombie_NPC');
  await sleep(200);
  bot.chat('/give Zombie_NPC iron_sword[minecraft:enchantments={levels:{"minecraft:sharpness":3}}] 1');
  bot.chat('/give Zombie_NPC iron_chestplate 1');
  bot.chat('/give Zombie_NPC iron_leggings 1');
  bot.chat('/give Zombie_NPC iron_boots 1');
  bot.chat('/effect give Zombie_NPC instant_health 1 100');
  await sleep(200);

  bot.chat('/clear Skeleton_NPC');
  await sleep(200);
  bot.chat('/give Skeleton_NPC bow[minecraft:enchantments={levels:{"minecraft:power":3}}] 1');
  bot.chat('/give Skeleton_NPC arrow 128');
  bot.chat('/give Skeleton_NPC leather_chestplate 1');
  bot.chat('/give Skeleton_NPC leather_leggings 1');
  bot.chat('/effect give Skeleton_NPC instant_health 1 100');
  await sleep(200);
  console.log('NPCs equipped');

  bot.chat('/tp axelbolston 225 -59 225');
  bot.chat('/tp Zombie_NPC 212 -59 217');
  bot.chat('/tp Skeleton_NPC 238 -59 233');
  await sleep(500);

  bot.chat('/title axelbolston title {"text":"ARENA COMBAT","color":"red","bold":true}');
  await sleep(100);
  bot.chat('/title axelbolston subtitle {"text":"GOAP+RL vs Player — FIGHT!","color":"gold"}');
  await sleep(1000);

  console.log('');
  console.log('=== GAME READY ===');
  console.log('');
  console.log('Hotbar:');
  console.log('  1. Diamond Sword (Sharp V, Fire II, KB II)');
  console.log('  2. Bow (Power V, Flame, Infinity)');
  console.log('  3. Crossbow (Quick Charge III, Multishot)');
  console.log('  4. Shield');
  console.log('  5. Golden Apples x16');
  console.log('  6. Ender Pearls x8');
  console.log('  7. Splash Healing x5');
  console.log('  8. Arrow x64');
  console.log('  9. Steak x16');
  console.log('  + Full Protection IV Diamond Armor');
  console.log('');
  console.log('NPCs:');
  console.log('  Zombie: Iron sword (Sharp III) + iron armor');
  console.log('  Skeleton: Bow (Power III) + leather armor');
  console.log('');
  console.log('FIGHT!');

  bot.quit();
  setTimeout(() => process.exit(0), 1000);
});

bot.on('error', err => { console.error('Error:', err.message); process.exit(1); });
