import os
import shutil
import tempfile
import unittest
from core.collision_resolver import CollisionResolver
from core.metadata_engine import MetadataEngine
from core.image_engine import ImageEngine

class TestCollisionAndPackaging(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_media_")

    def tearDown(self):
        if os.path.isdir(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_collision_resolver(self):
        # Create colliding stems: IMG_0001.JPG and IMG_0001.MOV
        f1 = os.path.join(self.test_dir, "IMG_0001.JPG")
        f2 = os.path.join(self.test_dir, "IMG_0001.MOV")
        with open(f1, "w") as f: f.write("dummy photo")
        with open(f2, "w") as f: f.write("dummy video")

        resolver = CollisionResolver(self.test_dir)
        collisions = resolver.find_collisions()
        self.assertEqual(len(collisions), 1)
        self.assertIn("img_0001", collisions)

        # Resolve
        stems_res, files_renamed = resolver.resolve_collisions()
        self.assertEqual(stems_res, 1)
        self.assertEqual(files_renamed, 1)

        # Verify collisions are 0
        self.assertEqual(len(resolver.find_collisions()), 0)
        remaining_files = os.listdir(self.test_dir)
        self.assertIn("IMG_0001.JPG", remaining_files)
        self.assertIn("IMG_0001_g1.MOV", remaining_files)

    def test_quarantine_corrupt_files(self):
        # Create a 0-byte file and a normal file
        corrupt_file = os.path.join(self.test_dir, "CORRUPT.PNG")
        normal_file = os.path.join(self.test_dir, "NORMAL.JPG")
        with open(corrupt_file, "w") as f: pass  # 0 bytes
        with open(normal_file, "w") as f: f.write("content")

        me = MetadataEngine()
        quarantined = me.quarantine_corrupt_files(self.test_dir)
        self.assertEqual(len(quarantined), 1)
        self.assertIn("CORRUPT.PNG", [os.path.basename(p) for p in quarantined])
        self.assertFalse(os.path.exists(corrupt_file))
        self.assertTrue(os.path.exists(normal_file))

    def test_image_engine_zero_byte_guard(self):
        corrupt_file = os.path.join(self.test_dir, "EMPTY.JPG")
        target_file = os.path.join(self.test_dir, "OUT.JPG")
        with open(corrupt_file, "w") as f: pass

        me = MetadataEngine()
        ie = ImageEngine(me)
        res = ie.process_image(corrupt_file, target_file)
        self.assertEqual(res.status, "FAILED")
        self.assertIn("corrupted", res.error_message.lower())

if __name__ == "__main__":
    unittest.main()
