import subprocess
from pathlib import Path

REPO_PATH = Path(__file__).parent / "repo"

def reset_repo():
    subprocess.run(["git", "checkout", "--", "."], cwd=REPO_PATH, check=True, capture_output=True)
    subprocess.run(["git", "clean", "-fd"], cwd=REPO_PATH, check=True, capture_output=True)

def ensure_repo_clean(repo_path: Path) -> None:
    """Verify a real-world repo has no modifications, reset if needed."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        subprocess.run(
            ["git", "checkout", "--", "."],
            cwd=str(repo_path),
            check=True,
        )
        subprocess.run(
            ["git", "clean", "-fd"],
            cwd=str(repo_path),
            check=True,
        )

if __name__ == "__main__":
    reset_repo()
    print(f"Reset {REPO_PATH}")
