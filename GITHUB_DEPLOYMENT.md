# 📋 Pre-Deployment Checklist for GitHub

## ✅ Before Pushing to GitHub

Run this checklist to ensure smooth CI/CD:

```bash
# 1. Clean up unnecessary files
rm -rf venv/ __pycache__/ .pytest_cache/ htmlcov/ .coverage
rm -rf data/raw/* data/processed/* logs/* models/*
rm -rf done/ echo/ target/ dbt_packages/ {data

# 2. Create/update .env (use .env.example as template)
cp .env.example .env
# Edit .env with your actual values

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run linters
black src/ tests/
isort src/ tests/
flake8 src/ tests/ --max-line-length=120

# 5. Run type checking
mypy src/ --ignore-missing-imports

# 6. Run tests locally
pytest tests/ -v --cov=src --cov-report=term-missing

# 7. Verify A/B testing engine
cd src/ab_testing
python ab_engine.py
cd ../../

# 8. Test docker-compose locally
docker-compose config
docker-compose build

# 9. Verify gitignore
git status --ignored

# 10. Check for secrets in code
git diff --cached | grep -i "password\|secret\|token\|key" && echo "⚠️ SECRETS FOUND!" || echo "✓ No secrets detected"
```

## 🔐 Security Checks

```bash
# Check for hardcoded credentials
grep -r "password" src/ config/ --exclude-dir=.git
grep -r "api_key" src/ config/ --exclude-dir=.git

# Check Python dependencies for vulnerabilities
safety check

# Check Docker image for vulnerabilities (requires docker scout)
docker scout cves .
```

## 📦 Create Release

```bash
# 1. Update version in setup.py (if you have one)
# 2. Update CHANGELOG.md
# 3. Commit changes
git add .
git commit -m "chore: release v1.0.0"

# 4. Create and push tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main
git push origin v1.0.0

# This will trigger the release workflow automatically!
```

## 🚀 GitHub Actions Setup

### 1. Create GitHub Repository

```bash
cd /path/to/ecommerce_analytics
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_ORG/nexacommerce-analytics.git
git push -u origin main
```

### 2. Enable GitHub Actions

1. Go to **Settings** → **Actions** → **General**
2. Set **Actions Permissions** to "Allow all actions and reusable workflows"
3. Enable "Allow GitHub Actions to create and approve pull requests"

### 3. Add Secrets (if needed)

Go to **Settings** → **Secrets and variables** → **Actions**

Optional secrets:
- `SLACK_WEBHOOK_URL` - For Slack notifications
- `PYPI_API_TOKEN` - For publishing Python package
- `DOCKER_USERNAME` / `DOCKER_PASSWORD` - For Docker Hub (not needed for GitHub Container Registry)

### 4. Configure Branch Protection

1. Go to **Settings** → **Branches** → **Add rule**
2. Apply to branch: `main`
3. Enable:
   - ✅ Require a pull request before merging
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require code reviews before merging (at least 1)

### 5. Approve Workflows

First PR will require approval to run workflows:
1. Go to Pull Requests
2. Click the failing workflow
3. Click "Approve and run"

## 📋 What the CI/CD Pipeline Does

### On Every Push to `main` or `develop`:

1. **Lint & Code Quality**
   - `flake8` - Style checking
   - `black` - Code formatting
   - `isort` - Import sorting
   - `mypy` - Type checking

2. **Tests (Python 3.11 & 3.12)**
   - Unit tests with `pytest`
   - Integration tests with live PostgreSQL + Redis
   - Code coverage reporting to Codecov

3. **Security Scans**
   - `bandit` - Static security analysis
   - `safety` - Dependency vulnerability checks

4. **Docker Build**
   - Builds production Docker image
   - Pushes to GitHub Container Registry
   - Tags with branch name and SHA

5. **A/B Testing Verification**
   - Runs ab_engine.py
   - Verifies output files (CSV, Parquet, JSON)

6. **Docker Compose Validation**
   - Validates docker-compose.yml syntax

### On Tag Push (e.g., `v1.0.0`):

1. **Create Release**
   - Auto-generates changelog from git history
   - Creates GitHub Release

2. **Build & Push Release Image**
   - Builds production image
   - Tags with version (v1.0.0)
   - Pushes to GitHub Container Registry

3. **Publish Python Package** (optional)
   - Publishes to PyPI if `setup.py` exists

4. **Slack Notification** (optional)
   - Sends deployment notification

## 🧪 Test Workflow Locally

```bash
# Install GitHub Actions runner locally
brew install act  # macOS
# or
choco install act  # Windows

# Run specific workflow locally
act -j test

# Run all workflows
act

# View available jobs
act -l
```

## 📊 View Workflow Status

1. Go to **Actions** tab on GitHub
2. Click workflow to see details
3. Click job to see logs
4. Click step to see individual command output

## 🐛 Troubleshooting CI/CD

### Workflow keeps failing?

1. **Check logs** - Click the failing workflow and scroll through logs
2. **Check environment** - Verify `.env` is set correctly
3. **Check secrets** - Ensure GitHub secrets are configured
4. **Run locally** - Use `pytest` to debug locally first
5. **Check syntax** - Validate YAML with `yamllint`

### Common Issues

**Database connection fails:**
```bash
# Ensure service dependencies are correct in workflow
# PostgreSQL must be healthy before tests run
services:
  postgres:
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-retries 5
```

**Docker image build fails:**
```bash
# Check Dockerfile syntax
docker build -t test:latest .

# Check .dockerignore
cat .dockerignore
```

**Tests pass locally but fail in CI:**
```bash
# Could be environment differences - check:
# 1. Python version (3.12 in CI)
# 2. OS differences (Ubuntu in CI vs your local)
# 3. Environment variables
# 4. File paths (use Path() not hardcoded paths)
```

## 🎯 Best Practices

1. ✅ **Always run tests locally before pushing**
   ```bash
   pytest tests/ -v --cov=src
   ```

2. ✅ **Format code before committing**
   ```bash
   black src/
   isort src/
   ```

3. ✅ **Use meaningful commit messages**
   ```bash
   git commit -m "feat: add A/B testing engine"
   git commit -m "fix: resolve database connection timeout"
   git commit -m "docs: update README with deployment instructions"
   ```

4. ✅ **Create feature branches**
   ```bash
   git checkout -b feature/new-analysis
   git push -u origin feature/new-analysis
   # Create Pull Request on GitHub
   ```

5. ✅ **Tag releases properly**
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0 - Initial production release"
   git push origin v1.0.0
   ```

6. ✅ **Keep .env and .env.docker secrets out of Git**
   - Already in `.gitignore`
   - Use `.env.example` for template
   - Never commit actual credentials

7. ✅ **Monitor workflow runs**
   - Check **Actions** tab regularly
   - Fix failures promptly
   - Review code coverage trends

---

## ✨ Quick Reference

| Task | Command |
|------|---------|
| Run tests | `pytest tests/ -v` |
| Format code | `black src/ && isort src/` |
| Check linting | `flake8 src/` |
| Type checking | `mypy src/` |
| Run A/B engine | `python src/ab_testing/ab_engine.py` |
| Build Docker | `docker build -t nexacommerce:latest .` |
| Run locally | `docker-compose up -d` |
| Push to main | `git push origin main` |
| Create release | `git tag v1.0.0 && git push origin v1.0.0` |

---

**Ready to deploy!** 🚀
