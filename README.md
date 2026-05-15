# 🏗️ JobSite — Automated Bangladeshi Job & Notice Publishing System

**JobSite** is a fully automated pipeline that watches for uploaded scanned newspaper images/PDFs, extracts text using OCR, classifies content with Google Gemini AI, generates SEO-optimized Bangla articles, and publishes them to a Hugo static site with automatic Git deployment.

## ✨ Features

- **📁 Auto File Watcher** — Monitors an uploads folder for new files and triggers processing automatically
- **🖼️ Image Preprocessing** — Grayscale, adaptive thresholding, sharpening, and smart resizing for optimal OCR
- **🔤 OCR Engine** — Tesseract-based Bangla + English text extraction with confidence scoring
- **🤖 AI Classification** — Google Gemini classifies content into: Job Circular, Tender Notice, Admission, Public Notice
- **📊 Structured Extraction** — AI extracts key fields (organization, deadline, salary, etc.) per category
- **✍️ Article Generation** — Generates human-quality, SEO-optimized Bangla articles with proper formatting
- **📝 Hugo Publishing** — Creates properly formatted Hugo markdown posts with YAML frontmatter
- **🚀 Git Auto-Deploy** — Automatic commit and push to GitHub Pages
- **🔍 Duplicate Detection** — SHA-256 hash + text similarity checks prevent duplicate posts
- **📈 Database Tracking** — SQLite database tracks all processed files, categories, and history

## 🏗️ Architecture

```
uploads/        ← Drop scanned images/PDFs here
    │
    ▼
ImageProcessor  ← Preprocess (grayscale, threshold, sharpen)
    │
    ▼
OCREngine       ← Tesseract OCR (Bangla + English)
    │
    ▼
AIClassifier    ← Gemini AI: classify content type
    │
    ▼
AIExtractor     ← Gemini AI: extract structured fields
    │
    ▼
AIWriter        ← Gemini AI: generate Bangla article
    │
    ▼
HugoWriter      ← Create Hugo markdown post
    │
    ▼
GitDeployer     ← Auto-commit & push to GitHub Pages
    │
    ▼
hugo-site/      ← Generated Hugo site (GitHub Pages ready)
```

## 📋 Prerequisites

- **Python 3.10+**
- **Tesseract OCR** with Bengali language data ([Download](https://github.com/UB-Mannheim/tesseract/wiki))
- **Google Gemini API Key** ([Get one](https://aistudio.google.com/apikey))
- **Hugo** (optional, for local preview — [Install](https://gohugo.io/installation/))

### Install Tesseract with Bengali

1. Download the Tesseract installer from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. During installation, select **Bengali** language data
3. Default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`
4. Update `config/settings.yaml` if installed elsewhere

## 🚀 Quick Start

### 1. Setup (One-time)

```bash
# Clone the repo
git clone https://github.com/yourusername/bd-jobs.git
cd bd-jobs

# Run the setup script
scripts\setup.bat
```

Or manually:

```bash
# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Initialize project
python main.py --setup
```

### 2. Configure

Edit `.env`:
```env
GEMINI_API_KEY=your_actual_api_key_here
```

Edit `config/settings.yaml` to customize OCR path, AI model, Hugo settings, etc.

### 3. Run

```bash
# Start the file watcher (processes files automatically)
scripts\run.bat

# Or directly:
python main.py

# Process a single file:
python main.py --once path\to\image.jpg

# Run setup again:
python main.py --setup
```

### 4. View Site

```bash
cd hugo-site
hugo server -D
# Open http://localhost:1313
```

## 📁 Project Structure

```
JobSite/
├── app/                    # Python application modules
│   ├── __init__.py         # Package init, version info
│   ├── ai_classifier.py    # Gemini AI content classifier
│   ├── ai_extractor.py     # Gemini AI structured data extractor
│   ├── ai_writer.py        # Gemini AI article generator
│   ├── database.py         # SQLite database manager
│   ├── git_deployer.py     # Git automation for deployment
│   ├── hugo_writer.py      # Hugo markdown post creator
│   ├── image_processor.py  # Image preprocessing pipeline
│   ├── logger.py           # Centralized logging system
│   ├── ocr_engine.py       # Tesseract OCR wrapper
│   ├── utils.py            # Shared utility functions
│   └── watcher.py          # File system watcher daemon
├── config/
│   └── settings.yaml       # Main configuration file
├── data/                   # SQLite database storage
├── failed/                 # Files that failed processing
├── hugo-site/              # Hugo static site
│   ├── config.toml         # Hugo site configuration
│   ├── content/posts/      # Generated markdown posts
│   ├── layouts/            # Hugo layout templates
│   ├── static/css/         # CSS styles
│   └── static/js/          # JavaScript
├── logs/                   # Application logs
├── processed/              # Successfully processed files
├── prompts/                # AI prompt templates
│   ├── classification.txt
│   ├── extraction.txt
│   └── article_generation.txt
├── scripts/                # Utility scripts
│   ├── setup.bat           # Windows setup script
│   ├── run.bat             # Windows run script
│   └── maintenance.py      # Stats, cleanup, Hugo build
├── thumbnails/             # Generated image thumbnails
├── uploads/                # Drop files here for processing
├── .env.example            # Environment variables template
├── .gitignore
├── main.py                 # Main pipeline entry point
├── README.md
└── requirements.txt        # Python dependencies
```

## 🎯 Usage Examples

### Process a single scanned notice:
```bash
python main.py --once "uploads/job_notice_01.jpg"
```

### View processing statistics:
```bash
python scripts\maintenance.py stats
```

### Clean old logs:
```bash
python scripts\maintenance.py clean --days 7
```

### Build Hugo site locally:
```bash
python scripts\maintenance.py build
```

## ⚙️ Configuration

Key settings in `config/settings.yaml`:

| Setting | Description | Default |
|---------|-------------|---------|
| `ocr.tesseract_cmd` | Tesseract executable path | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `ocr.languages` | OCR languages | `ben+eng` |
| `ai.model` | Gemini model | `gemini-2.0-flash` |
| `ai.temperature` | AI creativity (0-1) | `0.7` |
| `watcher.poll_interval` | File check interval (sec) | `5` |
| `git.auto_push` | Auto push to remote | `true` |
| `duplicate.similarity_threshold` | Duplicate match threshold | `85` |

## 🔧 Troubleshooting

**OCR produces garbled text:**
- Ensure Bengali language data is installed for Tesseract
- Try adjusting image preprocessing settings in `config/settings.yaml`
- Check that the scanned image is clear and high resolution

**Gemini API errors:**
- Verify GEMINI_API_KEY in `.env` is valid
- Check API quota limits
- Ensure internet connectivity

**Hugo site not building:**
- Install Hugo from https://gohugo.io/installation/
- Verify Hugo is in PATH or set `hugo.executable` in config

## 🛣️ Roadmap

- [x] Core OCR + AI pipeline
- [x] File watcher daemon
- [x] Hugo site generation
- [x] Git auto-deployment
- [x] Duplicate detection
- [ ] Web dashboard for monitoring
- [ ] Multi-language support (more OCR languages)
- [ ] Batch processing optimization
- [ ] Email notifications on failure
- [ ] Docker deployment support

## 📄 License

MIT License — See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request