const { spawn } = require('child_process');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';
const npmCmd = isWin ? 'npm.cmd' : 'npm';
const pythonCmd = process.env.PYTHON || (isWin ? 'python' : 'python3');

console.log('===============================================================');
console.log('🎮 AI GAMING COPILOT — UNIFIED DEVELOPMENT ENVIRONMENT');
console.log('===============================================================');
console.log('• Backend API:              http://localhost:5000/api');
console.log('• Frontend Dev (Vite HMR):   http://localhost:5173');
console.log('• Python Second Brain (HUD): http://localhost:8000');
console.log('• Combined Single Port:      http://localhost:5000 (after build)');
console.log('===============================================================\n');

function runService(name, colorCode, cwd, command, args) {
  const child = spawn(command, args, {
    cwd,
    stdio: 'pipe',
    shell: isWin
  });

  child.stdout.on('data', (data) => {
    process.stdout.write(`\x1b[${colorCode}m[${name}]\x1b[0m ${data}`);
  });

  child.stderr.on('data', (data) => {
    process.stderr.write(`\x1b[${colorCode}m[${name}]\x1b[0m ${data}`);
  });

  child.on('error', (err) => {
    console.error(`\x1b[31m[${name}] Failed to start: ${err.message}\x1b[0m`);
  });

  child.on('close', (code) => {
    console.log(`[${name}] Process exited with code ${code}`);
  });

  return child;
}

const backend = runService('BACKEND', '36', path.join(rootDir, 'backend'), npmCmd, ['run', 'dev']);
const frontend = runService('FRONTEND', '35', path.join(rootDir, 'frontend'), npmCmd, ['run', 'dev']);
const brain = runService('SECOND-BRAIN', '33', rootDir, pythonCmd, ['run.py']);

function cleanup() {
  try { backend.kill(); } catch {}
  try { frontend.kill(); } catch {}
  try { brain.kill(); } catch {}
  process.exit(0);
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

