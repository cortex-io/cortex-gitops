/**
 * Configuration for YouTube Ingestion Service
 */

export const config = {
  server: {
    port: parseInt(process.env.PORT) || 8080
  },
  redis: {
    host: process.env.REDIS_HOST || 'localhost',
    port: parseInt(process.env.REDIS_PORT) || 6379,
    enabled: process.env.REDIS_ENABLED === 'true'
  },
  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY || '',
    model: 'claude-3-5-sonnet-20241022'
  },
  storage: {
    transcriptsDir: process.env.TRANSCRIPTS_DIR || '/data/transcripts',
    knowledgeDir: process.env.KNOWLEDGE_DIR || '/data/knowledge',
    cacheDir: process.env.CACHE_DIR || '/data/cache'
  },
  youtube: {
    apiKey: process.env.YOUTUBE_API_KEY || ''
  }
};

export default config;
