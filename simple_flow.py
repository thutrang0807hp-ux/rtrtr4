"""Simple Flow for Windows. Build with build_windows.bat."""
import argparse
import asyncio
import os
from pathlib import Path
import re
import sys


def select_image():
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        return filedialog.askopenfilename(
            title='Chọn ảnh tham chiếu',
            filetypes=[('Images', '*.png *.jpg *.jpeg *.webp'), ('All files', '*.*')])
    finally:
        root.destroy()


async def pause(message):
    await asyncio.to_thread(input, message + '\nNhấn Enter để tiếp tục...')


async def run(image, prompt, url, channel):
    from playwright.async_api import async_playwright
    # Keep Google login outside the executable and repository.
    profile = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'SimpleFlow' / 'browser-profile'
    profile.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile), channel=channel, headless=False,
            accept_downloads=True)
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await pause('Đăng nhập Google, mở dự án và chọn chế độ tạo video từ ảnh trên Flow.')
            uploads = page.locator('input[type="file"]')
            if await uploads.count():
                await uploads.first.set_input_files(str(image.resolve()))
                await pause('Kiểm tra ảnh đã tải xong; xác nhận/cắt ảnh trên Flow nếu được yêu cầu.')
            else:
                await pause('Hãy tải ảnh tham chiếu thủ công trên Flow: ' + str(image.resolve()))
            editor = page.locator('textarea, [contenteditable="true"], [role="textbox"]').filter(visible=True).first
            await editor.fill(prompt, timeout=30000)
            await pause('Đã điền prompt. Kiểm tra ảnh, mô hình và chi phí trên Flow trước khi tạo video.')
            generate = page.get_by_role('button', name=re.compile(
                r'^(Generate|Create video|Tạo video|Tạo)$', re.I)).filter(visible=True)
            if await generate.count() == 1:
                await generate.click()
                print('Đã bấm tạo. Chờ kết quả và tải video trong trình duyệt.')
            else:
                print('Không xác định được duy nhất nút tạo. Hãy bấm tạo trực tiếp trên Flow.')
            await pause('Nhấn Enter khi đã tải video xong để đóng trình duyệt.')
        finally:
            await context.close()


def main():
    parser = argparse.ArgumentParser(description='Simple Flow video assistant')
    parser.add_argument('--image')
    parser.add_argument('--prompt')
    parser.add_argument('--url', default='https://labs.google/fx/tools/flow')
    parser.add_argument('--channel', choices=['msedge', 'chrome'], default='msedge')
    args = parser.parse_args()
    image_name = args.image or select_image()
    if not image_name:
        print('Đã hủy chọn ảnh.')
        return 0
    image = Path(image_name)
    if not image.is_file():
        raise ValueError('Không tìm thấy ảnh: ' + str(image))
    prompt = args.prompt or input('Nhập prompt tạo video: ').strip()
    if not prompt:
        raise ValueError('Prompt không được để trống.')
    asyncio.run(run(image, prompt, args.url, args.channel))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('\nLỗi:', exc)
        print('Cần cài Microsoft Edge; hoặc chạy với --channel chrome nếu dùng Google Chrome.')
        print('Đóng cửa sổ SimpleFlow khác nếu hồ sơ trình duyệt đang được sử dụng.')
        input('Nhấn Enter để thoát...')
        sys.exit(1)
