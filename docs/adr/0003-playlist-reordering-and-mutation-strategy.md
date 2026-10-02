# Hybrid Playlist Reordering and Concurrency Control Strategy

To support both precise offset adjustments and macro sequence transformations (such as AI-driven energy curves or full playlist reorganization), the server exposes both native index range reordering (`spotify_reorder_playlist_tracks`) and atomic whole-playlist replacement (`spotify_replace_playlist_tracks`). All mutation tools return the updated `snapshot_id` to provide optimistic concurrency safety for AI agent workflows.
