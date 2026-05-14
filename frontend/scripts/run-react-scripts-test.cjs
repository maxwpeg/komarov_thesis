const path = require('path');
const { spawn } = require('child_process');

const suppressorPath = path.resolve(__dirname, 'suppress-node-warnings.cjs');
const reactScriptsPath = path.resolve(__dirname, '..', 'node_modules', 'react-scripts', 'bin', 'react-scripts.js');
const inheritedNodeOptions = process.env.NODE_OPTIONS ? `${process.env.NODE_OPTIONS} ` : '';

const env = {
  ...process.env,
  NODE_OPTIONS: `${inheritedNodeOptions}--disable-warning=DEP0040 --require=${suppressorPath}`.trim(),
};

const child = spawn(process.execPath, [reactScriptsPath, 'test', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
