# -*- coding: utf-8 -*-
# Part of wdoo. See LICENSE file for full copyright and licensing details.

RELEASE_LEVELS = [ALPHA, BETA, RELEASE_CANDIDATE, FINAL] = ['alpha', 'beta', 'candidate', 'final']
RELEASE_LEVELS_DISPLAY = {ALPHA: ALPHA,
                          BETA: BETA,
                          RELEASE_CANDIDATE: 'rc',
                          FINAL: ''}

# version_info format: (MAJOR, MINOR, MICRO, RELEASE_LEVEL, SERIAL)
# inspired by Python's own sys.version_info, in order to be
# properly comparable using normal operarors, for example:
#  (6,1,0,'beta',0) < (6,1,0,'candidate',1) < (6,1,0,'candidate',2)
#  (6,1,0,'candidate',2) < (6,1,0,'final',0) < (6,1,2,'final',0)
version_info = (0, 0, 1, BETA, 0, '')
version = '.'.join(str(s) for s in version_info[:2]) + RELEASE_LEVELS_DISPLAY[version_info[3]] + str(version_info[4] or '') + version_info[5]
series = serie = major_version = '.'.join(str(s) for s in version_info[:2])

product_name = 'Wdoo'
description = 'Wdoo Server'
long_desc = '''wdoo is a web application framework. Technical features include
a distributed server, an object database, a dynamic GUI and XML-RPC interfaces.
'''
classifiers = """Development Status :: 5 - Beta
License :: OSI Approved :: BSD 3-Clause License
Programming Language :: Python
"""
url = 'https://www.sydus.it'
author = 'Sydus srls, Odoo S.A.'
author_email = 'info@sydus.it'
license = 'BSD 3-Clause'

nt_service_name = "wdoo-server-" + series.replace('~','-')