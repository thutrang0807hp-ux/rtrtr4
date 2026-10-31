import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from flow_engine import prepare_reference


class ReferenceTests(unittest.TestCase):
    def test_existing_image(self):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / 'ảnh.png'
            image.write_bytes(b'fixture')
            self.assertEqual(prepare_reference(image, 0, Path(d) / 'unused.png'), image.resolve())

    def test_video_frame_and_unicode_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            video = root / 'fixture.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 10, (64, 48))
            self.assertTrue(writer.isOpened())
            for _ in range(20):
                writer.write(np.full((48, 64, 3), (20, 100, 220), dtype=np.uint8))
            writer.release()
            destination = root / 'ảnh tham chiếu' / 'frame.png'
            self.assertEqual(prepare_reference(video, .5, destination), destination.resolve())
            decoded = cv2.imdecode(np.fromfile(destination, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(decoded.shape, (48, 64, 3))
            self.assertLess(abs(float(decoded[10, 10, 2]) - 220), 8)
            for seconds in [-1, 99]:
                with self.assertRaises(ValueError):
                    prepare_reference(video, seconds, destination)

    def test_missing_and_unsupported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                prepare_reference(root / 'missing.mp4', 0, root / 'x.png')
            file = root / 'text.txt'
            file.write_text('test')
            with self.assertRaises(ValueError):
                prepare_reference(file, 0, root / 'x.png')


if __name__ == '__main__':
    unittest.main()
