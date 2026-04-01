"""Auto-scheduling setup for weekly lottery data collection and prediction.

Creates a Windows Task Scheduler task that runs every Thursday at 22:00
(after the weekly draw) to collect new data and generate predictions.

Usage:
    python schedule_task.py install     Register the scheduled task
    python schedule_task.py uninstall   Remove the scheduled task
    python schedule_task.py status      Check if the task exists
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME = "LotteryAnalysis_WeeklyUpdate"
PROJECT_DIR = Path(__file__).parent.resolve()
PYTHON_EXE = Path(sys.executable).resolve()
MAIN_SCRIPT = PROJECT_DIR / "main.py"


def install_task() -> None:
    """Register the weekly scheduled task in Windows Task Scheduler.

    Runs every Thursday at 22:00 KST using ``python main.py all``.
    """
    command = (
        f'schtasks /Create /TN "{TASK_NAME}" '
        f'/TR "\\"{PYTHON_EXE}\\" \\"{MAIN_SCRIPT}\\" all" '
        f'/SC WEEKLY /D THU /ST 22:00 '
        f'/F /RL HIGHEST'
    )
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] 스케줄 등록 완료: 매주 목요일 22:00 실행")
        print(f"     작업 이름: {TASK_NAME}")
        print(f"     실행 명령: python main.py all")
    else:
        print(f"[ERROR] 스케줄 등록 실패:")
        print(f"  {result.stderr.strip()}")
        print("  관리자 권한으로 다시 실행해주세요.")


def uninstall_task() -> None:
    """Remove the scheduled task from Windows Task Scheduler."""
    command = f'schtasks /Delete /TN "{TASK_NAME}" /F'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] 스케줄 삭제 완료: {TASK_NAME}")
    else:
        print(f"[ERROR] 스케줄 삭제 실패: {result.stderr.strip()}")


def check_status() -> None:
    """Check if the scheduled task currently exists."""
    command = f'schtasks /Query /TN "{TASK_NAME}" /FO LIST'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[OK] 스케줄이 등록되어 있습니다.")
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    else:
        print(f"[INFO] 등록된 스케줄이 없습니다.")


def main() -> None:
    """Parse CLI arguments and execute requested command."""
    parser = argparse.ArgumentParser(
        description="연금복권720+ 주간 자동 업데이트 스케줄러",
    )
    parser.add_argument(
        "command",
        choices=["install", "uninstall", "status"],
        help="install: 등록 / uninstall: 삭제 / status: 확인",
    )
    args = parser.parse_args()

    if args.command == "install":
        install_task()
    elif args.command == "uninstall":
        uninstall_task()
    elif args.command == "status":
        check_status()


if __name__ == "__main__":
    main()
