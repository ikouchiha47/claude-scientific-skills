FROM ubuntu:24.04

# System deps + Playwright browser dependencies + imagemagick
RUN apt-get update && apt-get install -y \
    curl git sqlite3 nodejs npm imagemagick \
    # Playwright Chromium deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2t64 libxshmfence1 \
    fonts-liberation xdg-utils wget \
    && rm -rf /var/lib/apt/lists/*

# uv (Python toolchain — no system Python pollution)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Python via uv
RUN uv python install 3.12

# Install Playwright as uv tool + Chromium browser
RUN uv tool install playwright && \
    playwright install chromium

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# OpenCode
RUN curl -fsSL https://opencode.ai/install | bash || true \
    && ln -sf /root/.opencode/bin/opencode /usr/local/bin/opencode

# Codex
RUN npm install -g @openai/codex || true

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["entrypoint.sh"]
CMD ["sleep", "infinity"]
