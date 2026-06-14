"""金十快讯后台服务 - 保活脚本
检查服务是否在运行，未运行则启动。
AI 每次处理相关任务前调用此脚本确保服务在线。
"""
import io
import os
import subprocess
import sys

if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jin10_subscriber.py')


def is_running():
    """检查 jin10_subscriber.py 是否已在运行"""
    if os.name == 'nt':
        try:
            result = subprocess.run(
                ['powershell', '-Command',
                 "Get-WmiObject Win32_Process -Filter \"name='pythonw.exe'\" | "
                 "Where-Object { $_.CommandLine -like '*jin10_subscriber*' } | "
                 "Measure-Object | Select-Object -ExpandProperty Count"],
                capture_output=True, text=True, timeout=10
            )
            count = result.stdout.strip()
            return count and int(count) > 0
        except Exception:
            return False

    result = subprocess.run(
        ['pgrep', '-f', 'jin10_subscriber.py'],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def start():
    """启动后台服务"""
    if os.name == 'nt':
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen(
            ['pythonw.exe', SCRIPT],
            cwd=os.path.dirname(SCRIPT),
            creationflags=creationflags,
        )
        return

    subprocess.Popen(
        [sys.executable, SCRIPT],
        cwd=os.path.dirname(SCRIPT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


if __name__ == '__main__':
    if is_running():
        print('jin10_subscriber 已在运行')
    else:
        print('jin10_subscriber 未运行，正在启动...')
        start()
        print('已启动')
