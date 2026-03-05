#!/usr/bin/env python3
"""
Automated disk space cleanup for macOS.
Safe by default (dry-run mode). Run with --execute to actually clean.
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import json


def get_size(path: Path) -> int:
    """Get size of file or directory in bytes."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return total


def format_size(bytes_size: int) -> str:
    """Format bytes to human readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} PB"


def parse_size(size_str: str) -> int:
    """Parse size string like '500MB' or '500M' to bytes."""
    # Order matters - check longer suffixes first
    units = [
        ('TB', 1024**4), ('T', 1024**4),
        ('GB', 1024**3), ('G', 1024**3),
        ('MB', 1024**2), ('M', 1024**2),
        ('KB', 1024), ('K', 1024),
        ('B', 1),
    ]
    size_str = size_str.strip().upper()
    for unit, multiplier in units:
        if size_str.endswith(unit):
            num_part = size_str[:-len(unit)].strip()
            return int(float(num_part) * multiplier)
    return int(size_str)


def get_disk_usage() -> dict:
    """Get current disk usage."""
    result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    if len(lines) >= 2:
        parts = lines[1].split()
        return {
            'total': parts[1],
            'used': parts[2],
            'available': parts[3],
            'percent_used': parts[4]
        }
    return {}


def find_items(pattern_dirs: list[tuple[Path, str]], dry_run: bool = True) -> list[dict]:
    """Find items matching patterns."""
    found = []
    for base_dir, pattern in pattern_dirs:
        if not base_dir.exists():
            continue
        try:
            if pattern == '*':
                # Direct children only
                for item in base_dir.iterdir():
                    found.append({
                        'path': item,
                        'size': get_size(item),
                        'type': 'dir' if item.is_dir() else 'file'
                    })
            elif '**' in pattern:
                # Recursive glob
                for item in base_dir.glob(pattern):
                    found.append({
                        'path': item,
                        'size': get_size(item),
                        'type': 'dir' if item.is_dir() else 'file'
                    })
            else:
                # Direct glob
                for item in base_dir.glob(pattern):
                    found.append({
                        'path': item,
                        'size': get_size(item),
                        'type': 'dir' if item.is_dir() else 'file'
                    })
        except (PermissionError, OSError) as e:
            print(f"  ⚠️  Cannot access {base_dir}: {e}")
    return found


def delete_item(item: dict, dry_run: bool = True) -> bool:
    """Delete a file or directory."""
    path = item['path']
    if dry_run:
        return True
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except (PermissionError, OSError) as e:
        print(f"  ⚠️  Cannot delete {path}: {e}")
        return False


def find_large_files(start_path: Path, threshold_bytes: int, max_results: int = 50) -> list[dict]:
    """Find files larger than threshold."""
    large_files = []
    exclude_dirs = {'.Trash', 'node_modules', '.git', 'Library'}

    try:
        for item in start_path.iterdir():
            if item.name in exclude_dirs or item.name.startswith('.'):
                continue
            if item.is_file():
                try:
                    size = item.stat().st_size
                    if size >= threshold_bytes:
                        large_files.append({'path': item, 'size': size})
                except (PermissionError, OSError):
                    pass
            elif item.is_dir():
                large_files.extend(find_large_files(item, threshold_bytes, max_results))
    except (PermissionError, OSError):
        pass

    return sorted(large_files, key=lambda x: x['size'], reverse=True)[:max_results]


def run_command(cmd: list[str], dry_run: bool = True) -> tuple[bool, str]:
    """Run a shell command."""
    if dry_run:
        return True, f"Would run: {' '.join(cmd)}"
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def cleanup_caches(home: Path, dry_run: bool) -> int:
    """Clean user caches. Returns bytes freed."""
    print("\n📁 Cleaning User Caches...")

    cache_dirs = [
        (home / 'Library' / 'Caches', '*'),
    ]

    items = find_items(cache_dirs, dry_run)
    total_size = sum(item['size'] for item in items)

    # Skip certain important caches
    skip_patterns = ['CloudKit', 'com.apple', 'Metadata']
    items = [i for i in items if not any(s in str(i['path']) for s in skip_patterns)]

    for item in items:
        action = "Would delete" if dry_run else "Deleting"
        print(f"  {action}: {item['path'].name} ({format_size(item['size'])})")
        delete_item(item, dry_run)

    print(f"  {'Would free' if dry_run else 'Freed'}: {format_size(total_size)}")
    return total_size


def cleanup_trash(home: Path, dry_run: bool) -> int:
    """Empty trash. Returns bytes freed."""
    print("\n🗑️  Emptying Trash...")

    trash_path = home / '.Trash'
    if not trash_path.exists():
        print("  Trash is empty")
        return 0

    items = find_items([(trash_path, '*')], dry_run)
    total_size = sum(item['size'] for item in items)

    if dry_run:
        print(f"  Would empty trash: {len(items)} items ({format_size(total_size)})")
    else:
        for item in items:
            delete_item(item, dry_run)
        print(f"  Emptied trash: {len(items)} items ({format_size(total_size)})")

    return total_size


def cleanup_downloads(home: Path, dry_run: bool) -> int:
    """Clean old DMGs from Downloads. Returns bytes freed."""
    print("\n📥 Cleaning Downloads (DMG files only)...")

    downloads = home / 'Downloads'
    items = find_items([(downloads, '*.dmg')], dry_run)
    total_size = sum(item['size'] for item in items)

    for item in items:
        action = "Would delete" if dry_run else "Deleting"
        print(f"  {action}: {item['path'].name} ({format_size(item['size'])})")
        delete_item(item, dry_run)

    if not items:
        print("  No DMG files found")
    else:
        print(f"  {'Would free' if dry_run else 'Freed'}: {format_size(total_size)}")

    return total_size


def cleanup_node_modules(home: Path, dry_run: bool) -> int:
    """Remove node_modules folders. Returns bytes freed."""
    print("\n📦 Finding node_modules folders...")

    # Search common development directories
    search_dirs = [
        home / 'Projects',
        home / 'Code',
        home / 'Developer',
        home / 'dev',
        home / 'repos',
        home / 'workspace',
        home / 'Doms workspace',
        home / 'Documents',
        home / 'Desktop',
    ]

    all_items = []
    for search_dir in search_dirs:
        if search_dir.exists():
            items = find_items([(search_dir, '**/node_modules')], dry_run)
            # Filter out nested node_modules (inside other node_modules)
            items = [i for i in items if 'node_modules/node_modules' not in str(i['path'])]
            all_items.extend(items)

    # Deduplicate
    seen = set()
    unique_items = []
    for item in all_items:
        if str(item['path']) not in seen:
            seen.add(str(item['path']))
            unique_items.append(item)

    total_size = sum(item['size'] for item in unique_items)

    if not unique_items:
        print("  No node_modules folders found")
        return 0

    print(f"  Found {len(unique_items)} node_modules folders")
    for item in unique_items[:20]:  # Show first 20
        action = "Would delete" if dry_run else "Deleting"
        print(f"  {action}: {item['path']} ({format_size(item['size'])})")
        delete_item(item, dry_run)

    if len(unique_items) > 20:
        print(f"  ... and {len(unique_items) - 20} more")
        if not dry_run:
            for item in unique_items[20:]:
                delete_item(item, dry_run)

    print(f"  {'Would free' if dry_run else 'Freed'}: {format_size(total_size)}")
    return total_size


def cleanup_python_cache(home: Path, dry_run: bool) -> int:
    """Remove Python cache files. Returns bytes freed."""
    print("\n🐍 Cleaning Python caches...")

    search_dirs = [
        home / 'Projects',
        home / 'Code',
        home / 'Developer',
        home / 'dev',
        home / 'repos',
        home / 'workspace',
        home / 'Doms workspace',
    ]

    all_items = []
    for search_dir in search_dirs:
        if search_dir.exists():
            items = find_items([(search_dir, '**/__pycache__')], dry_run)
            all_items.extend(items)
            items = find_items([(search_dir, '**/*.pyc')], dry_run)
            all_items.extend(items)

    total_size = sum(item['size'] for item in all_items)

    if not all_items:
        print("  No Python cache found")
        return 0

    for item in all_items:
        delete_item(item, dry_run)

    print(f"  Found {len(all_items)} cache items")
    print(f"  {'Would free' if dry_run else 'Freed'}: {format_size(total_size)}")
    return total_size


def cleanup_xcode(home: Path, dry_run: bool) -> int:
    """Clean Xcode derived data. Returns bytes freed."""
    print("\n🔨 Cleaning Xcode DerivedData...")

    derived_data = home / 'Library' / 'Developer' / 'Xcode' / 'DerivedData'
    if not derived_data.exists():
        print("  Xcode not installed or no DerivedData")
        return 0

    items = find_items([(derived_data, '*')], dry_run)
    total_size = sum(item['size'] for item in items)

    for item in items:
        action = "Would delete" if dry_run else "Deleting"
        print(f"  {action}: {item['path'].name} ({format_size(item['size'])})")
        delete_item(item, dry_run)

    print(f"  {'Would free' if dry_run else 'Freed'}: {format_size(total_size)}")
    return total_size


def cleanup_npm_cache(dry_run: bool) -> int:
    """Clean npm cache. Returns bytes freed."""
    print("\n📦 Cleaning npm cache...")

    # Check if npm is installed
    npm_check = subprocess.run(['which', 'npm'], capture_output=True)
    if npm_check.returncode != 0:
        print("  npm not installed")
        return 0

    # Get cache size first
    result = subprocess.run(['npm', 'cache', 'ls'], capture_output=True, text=True)

    if dry_run:
        print("  Would run: npm cache clean --force")
        # Estimate size from ~/.npm/_cacache
        cache_path = Path.home() / '.npm' / '_cacache'
        if cache_path.exists():
            size = get_size(cache_path)
            print(f"  Would free approximately: {format_size(size)}")
            return size
        return 0

    success, output = run_command(['npm', 'cache', 'clean', '--force'], dry_run)
    if success:
        print("  npm cache cleaned")
    else:
        print(f"  ⚠️  npm cache clean failed: {output}")
    return 0  # npm doesn't report size


def cleanup_homebrew(dry_run: bool) -> int:
    """Clean Homebrew cache. Returns bytes freed."""
    print("\n🍺 Cleaning Homebrew cache...")

    # Check if brew is installed
    brew_check = subprocess.run(['which', 'brew'], capture_output=True)
    if brew_check.returncode != 0:
        print("  Homebrew not installed")
        return 0

    if dry_run:
        result = subprocess.run(['brew', '--cache'], capture_output=True, text=True)
        cache_path = Path(result.stdout.strip())
        if cache_path.exists():
            size = get_size(cache_path)
            print(f"  Would run: brew cleanup --prune=all")
            print(f"  Would free approximately: {format_size(size)}")
            return size
        return 0

    success, output = run_command(['brew', 'cleanup', '--prune=all'], dry_run)
    if success:
        print("  Homebrew cache cleaned")
    else:
        print(f"  ⚠️  Homebrew cleanup failed: {output}")
    return 0


def cleanup_pip_cache(dry_run: bool) -> int:
    """Clean pip cache. Returns bytes freed."""
    print("\n🐍 Cleaning pip cache...")

    # Check if pip is installed
    pip_check = subprocess.run(['which', 'pip'], capture_output=True)
    if pip_check.returncode != 0:
        # Try pip3
        pip_check = subprocess.run(['which', 'pip3'], capture_output=True)
        if pip_check.returncode != 0:
            print("  pip not installed")
            return 0

    pip_cmd = 'pip3' if subprocess.run(['which', 'pip'], capture_output=True).returncode != 0 else 'pip'

    # Get cache location
    result = subprocess.run([pip_cmd, 'cache', 'dir'], capture_output=True, text=True)
    if result.returncode != 0:
        print("  pip cache command not supported")
        return 0

    cache_path = Path(result.stdout.strip())
    if cache_path.exists():
        size = get_size(cache_path)
        if dry_run:
            print(f"  Would run: pip cache purge")
            print(f"  Would free approximately: {format_size(size)}")
            return size

        success, output = run_command([pip_cmd, 'cache', 'purge'], dry_run)
        if success:
            print(f"  pip cache purged: {format_size(size)}")
            return size

    print("  pip cache is empty")
    return 0


def cleanup_docker(dry_run: bool) -> int:
    """Clean Docker system. Returns bytes freed."""
    print("\n🐳 Cleaning Docker...")

    # Check if docker is installed
    docker_which = subprocess.run(['which', 'docker'], capture_output=True)
    if docker_which.returncode != 0:
        print("  Docker not installed")
        return 0

    # Check if docker is running
    docker_check = subprocess.run(['docker', 'info'], capture_output=True)
    if docker_check.returncode != 0:
        print("  Docker not running")
        return 0

    # Get current disk usage
    result = subprocess.run(['docker', 'system', 'df'], capture_output=True, text=True)
    print(f"  Current Docker usage:\n{result.stdout}")

    if dry_run:
        print("  Would run: docker system prune -a --volumes -f")
        return 0

    success, output = run_command(['docker', 'system', 'prune', '-a', '--volumes', '-f'], dry_run)
    if success:
        print("  Docker system cleaned")
        print(output)
    else:
        print(f"  ⚠️  Docker cleanup failed: {output}")
    return 0


def main():
    parser = argparse.ArgumentParser(description='Automated disk space cleanup for macOS')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Preview what would be deleted (default: True)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually perform the cleanup')
    parser.add_argument('--aggressive', action='store_true',
                        help='Include aggressive cleanup (Homebrew, pip cache)')
    parser.add_argument('--find-large', action='store_true',
                        help='Find large files')
    parser.add_argument('--large-threshold', type=str, default='500MB',
                        help='Size threshold for large files (default: 500MB)')
    parser.add_argument('--clean-docker', action='store_true',
                        help='Clean Docker (destructive!)')
    parser.add_argument('--clean-node', action='store_true', default=True,
                        help='Remove node_modules folders (default: True)')
    parser.add_argument('--no-clean-node', action='store_true',
                        help='Skip node_modules cleanup')

    args = parser.parse_args()

    # --execute overrides --dry-run
    dry_run = not args.execute

    if args.no_clean_node:
        args.clean_node = False

    home = Path.home()

    # Header
    print("=" * 60)
    print("🧹 macOS Disk Cleanup Tool")
    print("=" * 60)

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No files will be deleted")
        print("   Run with --execute to actually clean\n")
    else:
        print("\n🚨 EXECUTE MODE - Files will be permanently deleted!\n")

    # Show current disk usage
    disk_before = get_disk_usage()
    print(f"📊 Current Disk Usage:")
    print(f"   Total: {disk_before.get('total', 'N/A')}")
    print(f"   Used: {disk_before.get('used', 'N/A')} ({disk_before.get('percent_used', 'N/A')})")
    print(f"   Available: {disk_before.get('available', 'N/A')}")

    # Track total space
    total_freed = 0

    # Run cleanups
    total_freed += cleanup_caches(home, dry_run)
    total_freed += cleanup_trash(home, dry_run)
    total_freed += cleanup_downloads(home, dry_run)

    if args.clean_node:
        total_freed += cleanup_node_modules(home, dry_run)

    total_freed += cleanup_python_cache(home, dry_run)
    total_freed += cleanup_xcode(home, dry_run)
    total_freed += cleanup_npm_cache(dry_run)

    if args.aggressive:
        total_freed += cleanup_homebrew(dry_run)
        total_freed += cleanup_pip_cache(dry_run)

    if args.clean_docker:
        cleanup_docker(dry_run)

    # Find large files
    if args.find_large:
        print("\n🔍 Finding Large Files...")
        threshold = parse_size(args.large_threshold)
        large_files = find_large_files(home, threshold)

        if large_files:
            print(f"\n   Files larger than {args.large_threshold}:")
            for f in large_files[:30]:
                print(f"   {format_size(f['size']):>10} - {f['path']}")
        else:
            print(f"   No files larger than {args.large_threshold} found")

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)

    if dry_run:
        print(f"\n   Potential space to free: {format_size(total_freed)}")
        print("\n   Run with --execute to actually clean these files")
    else:
        print(f"\n   Space freed: {format_size(total_freed)}")
        disk_after = get_disk_usage()
        print(f"\n   Disk Usage After:")
        print(f"   Available: {disk_after.get('available', 'N/A')}")

    # Save log
    log_dir = Path(__file__).parent.parent / '.tmp'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"cleanup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(log_file, 'w') as f:
        f.write(f"Cleanup run at {datetime.now().isoformat()}\n")
        f.write(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}\n")
        f.write(f"Space {'potential' if dry_run else 'freed'}: {format_size(total_freed)}\n")

    print(f"\n   Log saved to: {log_file}")


if __name__ == '__main__':
    main()
