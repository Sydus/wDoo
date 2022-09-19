# -*- coding: utf-8 -*-
# Part of wdoo. See LICENSE file for full copyright and licensing details.
import logging

from wdoo import models
from wdoo.tools import populate

_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = "res.users"

    _populate_sizes = {
        'small': 10,
        'medium': 1000,
        'large': 10000,
    }

   

    def _populate_factories(self):
        return [
            ('active', populate.cartesian([True, False], [0.9, 0.1])),
            ('login', populate.constant('user_login_{counter}')),
            ('name', populate.constant('user_{counter}')),
        ]

    def _populate(self, size):
        self = self.with_context(no_reset_password=True)  # avoid sending reset password email
        return super(Users, self)._populate(size)
