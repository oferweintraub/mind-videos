#!/usr/bin/env node
/**
 * Kokoro TTS Bridge — generates WAV from text.
 *
 * Usage:
 *   node scripts/kokoro_tts.js --text "Hello world" --voice af_heart --output output/audio.wav
 *
 * Note: Outputs WAV only. Use ffmpeg externally to convert to MP3.
 * The phonemizer wasm module may crash on exit — this is harmless
 * as long as the WAV file was written successfully.
 *
 * Requires: kokoro-js (loaded from product-videos/node_modules)
 */

import { createRequire } from "module";
import { mkdirSync, existsSync } from "fs";
import { dirname, resolve } from "path";
import { parseArgs } from "util";

// Load kokoro-js from product-videos/node_modules
const require = createRequire("/Users/oferweintraub/OferW/product-videos/node_modules/kokoro-js/");
const { KokoroTTS } = require("kokoro-js");

const { values } = parseArgs({
  options: {
    text: { type: "string", short: "t" },
    voice: { type: "string", short: "v", default: "af_heart" },
    output: { type: "string", short: "o" },
  },
});

if (!values.text || !values.output) {
  console.error("Usage: node kokoro_tts.js --text 'text' --voice af_heart --output out.wav");
  process.exit(1);
}

const outputPath = resolve(values.output);
const outputDir = dirname(outputPath);
if (!existsSync(outputDir)) {
  mkdirSync(outputDir, { recursive: true });
}

console.log(`Loading Kokoro model...`);
const tts = await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", {
  dtype: "q8",
  device: "cpu",
});

console.log(`Generating speech (voice: ${values.voice})...`);
console.log(`Text: "${values.text.substring(0, 80)}${values.text.length > 80 ? '...' : ''}"`);

const audio = await tts.generate(values.text, { voice: values.voice });

audio.save(outputPath);
console.log(`SAVED: ${outputPath}`);
