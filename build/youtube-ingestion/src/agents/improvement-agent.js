/**
 * Improvement Agent
 * Analyzes videos for actionable improvements to Cortex
 */

export class ImprovementAgent {
  constructor(knowledgeStore) {
    this.knowledgeStore = knowledgeStore;
  }

  /**
   * Analyze a video for improvement opportunities
   * @param {Object} knowledge
   * @returns {Promise<Object>}
   */
  async analyzeVideo(knowledge) {
    console.log(`[ImprovementAgent] Analyzing video: ${knowledge.title}`);

    // Extract actionable items from classification
    const passive = [];
    const active = [];

    for (const item of knowledge.actionable_items || []) {
      const improvement = {
        type: item.type,
        description: item.description,
        implementation_notes: item.implementation_notes,
        video_id: knowledge.video_id,
        video_title: knowledge.title,
        relevance: knowledge.relevance_to_cortex,
        source: 'youtube-ingestion',
        created_at: new Date().toISOString()
      };

      // Classify as passive (learning) or active (implementation)
      if (item.type === 'technique' || item.type === 'pattern') {
        passive.push(improvement);
      } else {
        active.push(improvement);
      }
    }

    console.log(`[ImprovementAgent] Found ${passive.length} passive and ${active.length} active improvements`);

    return {
      video_id: knowledge.video_id,
      video_title: knowledge.title,
      improvements: {
        passive,
        active
      },
      analyzed_at: new Date().toISOString()
    };
  }

  /**
   * Perform meta-review of accumulated knowledge
   * @param {Object} options
   * @returns {Promise<Object>}
   */
  async performMetaReview(options = {}) {
    console.log('[ImprovementAgent] Performing meta-review...');

    // Get all videos from knowledge store
    const videos = await this.knowledgeStore.listAll(options.limit || 100);

    // Aggregate statistics
    const stats = {
      total_videos: videos.length,
      total_concepts: 0,
      total_tools: 0,
      total_improvements: 0,
      average_relevance: 0,
      categories: {},
      tools: {},
      concepts: {}
    };

    let relevanceSum = 0;

    for (const video of videos) {
      relevanceSum += video.relevance_to_cortex || 0;
      stats.total_concepts += (video.key_concepts || []).length;
      stats.total_tools += (video.tools_mentioned || []).length;
      stats.total_improvements += (video.actionable_items || []).length;

      // Category counts
      const cat = video.category || 'other';
      stats.categories[cat] = (stats.categories[cat] || 0) + 1;

      // Tool counts
      for (const tool of video.tools_mentioned || []) {
        stats.tools[tool] = (stats.tools[tool] || 0) + 1;
      }

      // Concept counts
      for (const concept of video.key_concepts || []) {
        stats.concepts[concept] = (stats.concepts[concept] || 0) + 1;
      }
    }

    stats.average_relevance = videos.length > 0 ? relevanceSum / videos.length : 0;

    return {
      stats,
      reviewed_at: new Date().toISOString()
    };
  }
}

export default ImprovementAgent;
