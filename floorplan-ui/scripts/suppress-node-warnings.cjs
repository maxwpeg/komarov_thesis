const originalEmitWarning = process.emitWarning.bind(process);

function getWarningCode(args) {
  const firstArg = args[0];
  if (typeof firstArg === 'object' && firstArg !== null) {
    return firstArg.code;
  }
  return args[1];
}

function getWarningMessage(warning) {
  if (typeof warning === 'string') {
    return warning;
  }
  return warning && typeof warning.message === 'string' ? warning.message : '';
}

process.emitWarning = (warning, ...args) => {
  const code = getWarningCode(args);
  const message = getWarningMessage(warning);

  if (code === 'DEP0040' || message.includes('punycode')) {
    return;
  }

  return originalEmitWarning(warning, ...args);
};
