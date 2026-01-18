/**
 * Metadata Extractor
 * Extracts video metadata from YouTube
 */

import axios from 'axios';

export class MetadataExtractor {
  constructor() {
    // Using oembed API (no key required)
    this.oembedUrl = 'https://www.youtube.com/oembed';
  }

  /**
   * Extract metadata for a video
   * @param {string} videoId
   * @returns {Promise<Object>}
   */
  async extract(videoId) {
    console.log(`[MetadataExtractor] Extracting metadata for ${videoId}`);

    try {
      // Use oEmbed endpoint (no API key needed)
      const response = await axios.get(this.oembedUrl, {
        params: {
          url: `https://www.youtube.com/watch?v=${videoId}`,
          format: 'json'
        }
      });

      const data = response.data;

      const metadata = {
        videoId,
        title: data.title || 'Unknown Title',
        channelName: data.author_name || 'Unknown Channel',
        description: '', // oEmbed doesn't provide description
        duration: 0, // oEmbed doesn't provide duration
        uploadDate: '', // oEmbed doesn't provide upload date
        thumbnailUrl: data.thumbnail_url || '',
        extractedAt: new Date().toISOString()
      };

      console.log(`[MetadataExtractor] Extracted metadata for: ${metadata.title}`);
      return metadata;
    } catch (error) {
      console.error(`[MetadataExtractor] Failed: ${error.message}`);

      // Return minimal metadata
      return {
        videoId,
        title: `Video ${videoId}`,
        channelName: 'Unknown',
        description: '',
        duration: 0,
        uploadDate: '',
        thumbnailUrl: '',
        extractedAt: new Date().toISOString(),
        error: error.message
      };
    }
  }
}

export default MetadataExtractor;
