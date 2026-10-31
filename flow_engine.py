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


async def upload_reference(page, reference, log):
    """Handle existing inputs, lazy upload menus and native file choosers."""
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError
    reference = Path(reference).resolve()
    chooser_tasks = set()
    delivered = asyncio.Event()
    async def fill_chooser(chooser):
        try:
            await chooser.set_files(str(reference))
            delivered.set()
        except Exception as error:
            log('Hộp chọn tệp chưa nhận ảnh: ' + str(error))
    def on_chooser(chooser):
        task = asyncio.create_task(fill_chooser(chooser))
        chooser_tasks.add(task)
        task.add_done_callback(chooser_tasks.discard)
    async def fill_input():
        inputs = page.locator('input[type="file"]')
        candidates = []
        explicit_images = []
        for index in range(await inputs.count()):
            item = inputs.nth(index)
            accept = (await item.get_attribute('accept') or '').lower()
            if not accept or 'image' in accept or any(ext in accept for ext in ('.png', '.jpg', '.jpeg', '.webp')):
                candidates.append(item)
                if accept:
                    explicit_images.append(item)
        selected = explicit_images if explicit_images else candidates
        if len(selected) != 1:
            return False
        try:
            await selected[0].set_input_files(str(reference), timeout=5000)
            delivered.set()
            return True
        except Exception as error:
            log('Ô tải ảnh chưa nhận tệp: ' + str(error))
            return False
    page.on('filechooser', on_chooser)
    try:
        if await fill_input():
            return True
        editors = page.locator('textarea, [contenteditable="true"], [role="textbox"]').filter(visible=True)
        scope = page
        if await editors.count() == 1:
            composer = editors.locator('xpath=ancestor::*[.//button][1]')
            if await composer.count() == 1:
                scope = composer
        add_name = re.compile(r'^(\+|add|add image|add media|add reference|attach|attach file|upload|upload image|upload media|thêm|thêm ảnh|tải ảnh lên|tải lên)$', re.I)
        buttons = scope.get_by_role('button', name=add_name).filter(visible=True)
        if await buttons.count() != 1:
            buttons = scope.locator('button').filter(has_text=re.compile(r'^\s*(add|add_photo_alternate|attach_file|upload|\+)\s*$', re.I)).filter(visible=True)
        if await buttons.count() == 1:
            await buttons.click(timeout=5000)
            log('Đã mở nút thêm tệp trong vùng nhập prompt.')
        # A chooser or input may be created after opening the menu.
        for _ in range(12):
            if delivered.is_set() or await fill_input():
                return True
            upload_name = re.compile(r'^(upload|upload image|upload media|upload file|from computer|from device|choose file|tải lên|tải ảnh lên|tải tệp lên|từ máy tính)(\s.*)?$', re.I)
            choices = page.get_by_role('menuitem', name=upload_name).or_(page.get_by_role('button', name=upload_name)).filter(visible=True)
            if await choices.count() == 1:
                await choices.click(timeout=3000)
                break
            await asyncio.sleep(.2)
        for _ in range(15):
            if delivered.is_set() or await fill_input():
                return True
            await asyncio.sleep(.2)
        return False
    except PlaywrightTimeoutError:
        log('Nút tải ảnh chưa sẵn sàng. Có thể mở nút + thủ công rồi thử lại.')
        return False
    finally:
        page.remove_listener('filechooser', on_chooser)
        if chooser_tasks:
            await asyncio.gather(*list(chooser_tasks), return_exceptions=True)


async def create_video(reference, prompt, profile, output, channel, log, confirm,
                       stopped, launch=None, url=FLOW_URL, verify_image=None):
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
            await checkpoint('Mở dự án và chọn chế độ tạo video từ ảnh. Nếu Flow yêu cầu đăng nhập lại, bấm Dừng rồi bắt đầu lại để đăng nhập ở trình duyệt thông thường; không nhập mật khẩu trong cửa sổ tự động. Khi sẵn sàng, bấm Tiếp tục.')
            editors = page.locator('textarea, [contenteditable="true"], [role="textbox"]').filter(visible=True)
            if await editors.count() != 1:
                await checkpoint('Chưa xác định được duy nhất ô prompt. Mở màn hình tạo video trên Flow rồi bấm Tiếp tục.')
            while True:
                uploaded = await upload_reference(page, reference, log)
                if uploaded:
                    log('Đã gửi tệp ảnh. Cần xác nhận Flow đã gắn ảnh vào lượt tạo; việc gửi tệp chưa chứng minh tải lên thành công.')
                else:
                    log('Chưa gửi được ảnh. Hãy mở nút + cạnh ô prompt, chọn tải ảnh; ứng dụng sẽ thử lại sau khi bạn bấm Tiếp tục. Tệp: ' + str(reference))
                await checkpoint('Kiểm tra ảnh: mở nút + cạnh prompt nếu chưa có ảnh, xác nhận/cắt ảnh nếu Flow yêu cầu. Bấm Tiếp tục để xác nhận ảnh đã gắn, hoặc thử tải lại.')
                check = verify_image or confirm
                attached = await asyncio.to_thread(check, 'Bạn đã nhìn thấy ảnh tham chiếu của mình gắn cạnh ô prompt trên Flow chưa? Chỉ chọn Có khi ảnh đã xuất hiện; chọn Không để thử tải lại.')
                if stopped():
                    raise Stopped()
                if attached:
                    break
                log('Chưa xác nhận có ảnh; không điền prompt hoặc bấm tạo. Đang thử lại bước tải ảnh.')
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
