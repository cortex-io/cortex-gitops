/**
 * Transcript Extractor
 * Extracts video transcripts using youtube-transcript-api
 */

import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class TranscriptExtractor {
  constructor() {
    this.pythonScript = path.join(__dirname, '../../extract_transcript.py');
  }

  /**
   * Extract transcript for a video
   * @param {string} videoId
   * @param {string} language
   * @returns {Promise<Object>}
   */
  async extract(videoId, language = 'en') {
    console.log(`[TranscriptExtractor] Extracting transcript for ${videoId}`);

    return new Promise((resolve, reject) => {
      const python = spawn('python3', [this.pythonScript, videoId, language]);

      let stdout = '';
      let stderr = '';

      python.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      python.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      python.on('close', (code) => {
        if (code !== 0) {
          console.error(`[TranscriptExtractor] Python script failed: ${stderr}`);
          return reject(new Error(`Transcript extraction failed: ${stderr}`));
        }

        try {
          const result = JSON.parse(stdout);

          if (!result.success) {
            return reject(new Error(result.error || 'Unknown error'));
          }

          // Transform to expected format
          const transcript = {
            videoId,
            language: result.language,
            segments: result.segments,
            rawText: result.segments.map(s => s.text).join(' '),
            wordCount: result.segments.map(s => s.text.split(/\s+/).length).reduce((a, b) => a + b, 0),
            hasTimestamps: true,
            extractedAt: new Date().toISOString()
          };

          console.log(`[TranscriptExtractor] Extracted ${transcript.wordCount} words`);
          resolve(transcript);
        } catch (error) {
          console.error(`[TranscriptExtractor] Parse error: ${error.message}`);
          reject(new Error(`Failed to parse transcript: ${error.message}`));
        }
      });
    });
  }
}

export default TranscriptExtractor;
