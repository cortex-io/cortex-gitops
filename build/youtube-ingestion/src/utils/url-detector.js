/**
 * YouTube URL Detector
 * Detects and extracts YouTube video IDs from text
 */

export class URLDetector {
  constructor() {
    // Regex patterns for YouTube URLs
    this.patterns = [
      /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/g,
      /(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})/g,
      /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/g
    ];
  }

  /**
   * Detect YouTube URLs in text
   * @param {string} text
   * @returns {Array<{url: string, videoId: string}>}
   */
  detect(text) {
    const results = [];
    const seen = new Set();

    for (const pattern of this.patterns) {
      const matches = text.matchAll(pattern);

      for (const match of matches) {
        const videoId = match[1];

        if (!seen.has(videoId)) {
          seen.add(videoId);
          results.push({
            url: match[0],
            videoId
          });
        }
      }
    }

    return results;
  }
}

export default URLDetector;
