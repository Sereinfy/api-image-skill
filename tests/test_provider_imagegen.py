import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from provider_imagegen.config import load_optional_image_provider_config
from provider_imagegen.outputs import resolve_base_path
from provider_imagegen.payloads import build_generation_payload


class ProviderConfigTests(unittest.TestCase):
    def load_toml(self, content: str, env: dict[str, str] | None = None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api-image.toml"
            path.write_text(content, encoding="utf-8")
            with patch.dict(os.environ, env or {}, clear=False):
                return load_optional_image_provider_config(path)

    def test_direct_api_key_takes_precedence(self):
        result = self.load_toml(
            'base_url = "https://provider.example/v1"\n'
            'api_key = "direct-key"\n'
            'api_key_env = "TEST_IMAGE_KEY"\n',
            {"TEST_IMAGE_KEY": "environment-key"},
        )
        self.assertEqual(result, ("direct-key", "https://provider.example/v1"))

    def test_api_key_env_is_used_when_direct_key_is_empty(self):
        result = self.load_toml(
            'base_url = "https://provider.example/v1"\n'
            'api_key = ""\n'
            'api_key_env = "TEST_IMAGE_KEY"\n',
            {"TEST_IMAGE_KEY": "environment-key"},
        )
        self.assertEqual(result, ("environment-key", "https://provider.example/v1"))

    def test_missing_file_key_falls_through(self):
        self.assertIsNone(self.load_toml('base_url = "https://provider.example/v1"\n'))


class OutputPathTests(unittest.TestCase):
    def test_explicit_output_format_controls_extension(self):
        self.assertEqual(resolve_base_path("result.png", "jpeg").name, "result.jpeg")
        self.assertEqual(resolve_base_path("result", "webp").name, "result.webp")

    def test_default_output_keeps_png_behavior(self):
        self.assertEqual(resolve_base_path("result").name, "result.png")
        self.assertEqual(resolve_base_path("result.png").name, "result.png")


class PayloadValidationTests(unittest.TestCase):
    @staticmethod
    def args(output_format: str):
        return Namespace(
            model="gpt-image-2",
            size="1024x1024",
            quality="high",
            n=1,
            background="transparent",
            output_format=output_format,
            output_compression=None,
            input_fidelity=None,
            moderation=None,
        )

    def test_gpt_image_2_transparent_png_is_allowed(self):
        payload = build_generation_payload(self.args("png"), "test")
        self.assertEqual(payload["background"], "transparent")

    def test_transparent_jpeg_is_rejected(self):
        with self.assertRaises(ValueError):
            build_generation_payload(self.args("jpeg"), "test")


if __name__ == "__main__":
    unittest.main()
