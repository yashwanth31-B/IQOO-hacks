const { spawn } = require('child_process');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const isWin = process.platform === 'win32';
const npmCmd = isWin ? 'npm.cmd' : 'npm';

console.log('===============================================================');
console.log('🎮 AI GAMING COPILOT — COMBINED DEVELOPMENT SERVER');
console.log('===============================================================');
console.log('• Backend API:              http://localhost:5000/api');
console.log('• Frontend Dev (Vite HMR):   http://localhost:5173');
console.log('• Combined Single Port:      http://localhost:5000 (after build)');
console.log('===============================================================\n');

function runService(name, colorCode, subDir, args) {
  const child = spawn(npmCmd, args, {
    cwd: path.join(rootDir, subDir),
    stdio: 'pipe',
    shell: isWin
  });

  child.stdout.on('data', (data) => {
    process.stdout.write(`\x1b[${colorCode}m[${name}]\x1b[0m ${data}`);
  });

  child.stderr.on('data', (data) => {
    process.stderr.write(`\x1b[${colorCode}m[${name}]\x1b[0m ${data}`);
  });

  child.on('close', (code) => {
    console.log(`[${name}] process exited with code ${code}`);
  });

  return child;
}

const backend = runService('BACKEND', '36', 'backend', ['run', 'dev']);
const frontend = runService('FRONTEND', '35', 'frontend', ['run', 'dev']);

process.on('SIGINT', () => {
  backend.kill();
  frontend.kill();
  process.exit(0);
});
