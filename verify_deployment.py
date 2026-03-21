#!/usr/bin/env python
"""GitHub Pre-Deployment Verification Script"""

import os
import sys
from pathlib import Path

class Checker:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.root = Path(__file__).parent

    def check(self, name: str, condition: bool, error_msg: str = "") -> bool:
        if condition:
            print(f"[OK] {name}")
            self.passed += 1
        else:
            print(f"[FAIL] {name}")
            if error_msg:
                print(f"       > {error_msg}")
            self.failed += 1
        return condition

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"         {self.failed}/{total} failed")
        print(f"{'='*60}\n")
        return 0 if self.failed == 0 else 1

def main():
    checker = Checker()

    print("\nNexaCommerce Analytics - Pre-Deployment Verification\n")

    # 1. File Structure
    print("1. File Structure")
    print("-" * 60)

    required_files = [
        "Dockerfile",
        "docker-compose.yml",
        "requirements.txt",
        "README.md",
        ".env.example",
        ".gitignore",
        "run_pipeline.py",
        "pytest.ini",
        ".github/workflows/ci-cd.yml",
        ".github/workflows/release.yml",
    ]

    for file in required_files:
        path = checker.root / file
        checker.check(f"File exists: {file}", path.exists(),
                     f"Missing: {path}")

    required_dirs = [
        "config",
        "src",
        "src/dashboard",
        "src/ab_testing",
        "tests",
        "dbt",
        "sql",
    ]

    for dir_name in required_dirs:
        path = checker.root / dir_name
        checker.check(f"Directory exists: {dir_name}", path.is_dir(),
                     f"Missing: {path}")

    # 2. Git Configuration
    print("\n2. Git Configuration")
    print("-" * 60)

    gitignore_path = checker.root / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        checker.check(".gitignore excludes .env", ".env" in content)
        checker.check(".gitignore excludes venv", "venv" in content)
        checker.check(".gitignore excludes __pycache__", "__pycache__" in content)

    # 3. Code Quality
    print("\n3. Code Quality")
    print("-" * 60)

    # Check for hardcoded secrets
    has_secrets = False
    try:
        for py_file in checker.root.glob("src/**/*.py"):
            content = py_file.read_text()
            if "password" in content.lower() or "secret" in content.lower():
                has_secrets = True
                break
    except:
        pass

    checker.check("No obvious hardcoded secrets in code", not has_secrets)

    # 4. Docker Configuration
    print("\n4. Docker Configuration")
    print("-" * 60)

    dockerfile = checker.root / "Dockerfile"
    if dockerfile.exists():
        content = dockerfile.read_text()
        checker.check("Dockerfile has production stage", "as production" in content)
        checker.check("Dockerfile has development stage", "as development" in content)
        checker.check("Dockerfile has healthcheck", "HEALTHCHECK" in content)

    dc_file = checker.root / "docker-compose.yml"
    if dc_file.exists():
        content = dc_file.read_text()
        checker.check("docker-compose has services", "services:" in content)
        checker.check("docker-compose has postgres", "postgres" in content)
        checker.check("docker-compose has redis", "redis" in content)

    # 5. GitHub Actions Workflows
    print("\n5. GitHub Actions Workflows")
    print("-" * 60)

    workflows = [
        ".github/workflows/ci-cd.yml",
        ".github/workflows/release.yml",
    ]

    for workflow in workflows:
        path = checker.root / workflow
        checker.check(f"Workflow exists: {workflow}", path.exists())

    # 6. Python Dependencies
    print("\n6. Python Dependencies")
    print("-" * 60)

    req_file = checker.root / "requirements.txt"
    if req_file.exists():
        content = req_file.read_text()
        essential = ["pandas", "streamlit", "plotly", "pytest"]
        for pkg in essential:
            has_pkg = any(pkg.lower() in line.lower() for line in content.split("\n"))
            checker.check(f"Requirement includes {pkg}", has_pkg)

    # 7. Configuration Files
    print("\n7. Configuration Files")
    print("-" * 60)

    env_example = checker.root / ".env.example"
    if env_example.exists():
        content = env_example.read_text()
        checker.check(".env.example has DB_HOST", "DB_HOST" in content)
        checker.check(".env.example has REDIS_HOST", "REDIS_HOST" in content)

    # 8. Tests
    print("\n8. Test Suite")
    print("-" * 60)

    test_dir = checker.root / "tests"
    has_tests = test_dir.exists() and any(test_dir.glob("test_*.py"))
    checker.check("Test files exist", has_tests)

    pytest_ini = checker.root / "pytest.ini"
    checker.check("pytest.ini exists", pytest_ini.exists())

    # 9. Documentation
    print("\n9. Documentation")
    print("-" * 60)

    readme = checker.root / "README.md"
    checker.check("README.md exists", readme.exists())

    gh_deploy = checker.root / "GITHUB_DEPLOYMENT.md"
    checker.check("GITHUB_DEPLOYMENT.md exists", gh_deploy.exists())

    # Summary
    exit_code = checker.summary()

    if exit_code == 0:
        print("SUCCESS: All checks passed! Ready for GitHub deployment.\n")
        print("Next steps:")
        print("1. git add .")
        print("2. git commit -m 'initial commit'")
        print("3. git remote add origin https://github.com/YOUR_ORG/nexacommerce-analytics.git")
        print("4. git branch -M main")
        print("5. git push -u origin main")
        print()
    else:
        print("FAILURE: Some checks failed. Please fix the issues above.\n")
        print("For details, see: GITHUB_DEPLOYMENT.md")
        print()

    return exit_code

if __name__ == "__main__":
    sys.exit(main())
