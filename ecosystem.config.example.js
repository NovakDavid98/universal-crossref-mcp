module.exports = {
  apps: [
    {
      name: "universal-crossref-mcp",
      script: "src/mcp_server/simple_server.py",
      interpreter: "python3",
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: "200M",
      env: {
        NODE_ENV: "development",
        DATABASE_URL: "sqlite+aiosqlite:///./crossref.db"
      },
      env_production: {
        NODE_ENV: "production",
        DATABASE_URL: "sqlite+aiosqlite:///./crossref.db"
        // For PostgreSQL, uncomment and modify:
        // DATABASE_URL: "postgresql+asyncpg://username:password@localhost:5432/crossref_db"
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: "logs/err-0.log",
      out_file: "logs/out-0.log",
      merge_logs: true,
      time: true
    }
  ]
}; 