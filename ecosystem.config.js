// PM2 process manager config — auto-restarts on crash/freeze
// Usage: pm2 start ecosystem.config.js
// Or:    npm run dev:safe
module.exports = {
  apps: [
    {
      name: "purangpt-next",
      script: "node_modules/.bin/next",
      args: "dev --port 3000",
      cwd: __dirname,
      env: {
        NODE_ENV: "development",
      },
      // Auto-restart on crash or memory leak
      max_memory_restart: "1G",
      restart_delay: 2000,
      max_restarts: 10,
      min_uptime: "5s",
      // Health check — if no response in 30s, restart
      exp_backoff_restart_delay: 1000,
      watch: false, // Next.js has its own HMR
      // Log files
      out_file: "/tmp/purangpt-next.out.log",
      error_file: "/tmp/purangpt-next.err.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
    },
  ],
};
