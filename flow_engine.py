"""Browser operations shared by the desktop UI and local smoke tests."""
from pathlib import Path
import asyncio
import re

FLOW_URL = 'https://labs.google/fx/tools/flow'


def prepare_reference(source, seconds, destination):
    source = Path(source)
    if not source.is_file():
        raise ValueError('Không tìm thấy tệp đầu vào.')
    if source.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}:
        return source.resolve()
    if source.suffix.lower() not in {'.mp4', '.mov', '.mkv', '.avi', '.webm'}:
        raise ValueError('Định dạng chưa hỗ trợ. Chọn ảnh hoặc video MP4/MOV/MKV/AVI/WebM.')
    import cv2
    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise ValueError('Không đọc được video. Thử xuất video sang MP4 H.264.')
        fps = capture.get(cv2.CAP_PROP_FPS)
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if seconds < 0 or (fps > 0 and frames > 0 and seconds >= frames / fps):
            raise ValueError('Thời điểm lấy khung hình nằm ngoài video.')
        capture.set(cv2.CAP_PROP_POS_MSEC, seconds * 1000)
        ok, frame = capture.read()
        if not ok:
            raise ValueError('Không lấy được khung hình tại thời điểm đã chọn.')
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        encoded, buffer = cv2.imencode('.png', frame)
        if not encoded:
            raise ValueError('Không mã hóa được ảnh tham chiếu.')
        buffer.tofile(str(destination))
        return destination.resolve()
    finally:
        capture.release()


class Stopped(Exception):
    pass


async def create_video(reference, prompt, profile, output, channel, log, confirm,
                       stopped, launch=None, url=FLOW_URL):
    from playwright.async_api import async_playwright
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        if launch is None:
            context = await playwright.chromium.launch_persistent_context(
                str(profile), channel=channel, headless=False, accept_downloads=True)
        else:
            context = await launch(playwright)
        downloads = set()
        async def save_download(download):
            # Prevent download names from escaping the chosen output folder.
            filename = Path(download.suggested_filename.replace('\\', '/')).name
            destination = output / filename
            if destination.exists():
                import uuid
                destination = output / (destination.stem + '-' + uuid.uuid4().hex[:8] + destination.suffix)
            try:
                await download.save_as(str(destination))
                log('Đã lưu tệp: ' + str(destination))
            except Exception as error:
                log('Tải xuống chưa thành công: ' + str(error))
        def register(page):
            def on_download(download):
                task = asyncio.create_task(save_download(download))
                downloads.add(task)
                task.add_done_callback(downloads.discard)
            page.on('download', on_download)
        for page in context.pages:
            register(page)
        context.on('page', register)
        async def checkpoint(message):
            if stopped():
                raise Stopped()
            if not await asyncio.to_thread(confirm, message):
                raise Stopped()
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            log('Đang mở Google Flow…')
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            await checkpoint('Trong cửa sổ trình duyệt: đăng nhập Google, mở dự án và chọn chế độ tạo video từ ảnh. Sau đó bấm Tiếp tục trong ứng dụng.')
            editors = page.locator('textarea, [contenteditable="true"], [role="textbox"]').filter(visible=True)
            if await editors.count() != 1:
                await checkpoint('Chưa xác định được duy nhất ô prompt. Mở màn hình tạo video trên Flow rồi bấm Tiếp tục.')
            uploads = page.locator('input[type="file"]')
            if await uploads.count() == 1:
                try:
                    await uploads.set_input_files(str(reference))
                    log('Đã gửi ảnh tham chiếu tới ô tải lên.')
                except Exception:
                    log('Flow chưa nhận ảnh tự động; hãy tải ảnh thủ công.')
            else:
                log('Hãy tải ảnh tham chiếu thủ công trên Flow: ' + str(reference))
            await checkpoint('Kiểm tra ảnh tham chiếu trên Flow; tải ảnh thủ công hoặc xác nhận/cắt ảnh nếu cần. Chỉ bấm Tiếp tục khi ảnh đã sẵn sàng.')
            editors = page.locator('textarea, [contenteditable="true"], [role="textbox"]').filter(visible=True)
            if await editors.count() == 1:
                await editors.fill(prompt)
                log('Đã điền prompt.')
            else:
                await checkpoint('Không xác định được ô prompt. Sao chép prompt từ ứng dụng và dán vào Flow, sau đó bấm Tiếp tục.')
            await checkpoint('Kiểm tra ảnh, prompt, mô hình và số credit trên Flow. Bấm Tiếp tục để yêu cầu tạo video; thao tác này có thể dùng credit tài khoản của bạn.')
            buttons = page.get_by_role('button', name=re.compile(r'^(Generate|Create video|Tạo video|Tạo)$', re.I)).filter(visible=True)
            if await buttons.count() == 1 and await buttons.is_enabled():
                await buttons.click()
                log('Đã gửi thao tác tạo. Chưa xác minh Flow đã tạo video thành công.')
            else:
                log('Hãy bấm nút tạo trực tiếp trên Flow; giao diện chưa xác định được nút tự động.')
            await checkpoint('Chờ video trên Flow, rồi bấm nút tải video trong trình duyệt. Ứng dụng sẽ lưu các tệp tải xuống vào thư mục kết quả. Sau khi đã lưu xong, bấm Tiếp tục để kết thúc.')
            if downloads:
                await asyncio.gather(*list(downloads))
            log('Đã kết thúc phiên. Kiểm tra thư mục kết quả để xem các tệp đã tải.')
        finally:
            if downloads:
                await asyncio.gather(*list(downloads), return_exceptions=True)
            await context.close()
