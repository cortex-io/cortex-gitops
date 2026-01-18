FROM node:20-slim

# Install Python and pip for transcript extraction
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
RUN pip3 install --no-cache-dir youtube-transcript-api --break-system-packages

# Copy package files
COPY package*.json ./

# Install Node dependencies
RUN npm install --production

# Copy source code
COPY src/ ./src/
COPY extract_transcript.py ./

# Create data directories
RUN mkdir -p /data/transcripts /data/knowledge /data/cache

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:8080/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); })"

# Expose port
EXPOSE 8080

# Run the service
CMD ["node", "src/index.js"]
