"""SimpleFlow desktop entry point. No terminal needed in packaged Windows build."""
import asyncio
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid

from flow_engine import create_video, prepare_reference, Stopped


class App:
    def __init__(self, root):
        self.root = root
        root.title('SimpleFlow • Video từ ý tưởng')
        root.geometry('860x790')
        root.minsize(720, 700)
        self.events = queue.Queue()
        self.resume = threading.Event()
        self.cancel = threading.Event()
        self.running = False
        self.waiting = False
        self.reference = None
        self.media = tk.StringVar()
        self.seconds = tk.StringVar(value='0')
        self.browser = tk.StringVar(value='Microsoft Edge')
        self.output = tk.StringVar(value=str(Path.home() / 'Downloads' / 'SimpleFlow'))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 24, 'bold'))
        style.configure('Action.TButton', font=('Segoe UI', 11, 'bold'), padding=10)
        shell = ttk.Frame(root, padding=24)
        shell.pack(fill='both', expand=True)
        ttk.Label(shell, text='SimpleFlow', style='Title.TLabel').pack(anchor='w')
        ttk.Label(shell, text='Chọn ảnh hoặc video · Nhập prompt · Tạo trên Google Flow').pack(anchor='w', pady=(0, 18))
        ttk.Label(shell, text='1. Ảnh / video đầu vào').pack(anchor='w')
        row = ttk.Frame(shell)
        row.pack(fill='x', pady=5)
        ttk.Entry(row, textvariable=self.media).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Chọn tệp', command=self.pick_media).pack(side='left', padx=(8, 0))
        row = ttk.Frame(shell)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text='Lấy khung hình tại giây:').pack(side='left')
        ttk.Entry(row, textvariable=self.seconds, width=8).pack(side='left', padx=8)
        ttk.Label(row, text='Chỉ áp dụng với video').pack(side='left')
        ttk.Label(shell, text='Video được lấy một khung hình làm ảnh tham chiếu; không chuyển toàn bộ chuyển động sang Flow.', wraplength=760).pack(anchor='w', pady=(0, 10))
        ttk.Label(shell, text='2. Prompt tạo video').pack(anchor='w')
        self.prompt = tk.Text(shell, height=5, wrap='word', font=('Segoe UI', 11), undo=True)
        self.prompt.pack(fill='x', pady=6)
        ttk.Button(shell, text='Sao chép prompt', command=self.copy_prompt).pack(anchor='e')
        row = ttk.Frame(shell)
        row.pack(fill='x', pady=10)
        ttk.Label(row, text='Trình duyệt:').pack(side='left')
        ttk.Combobox(row, textvariable=self.browser, values=['Microsoft Edge', 'Google Chrome'], state='readonly', width=20).pack(side='left', padx=10)
        ttk.Label(shell, text='3. Thư mục kết quả').pack(anchor='w')
        row = ttk.Frame(shell)
        row.pack(fill='x', pady=6)
        ttk.Entry(row, textvariable=self.output).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Chọn', command=self.pick_output).pack(side='left', padx=8)
        ttk.Button(row, text='Mở thư mục', command=self.open_output).pack(side='left')
        row = ttk.Frame(shell)
        row.pack(fill='x', pady=(12, 8))
        self.start = ttk.Button(row, text='Mở Flow và bắt đầu', command=self.start_job, style='Action.TButton')
        self.start.pack(side='left')
        self.next = ttk.Button(row, text='Tiếp tục', command=self.continue_job, state='disabled')
        self.next.pack(side='left', padx=10)
        self.stop = ttk.Button(row, text='Dừng sau bước hiện tại', command=self.stop_job, state='disabled')
        self.stop.pack(side='left')
        self.status = tk.StringVar(value='Sẵn sàng. Cần Edge hoặc Chrome và tài khoản có quyền truy cập Flow.')
        ttk.Label(shell, textvariable=self.status, wraplength=760).pack(anchor='w', pady=8)
        self.logbox = tk.Text(shell, height=7, wrap='word', state='disabled', font=('Segoe UI', 9))
        self.logbox.pack(fill='both', expand=True)
        ttk.Label(shell, text='Đăng nhập trực tiếp trên Google. Không chia sẻ thư mục hồ sơ đăng nhập của ứng dụng.', wraplength=760).pack(anchor='w', pady=(10, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def pick_media(self):
        name = filedialog.askopenfilename(filetypes=[('Ảnh và video', '*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv *.avi *.webm'), ('Tất cả', '*.*')])
        if name:
            self.media.set(name)

    def pick_output(self):
        name = filedialog.askdirectory()
        if name:
            self.output.set(name)

    def open_output(self):
        try:
            path = Path(self.output.get()).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            if os.name == 'nt':
                os.startfile(str(path))
            else:
                messagebox.showinfo('Thư mục kết quả', str(path))
        except OSError as error:
            messagebox.showerror('Không mở được thư mục', str(error))

    def copy_prompt(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.prompt.get('1.0', 'end').strip())

    def start_job(self):
        if self.running:
            return
        try:
            source = Path(self.media.get())
            if not source.is_file():
                raise ValueError('Chọn một tệp ảnh hoặc video có sẵn trên máy.')
            prompt = self.prompt.get('1.0', 'end').strip()
            if not prompt:
                raise ValueError('Hãy nhập prompt tạo video.')
            seconds = float(self.seconds.get())
            import math
            if not math.isfinite(seconds) or seconds < 0:
                raise ValueError('Thời điểm khung hình phải là số giây không âm.')
            if not self.output.get().strip():
                raise ValueError('Chọn thư mục kết quả.')
            output = Path(self.output.get()).expanduser().resolve()
            output.mkdir(parents=True, exist_ok=True)
        except (ValueError, OSError) as error:
            messagebox.showerror('Kiểm tra đầu vào', str(error))
            return
        channel = 'msedge' if self.browser.get() == 'Microsoft Edge' else 'chrome'
        self.cancel.clear()
        self.running = True
        self.start.configure(state='disabled')
        self.stop.configure(state='normal')
        self.status.set('Đang chuẩn bị ảnh tham chiếu và mở trình duyệt…')
        threading.Thread(target=self.worker, args=(source, seconds, prompt, output, channel), daemon=True).start()

    def worker(self, source, seconds, prompt, output, channel):
        profile = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SimpleFlow' / 'browser-profile'
        def log(text):
            self.events.put(('log', text))
        def confirm(text):
            self.resume.clear()
            self.events.put(('wait', text))
            while not self.resume.wait(.2):
                if self.cancel.is_set():
                    return False
            return not self.cancel.is_set()
        try:
            reference = prepare_reference(source, seconds, output / 'references' / (uuid.uuid4().hex + '.png'))
            self.reference = reference
            log('Ảnh tham chiếu: ' + str(reference))
            profile.mkdir(parents=True, exist_ok=True)
            asyncio.run(create_video(reference, prompt, profile, output, channel, log, confirm, self.cancel.is_set))
        except Stopped:
            log('Đã dừng phiên.')
        except ModuleNotFoundError as error:
            self.events.put(('error', 'Bản đóng gói thiếu thành phần: ' + str(error) + '\nCần build lại bản EXE; không phải lỗi Edge.'))
        except Exception as error:
            self.events.put(('error', str(error) + '\nKiểm tra kết nối mạng, trình duyệt đã chọn và đóng phiên SimpleFlow khác nếu có.'))
        finally:
            self.events.put(('done', 'Phiên đã kết thúc. Xem nhật ký để biết kết quả.'))

    def continue_job(self):
        if self.waiting:
            self.waiting = False
            self.next.configure(state='disabled')
            self.status.set('Đang xử lý…')
            self.resume.set()

    def stop_job(self):
        self.cancel.set()
        self.resume.set()
        self.next.configure(state='disabled')
        self.status.set('Đang dừng sau thao tác hiện tại…')

    def poll(self):
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == 'wait':
                    if self.cancel.is_set():
                        continue
                    self.waiting = True
                    self.status.set(text)
                    self.next.configure(state='normal')
                elif kind == 'error':
                    messagebox.showerror('SimpleFlow', text)
                elif kind == 'done':
                    self.running = self.waiting = False
                    self.start.configure(state='normal')
                    self.next.configure(state='disabled')
                    self.stop.configure(state='disabled')
                    self.status.set(text)
                self.logbox.configure(state='normal')
                self.logbox.insert('end', text + '\n\n')
                self.logbox.see('end')
                self.logbox.configure(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.running:
            if messagebox.askyesno('Đang chạy', 'Dừng phiên trước khi đóng? Trình duyệt sẽ đóng sau thao tác hiện tại.'):
                self.stop_job()
                self.root.after(250, self.close_when_idle)
        else:
            self.root.destroy()

    def close_when_idle(self):
        if self.running:
            self.root.after(250, self.close_when_idle)
        else:
            self.root.destroy()


if __name__ == '__main__':
    import sys
    if '--self-test' in sys.argv:
        import cv2
        import playwright.async_api
        root = tk.Tk()
        root.withdraw()
        App(root)
        root.update_idletasks()
        root.destroy()
    else:
        root = tk.Tk()
        App(root)
        root.mainloop()
