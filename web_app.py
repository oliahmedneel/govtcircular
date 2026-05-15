# ========================================
# JobSite — Complete Web Dashboard (Flask)
# ========================================
"""
Full browser-based interface for the JobSite automation system.
All operations can be performed through this dashboard.
"""

import os
import sys
import json
import sqlite3
import threading
import time
import logging
import re
from pathlib import Path
from datetime import datetime
from io import TextIOWrapper

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_from_directory, Response, session, stream_with_context
)
from werkzeug.utils import secure_filename

from app.utils import load_config, get_project_root, get_supported_extensions, ensure_directories
from app.database import Database
from app.publisher import Publisher
from main import JobSitePipeline

app = Flask(__name__)
app.secret_key = 'jobsite_secret_key_change_in_production'

config = load_config()
pipeline = JobSitePipeline(config)
db = Database(config)

project_root = get_project_root()

# Paths from config
UPLOAD_FOLDER = os.path.join(project_root, config.get("paths", {}).get("uploads", "uploads"))
PROCESSED_FOLDER = os.path.join(project_root, config.get("paths", {}).get("processed", "processed"))
FAILED_FOLDER = os.path.join(project_root, config.get("paths", {}).get("failed", "failed"))
LOGS_FOLDER = os.path.join(project_root, config.get("paths", {}).get("logs", "logs"))
THUMBNAILS_FOLDER = os.path.join(project_root, config.get("paths", {}).get("thumbnails", "thumbnails"))
DATA_FOLDER = os.path.join(project_root, config.get("paths", {}).get("data", "data"))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(FAILED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

SUPPORTED_EXTENSIONS = get_supported_extensions(config)

CATEGORIES = config.get("categories", {
    "job_circular": "চাকরির বিজ্ঞপ্তি",
    "tender_notice": "দরপত্র বিজ্ঞপ্তি",
    "admission": "ভর্তি বিজ্ঞপ্তি",
    "public_notice": "সরকারি বিজ্ঞপ্তি",
    "unknown": "অন্যান্য",
})


# ===========================
# HELPER FUNCTIONS
# ===========================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


def get_file_list(folder: str) -> list:
    """Get list of files in a folder with metadata."""
    files = []
    if not os.path.exists(folder):
        return files
    try:
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                files.append({
                    "name": fname,
                    "size": stat.st_size,
                    "size_hr": format_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "ext": os.path.splitext(fname)[1].lower(),
                })
    except Exception:
        pass
    files.sort(key=lambda x: x["modified"], reverse=True)
    return files


def format_size(size: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_log_content(log_type: str = "app", tail_lines: int = 200) -> str:
    """Get content of log files."""
    log_file = os.path.join(LOGS_FOLDER, f"{log_type}.log")
    if not os.path.exists(log_file):
        return "No log file found."
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-tail_lines:])
    except Exception as e:
        return f"Error reading log: {str(e)}"


def get_hugo_content_dir() -> str:
    """Get the Hugo content directory path."""
    paths = config.get("paths", {})
    hugo_site = os.path.join(project_root, paths.get("hugo_site", "hugo-site"))
    return os.path.join(hugo_site, paths.get("hugo_content", "content/posts"))


def get_hugo_posts() -> list:
    """Get list of generated Hugo posts."""
    content_dir = get_hugo_content_dir()
    posts = []
    if not os.path.exists(content_dir):
        return posts
    try:
        for fname in os.listdir(content_dir):
            if fname.endswith(".md"):
                fpath = os.path.join(content_dir, fname)
                stat = os.stat(fpath)
                # Extract title from YAML frontmatter
                title = fname
                category = ""
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Simple frontmatter parsing
                    match = re.search(r'title:\s*"([^"]+)"', content)
                    if match:
                        title = match.group(1)
                    match = re.search(r'categories:\s*\n\s*-\s*(.+)', content)
                    if match:
                        category = match.group(1).strip()
                except Exception:
                    pass
                posts.append({
                    "filename": fname,
                    "title": title,
                    "category": category,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "path": fpath,
                })
    except Exception:
        pass
    posts.sort(key=lambda x: x["modified"], reverse=True)
    return posts


def get_db_path() -> str:
    """Get database file path."""
    return os.path.join(DATA_FOLDER, "jobsite.db")


# ===========================
# ROUTES: Core Pages
# ===========================

@app.route('/')
def index():
    """Dashboard home page."""
    stats = db.get_stats()
    return render_template('index.html', stats=stats, categories=CATEGORIES)


@app.route('/files')
def files_page():
    """File management page."""
    uploads = get_file_list(UPLOAD_FOLDER)
    processed = get_file_list(PROCESSED_FOLDER)
    failed = get_file_list(FAILED_FOLDER)
    # Get file stats from DB
    stats = db.get_stats()
    return render_template(
        'files.html',
        uploads=uploads,
        processed=processed,
        failed=failed,
        stats=stats
    )


@app.route('/posts')
def posts_page():
    """Hugo posts management page."""
    posts = get_hugo_posts()
    stats = db.get_stats()
    return render_template('posts.html', posts=posts, stats=stats)


@app.route('/logs')
def logs_page():
    """Log viewer page."""
    log_types = ["app", "error"]
    current_log = request.args.get("type", "app")
    lines = request.args.get("lines", 200, type=int)
    content = get_log_content(current_log, lines)
    return render_template(
        'logs.html',
        log_types=log_types,
        current_log=current_log,
        content=content,
        lines=lines
    )


@app.route('/config-page')
def config_page():
    """Configuration management page."""
    return render_template('config.html', config=config, categories=CATEGORIES)


@app.route('/categories')
def categories_page():
    """Category management page."""
    stats = db.get_stats()
    return render_template('categories.html', categories=CATEGORIES, stats=stats)


# ===========================
# API ROUTES: File Operations
# ===========================

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload and process a single file."""
    if 'file' not in request.files:
        flash('কোন ফাইল পাওয়া যায়নি', 'danger')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('কোন ফাইল সিলেক্ট করা হয়নি', 'warning')
        return redirect(url_for('index'))

    if not allowed_file(file.filename):
        flash(f'অনুমোদিত ফাইল টাইপ নয়। সমর্থিত: {", ".join(SUPPORTED_EXTENSIONS)}', 'danger')
        return redirect(url_for('index'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Process the file
        result = pipeline.process_file(filepath)

        if result.get("success"):
            flash(f'✅ সফলভাবে প্রসেস করা হয়েছে: {filename}', 'success')
        else:
            flash(f'❌ প্রসেস ব্যর্থ: {result.get("error", "অজানা ত্রুটি")}', 'danger')

        return redirect(url_for('index'))


@app.route('/upload-json', methods=['POST'])
def upload_file_json():
    """Upload file via AJAX and return JSON response."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False,
            "error": f"Invalid file type. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        }), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Process in background thread
    def process_in_background(fp, fn):
        with app.app_context():
            try:
                result = pipeline.process_file(fp)
                if result.get("success"):
                    flash(f'✅ সফলভাবে প্রসেস করা হয়েছে: {fn}', 'success')
                else:
                    flash(f'❌ প্রসেস ব্যর্থ: {fn}', 'danger')
            except Exception as e:
                flash(f'❌ প্রসেস ব্যর্থ: {fn} - {str(e)}', 'danger')

    thread = threading.Thread(target=process_in_background, args=(filepath, filename))
    thread.daemon = True
    thread.start()

    return jsonify({"success": True, "message": f"Processing started: {filename}"})


@app.route('/api/reprocess/<path:filename>')
def reprocess_file(filename):
    """Reprocess a file from processed or uploads folder."""
    # Check in uploads first
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        # Check in processed
        filepath = os.path.join(PROCESSED_FOLDER, filename)
    if not os.path.exists(filepath):
        flash(f'ফাইল পাওয়া যায়নি: {filename}', 'danger')
        return redirect(url_for('files_page'))

    result = pipeline.process_file(filepath)

    if result.get("success"):
        flash(f'✅ পুনরায় প্রসেস সফল: {filename}', 'success')
    else:
        flash(f'❌ প্রসেস ব্যর্থ: {result.get("error", "অজানা ত্রুটি")}', 'danger')

    return redirect(url_for('files_page'))


@app.route('/api/delete-file', methods=['POST'])
def delete_file():
    """Delete a file from any directory."""
    data = request.get_json()
    filepath = data.get('path', '')
    folder = data.get('folder', 'uploads')

    if folder == 'uploads':
        base = UPLOAD_FOLDER
    elif folder == 'processed':
        base = PROCESSED_FOLDER
    elif folder == 'failed':
        base = FAILED_FOLDER
    else:
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    full_path = os.path.join(base, os.path.basename(filepath))
    if os.path.exists(full_path):
        os.remove(full_path)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "File not found"}), 404


@app.route('/api/clear-folder', methods=['POST'])
def clear_folder():
    """Clear all files in a folder."""
    data = request.get_json()
    folder = data.get('folder', '')

    if folder == 'uploads':
        base = UPLOAD_FOLDER
    elif folder == 'processed':
        base = PROCESSED_FOLDER
    elif folder == 'failed':
        base = FAILED_FOLDER
    else:
        return jsonify({"success": False, "error": "Invalid folder"}), 400

    count = 0
    if os.path.exists(base):
        for fname in os.listdir(base):
            fpath = os.path.join(base, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                count += 1

    return jsonify({"success": True, "count": count})


# ===========================
# API ROUTES: Posts
# ===========================

@app.route('/api/post/<slug>')
def get_post_content(slug):
    """Get content of a specific post."""
    content_dir = get_hugo_content_dir()
    filepath = os.path.join(content_dir, f"{slug}.md")
    if not os.path.exists(filepath):
        # Try with .md extension already
        filepath = os.path.join(content_dir, slug)
    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": "Post not found"}), 404

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"success": True, "content": content})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/delete-post', methods=['POST'])
def delete_post():
    """Delete a Hugo post."""
    data = request.get_json()
    filename = data.get('filename', '')
    content_dir = get_hugo_content_dir()
    filepath = os.path.join(content_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({"success": False, "error": "Post not found"}), 404

    try:
        os.remove(filepath)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ===========================
# API ROUTES: Database & Stats
# ===========================

@app.route('/api/stats')
def api_stats():
    """Get processing statistics as JSON."""
    return jsonify(db.get_stats())


@app.route('/api/db-records')
def api_db_records():
    """Get all database records."""
    try:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get files
        cursor.execute("""
            SELECT id, filename, category, slug, status, error, processed_at, created_at
            FROM files ORDER BY processed_at DESC LIMIT 200
        """)
        files = [dict(row) for row in cursor.fetchall()]

        # Get posts
        cursor.execute("""
            SELECT p.*, f.filename as source_file
            FROM posts p
            LEFT JOIN files f ON p.file_id = f.id
            ORDER BY p.created_at DESC LIMIT 200
        """)
        posts = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return jsonify({"files": files, "posts": posts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/db-clear', methods=['POST'])
def api_db_clear():
    """Clear all database records."""
    try:
        import sqlite3
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("DELETE FROM posts")
        cursor.execute("DELETE FROM files")
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ===========================
# API ROUTES: Static Website Publisher (Phase 2)
# ===========================

@app.route('/api/publish', methods=['POST'])
def api_publish():
    """Run the complete publishing pipeline: Hugo build + Git deploy."""
    try:
        publisher = Publisher(config)
        data = request.get_json() or {}
        filepath = data.get('filepath', '')

        if filepath and os.path.exists(filepath):
            result = publisher.publish_single(filepath)
        else:
            result = publisher.publish_all()

        return jsonify({
            "success": result.get("success", False),
            "message": "✅ প্রকাশ সম্পন্ন হয়েছে!" if result.get("success") else "❌ প্রকাশ ব্যর্থ হয়েছে",
            "details": result,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/publish/setup', methods=['POST'])
def api_publish_setup():
    """Setup the Hugo repository for GitHub Pages."""
    try:
        publisher = Publisher(config)
        success = publisher.setup_repository()
        return jsonify({
            "success": success,
            "message": "✅ সেটআপ সম্পন্ন" if success else "❌ সেটআপ ব্যর্থ",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/publish/check', methods=['GET'])
def api_publish_check():
    """Check if Hugo is installed and ready."""
    try:
        publisher = Publisher(config)
        info = publisher.check_hugo_installation()
        return jsonify(info)
    except Exception as e:
        return jsonify({"installed": False, "error": str(e)})


@app.route('/api/publish/search-index', methods=['POST'])
def api_publish_search_index():
    """Generate search index JSON."""
    try:
        publisher = Publisher(config)
        path = publisher.generate_search_index()
        return jsonify({
            "success": path is not None,
            "path": path,
            "message": "✅ সার্চ ইনডেক্স জেনারেট করা হয়েছে" if path else "❌ ব্যর্থ",
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ===========================
# API ROUTES: System & Actions
# ===========================

@app.route('/api/logs')
def api_logs():
    """Get log content as JSON."""
    log_type = request.args.get("type", "app")
    lines = request.args.get("lines", 100, type=int)
    content = get_log_content(log_type, lines)
    return jsonify({"content": content, "type": log_type})


@app.route('/api/logs-stream')
def api_logs_stream():
    """Stream log updates via SSE."""
    log_type = request.args.get("type", "app")

    def generate():
        log_file = os.path.join(LOGS_FOLDER, f"{log_type}.log")
        last_size = 0
        while True:
            try:
                if os.path.exists(log_file):
                    current_size = os.path.getsize(log_file)
                    if current_size > last_size:
                        with open(log_file, "r", encoding="utf-8") as f:
                            f.seek(last_size)
                            new_content = f.read()
                            last_size = current_size
                            yield f"data: {json.dumps({'new': new_content})}\n\n"
                    elif current_size < last_size:
                        # File was rotated, read all
                        last_size = 0
            except Exception:
                pass
            time.sleep(2)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route('/api/system-info')
def api_system_info():
    """Get system information."""
    stats = db.get_stats()
    upload_count = len(get_file_list(UPLOAD_FOLDER))
    processed_count = len(get_file_list(PROCESSED_FOLDER))
    failed_count = len(get_file_list(FAILED_FOLDER))
    post_count = len(get_hugo_posts())

    return jsonify({
        "db_stats": stats,
        "file_counts": {
            "uploads": upload_count,
            "processed": processed_count,
            "failed": failed_count,
        },
        "post_count": post_count,
        "categories": CATEGORIES,
        "config_summary": {
            "ocr_languages": config.get("ocr", {}).get("languages", "ben+eng"),
            "ai_model": config.get("ai", {}).get("model", "gemini-2.0-flash"),
            "auto_push": config.get("git", {}).get("auto_push", True),
            "watcher_enabled": config.get("watcher", {}).get("poll_interval", 5) > 0,
        }
    })


@app.route('/api/run-pipeline', methods=['POST'])
def api_run_pipeline():
    """Manually run a specific pipeline stage or full pipeline on a file."""
    data = request.get_json()
    filepath = data.get('filepath', '')

    if not filepath or not os.path.exists(filepath):
        return jsonify({"success": False, "error": "File not found"}), 404

    try:
        result = pipeline.process_file(filepath)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/git-push', methods=['POST'])
def api_git_push():
    """Trigger git commit and push."""
    try:
        from app.git_deployer import GitDeployer
        git = GitDeployer(config)
        message = request.json.get('message', 'Manual deploy from dashboard')
        result = git.commit_and_push(message)
        return jsonify({"success": True, "message": f"Git push triggered: {result}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """Get or update configuration."""
    if request.method == 'GET':
        return jsonify(config)

    # POST: Update config
    try:
        updates = request.get_json()
        config_path = os.path.join(project_root, "config", "settings.yaml")
        import yaml

        # Merge updates into current config
        for key, value in updates.items():
            if isinstance(value, dict) and key in config:
                config[key].update(value)
            else:
                config[key] = value

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

        return jsonify({"success": True, "message": "Configuration updated. Restart required for some changes."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/run-setup', methods=['POST'])
def api_run_setup():
    """Run setup process."""
    try:
        ensure_directories(config)
        db.initialize()
        return jsonify({"success": True, "message": "Setup completed successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/prompt/<name>', methods=['GET', 'POST'])
def api_prompt(name):
    """Get or update AI prompt files."""
    prompts_dir = os.path.join(project_root, config.get("paths", {}).get("prompts", "prompts"))
    valid_names = ["classification", "extraction", "article_generation"]
    
    if name not in valid_names:
        return jsonify({"success": False, "error": "Invalid prompt name"}), 400
    
    filepath = os.path.join(prompts_dir, f"{name}.txt")
    
    if request.method == 'GET':
        if not os.path.exists(filepath):
            return jsonify({"success": False, "error": "Prompt file not found"}), 404
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return jsonify({"success": True, "content": content})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    else:
        try:
            data = request.get_json()
            content = data.get('content', '')
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return jsonify({"success": True, "message": "Prompt saved"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/move-to-uploads', methods=['POST'])
def api_move_to_uploads():
    """Move a file from processed/failed back to uploads for reprocessing."""
    data = request.get_json()
    filepath = data.get('filepath', '')
    source_folder = data.get('source', 'failed')

    if source_folder == 'failed':
        src = FAILED_FOLDER
    elif source_folder == 'processed':
        src = PROCESSED_FOLDER
    else:
        return jsonify({"success": False, "error": "Invalid source"}), 400

    basename = os.path.basename(filepath)
    src_path = os.path.join(src, basename)

    if not os.path.exists(src_path):
        return jsonify({"success": False, "error": "Source file not found"}), 404

    dest_path = os.path.join(UPLOAD_FOLDER, basename)
    # Handle filename conflict
    if os.path.exists(dest_path):
        name, ext = os.path.splitext(basename)
        basename = f"{name}_{int(time.time())}{ext}"
        dest_path = os.path.join(UPLOAD_FOLDER, basename)

    os.rename(src_path, dest_path)
    return jsonify({"success": True, "new_path": dest_path})


# ===========================
# ROUTES: Static Assets
# ===========================

@app.route('/static/<path:filename>')
def custom_static(filename):
    """Serve files from the static directory."""
    return send_from_directory(os.path.join(project_root, 'static'), filename)


@app.route('/thumbnails/<path:filename>')
def serve_thumbnail(filename):
    """Serve thumbnail images."""
    return send_from_directory(THUMBNAILS_FOLDER, filename)


# ===========================
# MAIN ENTRY
# ===========================

if __name__ == '__main__':
    # Configure root logger for the web app
    from app.logger import get_logger
    get_logger(__name__, config)

    print("=" * 60)
    print("  🌐 JobSite Web Dashboard")
    print("=" * 60)
    print(f"  📁 Uploads:     {UPLOAD_FOLDER}")
    print(f"  📊 Database:    {get_db_path()}")
    print(f"  📝 Logs:        {LOGS_FOLDER}")
    print("=" * 60)
    print("  Open browser: http://localhost:5000")
    print("=" * 60)

    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)