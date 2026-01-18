/**
 * Learning Tracker Service
 * Tracks what the system learns from YouTube videos and makes it queryable via chat
 */

import Redis from 'ioredis';

export class LearningTracker {
  constructor(redis) {
    this.redis = redis;
  }

  /**
   * Record a learning from processed video
   */
  async recordLearning(videoId, learning) {
    const timestamp = new Date().toISOString();
    const date = new Date().toISOString().split('T')[0];
    const now = Date.now();

    // Store individual learning
    const learningId = 'learning:' + videoId + ':' + now;
    await this.redis.hset(learningId, {
      videoId,
      title: learning.title || '',
      summary: learning.summary || '',
      keyTakeaways: JSON.stringify(learning.keyTakeaways || []),
      category: learning.category || 'general',
      implementationStatus: learning.implementationStatus || 'pending',
      implementationDetails: learning.implementationDetails || '',
      timestamp,
      date
    });

    // Add to daily learnings sorted set
    await this.redis.zadd('learnings:daily:' + date, now, learningId);

    // Add to all learnings
    await this.redis.zadd('learnings:all', now, learningId);

    // Update category index
    await this.redis.sadd('learnings:category:' + learning.category, learningId);

    // Update video index
    await this.redis.sadd('learnings:video:' + videoId, learningId);

    console.log('[LearningTracker] Learning recorded:', learningId);
  }

  /**
   * Get learnings for today
   */
  async getTodaysLearnings() {
    const today = new Date().toISOString().split('T')[0];
    const learningIds = await this.redis.zrange('learnings:daily:' + today, 0, -1);

    const learnings = [];
    for (const id of learningIds) {
      const learning = await this.redis.hgetall(id);
      if (learning && learning.videoId) {
        learning.keyTakeaways = JSON.parse(learning.keyTakeaways || '[]');
        learnings.push(learning);
      }
    }

    return learnings;
  }

  /**
   * Get learnings for a specific date
   */
  async getLearningsForDate(date) {
    const learningIds = await this.redis.zrange('learnings:daily:' + date, 0, -1);

    const learnings = [];
    for (const id of learningIds) {
      const learning = await this.redis.hgetall(id);
      if (learning && learning.videoId) {
        learning.keyTakeaways = JSON.parse(learning.keyTakeaways || '[]');
        learnings.push(learning);
      }
    }

    return learnings;
  }

  /**
   * Get recent learnings (last N days)
   */
  async getRecentLearnings(days = 7) {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const learnings = [];
    for (let d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
      const date = d.toISOString().split('T')[0];
      const dailyLearnings = await this.getLearningsForDate(date);
      learnings.push(...dailyLearnings);
    }

    return learnings;
  }

  /**
   * Get learning statistics
   */
  async getStats() {
    const today = new Date().toISOString().split('T')[0];
    const todayCount = await this.redis.zcard('learnings:daily:' + today);
    const totalCount = await this.redis.zcard('learnings:all');

    // Get category counts
    const categories = ['kubernetes', 'security', 'ai', 'networking', 'devops', 'monitoring'];
    const categoryStats = {};
    for (const cat of categories) {
      categoryStats[cat] = await this.redis.scard('learnings:category:' + cat);
    }

    return {
      today: todayCount,
      total: totalCount,
      byCategory: categoryStats
    };
  }

  /**
   * Format learnings for chat response
   */
  formatForChat(learnings) {
    if (!learnings || learnings.length === 0) {
      return "I haven't learned anything new today yet. The learning pipeline is processing videos in the queue!";
    }

    let response = '📚 Here\'s what I learned today:\n\n';

    learnings.forEach((learning, index) => {
      response += '### ' + (index + 1) + '. ' + learning.title + '\n\n';
      
      if (learning.summary) {
        response += '**Summary:** ' + learning.summary + '\n\n';
      }

      if (learning.keyTakeaways && learning.keyTakeaways.length > 0) {
        response += '**Key Takeaways:**\n';
        learning.keyTakeaways.forEach(takeaway => {
          response += '- ' + takeaway + '\n';
        });
        response += '\n';
      }

      if (learning.implementationStatus) {
        response += '**Status:** ' + learning.implementationStatus + '\n';
        if (learning.implementationDetails) {
          response += '**Implementation:** ' + learning.implementationDetails + '\n';
        }
        response += '\n';
      }

      response += '---\n\n';
    });

    return response;
  }

  /**
   * Search learnings by query
   */
  async searchLearnings(query) {
    const allLearningIds = await this.redis.zrange('learnings:all', 0, -1);
    const queryLower = query.toLowerCase();

    const matches = [];
    for (const id of allLearningIds) {
      const learning = await this.redis.hgetall(id);
      if (learning && learning.videoId) {
        const searchText = (learning.title + ' ' + learning.summary).toLowerCase();
        if (searchText.includes(queryLower)) {
          learning.keyTakeaways = JSON.parse(learning.keyTakeaways || '[]');
          matches.push(learning);
        }
      }
    }

    return matches.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }
}

/**
 * Extract learnings from processed video knowledge
 */
export function extractLearningsFromVideo(videoKnowledge) {
  const learning = {
    title: videoKnowledge.title || '',
    summary: videoKnowledge.summary || '',
    keyTakeaways: [],
    category: 'general',
    implementationStatus: 'processed',
    implementationDetails: ''
  };

  // Extract key takeaways from summary or improvements
  if (videoKnowledge.improvements && Array.isArray(videoKnowledge.improvements)) {
    learning.keyTakeaways = videoKnowledge.improvements.map(imp => imp.description || imp);
  }

  // Categorize based on title/content
  const title = videoKnowledge.title.toLowerCase();
  if (title.includes('kubernetes') || title.includes('k8s')) {
    learning.category = 'kubernetes';
  } else if (title.includes('security') || title.includes('cyber')) {
    learning.category = 'security';
  } else if (title.includes('ai') || title.includes('llm') || title.includes('ml')) {
    learning.category = 'ai';
  } else if (title.includes('network')) {
    learning.category = 'networking';
  } else if (title.includes('devops') || title.includes('automation')) {
    learning.category = 'devops';
  } else if (title.includes('monitor') || title.includes('observability')) {
    learning.category = 'monitoring';
  }

  return learning;
}
