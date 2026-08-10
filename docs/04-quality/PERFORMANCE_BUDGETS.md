# Performance Budgets

Initial targets:
- cold start <3s on mid-range SSD desktop;
- medium fixture usable <2s after project open, background indexing allowed;
- UI 60 FPS target;
- local event append p95 <20ms;
- backend state to UI p95 <150ms local;
- large transcripts virtualized;
- context building exposes size/timing and avoids unnecessary full scans.
