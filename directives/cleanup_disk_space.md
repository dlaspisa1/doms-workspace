# Cleanup Disk Space

Automated disk space cleanup for macOS. Safely removes caches, temporary files, development artifacts, and identifies large files.

## When to Use

- Mac running low on disk space
- Regular maintenance (monthly recommended)
- Before large downloads/installs
- After heavy development work

## Inputs

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `--dry-run` | No | `True` | Preview what would be deleted without deleting |
| `--execute` | No | `False` | Actually perform the cleanup |
| `--aggressive` | No | `False` | Include more aggressive cleanup (Homebrew, pip cache) |
| `--find-large` | No | `True` | Find files larger than threshold |
| `--large-threshold` | No | `500MB` | Size threshold for "large file" detection |
| `--clean-docker` | No | `False` | Clean Docker images/containers (destructive!) |
| `--clean-node` | No | `True` | Remove node_modules folders |

## Execution

```bash
# Preview what would be cleaned (safe, always run first)
python execution/cleanup_disk_space.py --dry-run

# Execute cleanup after reviewing
python execution/cleanup_disk_space.py --execute

# Aggressive cleanup (includes Homebrew, pip, more caches)
python execution/cleanup_disk_space.py --execute --aggressive

# Find large files only (no cleanup)
python execution/cleanup_disk_space.py --find-large --large-threshold 1GB
```

## What Gets Cleaned

### Safe (Default)
- `~/Library/Caches/*` - User application caches
- `~/.Trash/*` - Trash
- `~/Downloads/*.dmg` - Old disk images
- `~/.npm/_cacache` - npm cache
- `**/node_modules` - Node.js dependencies (can be reinstalled)
- `**/__pycache__` - Python bytecode cache
- `**/*.pyc` - Python compiled files
- `~/.gradle/caches` - Gradle build cache
- `~/Library/Developer/Xcode/DerivedData` - Xcode build artifacts

### Aggressive (--aggressive flag)
- Homebrew cache: `brew cleanup --prune=all`
- pip cache: `pip cache purge`
- CocoaPods cache
- Carthage cache

### Docker (--clean-docker flag)
- Stopped containers
- Unused images
- Build cache
- Unused volumes (careful!)

## Outputs

- Console report showing:
  - Space before cleanup
  - Items found/deleted
  - Space recovered
  - Large files detected
- Log file: `.tmp/cleanup_log_{timestamp}.txt`

## Safety Features

1. **Dry-run by default** - Always previews before deleting
2. **Excludes active projects** - Won't delete node_modules in current directory
3. **Confirms large deletions** - Asks before deleting >1GB
4. **Preserves important caches** - Browser caches, credential stores untouched
5. **Logs everything** - Full audit trail in `.tmp/`

## Edge Cases

- **Xcode not installed**: Skips DerivedData cleanup
- **Docker not running**: Skips Docker cleanup with warning
- **Permission denied**: Logs error, continues with other items
- **Active downloads**: Skips Downloads folder if browser is running

## Learnings

- npm cache can grow to 5GB+, safe to clear
- node_modules folders across old projects often waste 20GB+
- Xcode DerivedData is the #1 space hog for iOS developers
- ~/Library/Caches rarely contains anything critical
