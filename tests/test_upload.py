import os
from pathlib import Path
import shutil
import tempfile
import unittest
import asyncio
from unittest.mock import patch

from playwright.async_api import async_playwright, Page
from flow_engine import upload_reference, create_video


class UploadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.name == 'nt':
            from browser_login import find_browser
            executable = str(find_browser('msedge'))
        else:
            executable = shutil.which('chromium')
        if not executable:
            self.skipTest('Installed Chromium or Edge required')
        self.temp = tempfile.TemporaryDirectory()
        self.reference = Path(self.temp.name) / 'ảnh.png'
        self.reference.write_bytes(b'fixture')
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(executable_path=executable, headless=True)
        self.page = await self.browser.new_page()

    async def asyncTearDown(self):
        if hasattr(self, 'browser'):
            await self.browser.close()
            await self.playwright.stop()
            self.temp.cleanup()

    async def assert_uploaded(self):
        self.assertTrue(await upload_reference(self.page, self.reference, lambda _: None))
        self.assertEqual(await self.page.locator('input[type=file][accept="image/*"]').evaluate('(e)=>e.files[0].name'), 'ảnh.png')

    async def test_hidden_image_input_with_other_video_input(self):
        await self.page.set_content('<input type=file accept="video/*"><input type=file accept="image/*" hidden>')
        await self.assert_uploaded()

    async def test_plus_creates_input_lazily_in_composer(self):
        await self.page.set_content('''<button aria-label="add">Sidebar</button><section><textarea></textarea><button aria-label="add" onclick="this.insertAdjacentHTML('afterend', '&lt;input type=file accept=&quot;image/*&quot; hidden&gt;')">+</button></section>''')
        await self.assert_uploaded()

    async def test_menu_opens_native_file_chooser(self):
        await self.page.set_content('''<section><textarea></textarea><button aria-label="add" onclick="document.getElementById('menu').hidden=false">+</button></section><div id=menu hidden><button role=menuitem onclick="let f=document.createElement('input'); f.type='file'; f.accept='image/*'; f.hidden=true; document.body.appendChild(f); f.click()">Upload image</button></div>''')
        await self.assert_uploaded()

    async def test_ambiguous_inputs_are_not_filled(self):
        await self.page.set_content('<input type=file accept="image/*"><input type=file accept="image/*">')
        self.assertFalse(await upload_reference(self.page, self.reference, lambda _: None))
        self.assertEqual(await self.page.locator('input').evaluate_all('(items)=>items.reduce((n,e)=>n+e.files.length,0)'), 0)

    async def test_prompt_and_generation_wait_for_image_confirmation(self):
        page = self.page
        loop = asyncio.get_running_loop()
        checked = []
        async def goto(*args, **kwargs):
            await page.set_content('<input type=file accept="image/*"><textarea></textarea><button onclick="document.body.dataset.generated=1">Generate</button>')
        async def verify_empty():
            self.assertEqual(await page.locator('textarea').input_value(), '')
            self.assertIsNone(await page.locator('body').get_attribute('data-generated'))
        def verify_image(text):
            asyncio.run_coroutine_threadsafe(verify_empty(), loop).result(timeout=10)
            checked.append(text)
            return len(checked) == 2
        async def verify_done():
            self.assertEqual(await page.locator('textarea').input_value(), 'test prompt')
            self.assertEqual(await page.locator('body').get_attribute('data-generated'), '1')
        def confirm(text):
            if text.startswith('Chờ video'):
                asyncio.run_coroutine_threadsafe(verify_done(), loop).result(timeout=10)
            return True
        async def launch(playwright):
            return page.context
        with patch.object(Page, 'goto', goto):
            await create_video(self.reference, 'test prompt', Path(self.temp.name) / 'profile',
                               Path(self.temp.name) / 'output', 'msedge', lambda _: None,
                               confirm, lambda: False, launch=launch, verify_image=verify_image)
        self.assertEqual(len(checked), 2)
