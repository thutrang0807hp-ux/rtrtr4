"""Open the installed browser normally for user-controlled Google sign-in."""
import os
from pathlib import Path
import subprocess

from flow_engine import FLOW_URL, Stopped


def find_browser(channel):
    relative = {'msedge': Path('Microsoft/Edge/Application/msedge.exe'),
                'chrome': Path('Google/Chrome/Application/chrome.exe')}[channel]
    candidates = [Path(os.environ[name]) / relative
                  for name in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA')
                  if os.environ.get(name)]
    # App Paths also covers installations in custom locations.
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for access in (winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
                           winreg.KEY_READ | winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\' + relative.name, 0, access) as key:
                        value, _ = winreg.QueryValueEx(key, None)
                        candidates.append(Path(value.strip('"')))
                except OSError:
                    continue
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError('Không tìm thấy trình duyệt đã chọn. Cài Microsoft Edge hoặc Google Chrome, hoặc chọn trình duyệt còn lại trong ứng dụng.')


def sign_in_normally(channel, profile, log, confirm, stopped, opener=None):
    if stopped():
        raise Stopped()
    executable = find_browser(channel)
    profile = Path(profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    process = (opener or subprocess.Popen)([
        str(executable), '--user-data-dir=' + str(profile),
        '--no-first-run', '--disable-background-mode', '--new-window', FLOW_URL])
    log('Đã mở trình duyệt thông thường để đăng nhập, chưa chạy Playwright.')
    while True:
        accepted = confirm('ĐĂNG NHẬP: Trong trình duyệt vừa mở, đăng nhập Google và kiểm tra mở được Flow. Sau đó ĐÓNG tất cả cửa sổ trình duyệt SimpleFlow vừa mở, rồi bấm Tiếp tục. Nếu vẫn bị Google từ chối, bấm Dừng; ứng dụng không thể bỏ qua yêu cầu bảo mật của Google.')
        if not accepted or stopped():
            log('Đã dừng; cửa sổ đăng nhập thông thường do bạn tự đóng.')
            raise Stopped()
        if process.poll() is not None:
            return
        log('Trình duyệt đăng nhập vẫn đang chạy. Hãy đóng cửa sổ đó trước khi bấm Tiếp tục.')
