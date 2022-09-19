# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
import base64

from PIL import Image

from wdoo.tests.common import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestImage(HttpCase):
    def test_01_content_image_resize_placeholder(self):
        """The goal of this test is to make sure the placeholder image is
        resized appropriately depending on the given URL parameters."""

        # CASE: resize placeholder, given size but original ratio is always kept
        response = self.url_open('/web/image/0/200x150')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (150, 150))

        # CASE: resize placeholder to 128
        response = self.url_open('/web/image/fake/0/image_128')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (128, 128))

        # CASE: resize placeholder to 256
        response = self.url_open('/web/image/fake/0/image_256')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (256, 256))

        # CASE: resize placeholder to 1024 (but placeholder image is too small)
        response = self.url_open('/web/image/fake/0/image_1024')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (256, 256))

        # CASE: no size found, use placeholder original size
        response = self.url_open('/web/image/fake/0/image_no_size')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (256, 256))
