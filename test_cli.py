"""CLI 테스트 스크립트"""

from novel_total_processor.cli import app
from typer.testing import CliRunner

runner = CliRunner()

def test_status():
    """상태 확인 테스트"""
    result = runner.invoke(app, ["status"])
    print(result.stdout)
    assert result.exit_code == 0

def test_help():
    """도움말 테스트"""
    result = runner.invoke(app, ["--help"])
    print(result.stdout)
    assert result.exit_code == 0

if __name__ == "__main__":
    print("Testing CLI...")
    print("\n=== Help ===")
    test_help()
    print("\n=== Status ===")
    test_status()
    print("\n✅ CLI tests passed!")
