#!/usr/bin/env node
// Simple PNG->SVG wrapper (embeds PNG as base64 in an <image> tag)
// Usage: node scripts/png-to-svg.js [inputPng] [outputSvg]
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const baseDir = path.resolve(__dirname, '..'); // client/
const inArg = process.argv[2];
const outArg = process.argv[3];

const defaultIn = path.resolve(baseDir, 'public', 'logo-epfl.png');
const defaultOut = path.resolve(baseDir, 'public', 'logo.svg');

const inputPng = inArg ? path.resolve(baseDir, inArg) : defaultIn;
const outputSvg = outArg ? path.resolve(baseDir, outArg) : defaultOut;

if (!fs.existsSync(inputPng)) {
  console.error(`Input PNG not found: ${inputPng}`);
  process.exit(1);
}

const pngBuffer = fs.readFileSync(inputPng);
const base64 = pngBuffer.toString('base64');

// Basic size guess: try to read image size via data URL in browser later; for the file,
// set viewBox and preserveAspectRatio so it scales nicely in UI and as favicon.
const svgContent = `<?xml version="1.0" encoding="UTF-8"?>\n` +
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" preserveAspectRatio="xMidYMid meet">\n` +
  `  <image href="data:image/png;base64,${base64}" x="0" y="0" width="512" height="512"/>\n` +
  `</svg>\n`;

fs.writeFileSync(outputSvg, svgContent);
console.log(`Wrote SVG: ${outputSvg}`);
