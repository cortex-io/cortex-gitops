/**
 * YouTube Ingestion Service - Main Entry Point
 * HTTP server that exposes endpoints for video ingestion and knowledge retrieval
 */

import express from 'express';
import { createClient } from 'redis';
import { IngestionService } from './ingestion-service.js';
import { config } from './config.js';

const app = express();
app.use(express.json());

// Initialize Redis client
const redisClient = createClient({
  url: `redis://${config.redis.host}:${config.redis.port}`
});

redisClient.on('error', (err) => console.error('[Redis] Error:', err));
redisClient.on('connect', () => console.log('[Redis] Connected'));

// Initialize ingestion service
const ingestionService = new IngestionService(redisClient);

/**
 * Health check endpoint
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'youtube-ingestion',
    redis: redisClient.isOpen ? 'connected' : 'disconnected'
  });
});

/**
 * Process a message for YouTube URLs
 * POST /process
 * Body: { message: "check out this video https://www.youtube.com/watch?v=abc123" }
 */
app.post('/process', async (req, res) => {
  try {
    const { message } = req.body;

    if (!message) {
      return res.status(400).json({ error: 'message field is required' });
    }

    const result = await ingestionService.processMessage(message);

    res.json(result);
  } catch (error) {
    console.error('[API] Process failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Ingest a specific video by ID
 * POST /ingest
 * Body: { videoId: "abc123" }
 */
app.post('/ingest', async (req, res) => {
  try {
    const { videoId } = req.body;

    if (!videoId) {
      return res.status(400).json({ error: 'videoId field is required' });
    }

    const knowledge = await ingestionService.ingestVideo(videoId);

    res.json({
      status: 'success',
      videoId,
      knowledge
    });
  } catch (error) {
    console.error('[API] Ingest failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get ingestion statistics
 * GET /stats
 */
app.get('/stats', async (req, res) => {
  try {
    const stats = await ingestionService.getStats();
    res.json(stats);
  } catch (error) {
    console.error('[API] Stats failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Search the knowledge base
 * POST /search
 * Body: { query: { ... } }
 */
app.post('/search', async (req, res) => {
  try {
    const { query } = req.body;

    if (!query) {
      return res.status(400).json({ error: 'query field is required' });
    }

    const results = await ingestionService.search(query);
    res.json({ results });
  } catch (error) {
    console.error('[API] Search failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * List all ingested videos
 * GET /videos?limit=100
 */
app.get('/videos', async (req, res) => {
  try {
    const limit = parseInt(req.query.limit) || 100;
    const videos = await ingestionService.listAll(limit);
    res.json({ videos });
  } catch (error) {
    console.error('[API] List failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Get pending improvements
 * GET /improvements
 */
app.get('/improvements', async (req, res) => {
  try {
    const improvements = await ingestionService.getPendingImprovements();
    res.json({ improvements });
  } catch (error) {
    console.error('[API] Get improvements failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Perform meta-review
 * POST /meta-review
 * Body: { options: { ... } }
 */
app.post('/meta-review', async (req, res) => {
  try {
    const { options = {} } = req.body;
    const review = await ingestionService.performMetaReview(options);
    res.json(review);
  } catch (error) {
    console.error('[API] Meta-review failed:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * Start the server
 */
async function start() {
  try {
    // Connect to Redis
    await redisClient.connect();

    // Initialize ingestion service
    await ingestionService.initialize();

    // Start HTTP server
    const port = config.server.port || 8080;
    app.listen(port, '0.0.0.0', () => {
      console.log(`[Server] YouTube Ingestion Service listening on port ${port}`);
      console.log(`[Server] Health check: http://localhost:${port}/health`);
    });
  } catch (error) {
    console.error('[Server] Failed to start:', error);
    process.exit(1);
  }
}

// Handle graceful shutdown
process.on('SIGTERM', async () => {
  console.log('[Server] SIGTERM received, shutting down gracefully...');
  await redisClient.quit();
  process.exit(0);
});

process.on('SIGINT', async () => {
  console.log('[Server] SIGINT received, shutting down gracefully...');
  await redisClient.quit();
  process.exit(0);
});

// Start the service
start().catch((error) => {
  console.error('[Server] Fatal error:', error);
  process.exit(1);
});
