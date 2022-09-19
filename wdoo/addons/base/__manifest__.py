# -*- coding: utf-8 -*-
# Part of wdoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Base',
    'version': '1.3',
    'category': 'Hidden',
    'description': """
The kernel of wdoo, needed for all installation.
===================================================
""",
    'depends': [],
    'data': [

        'data/res.lang.csv',
        'data/res_lang_data.xml',
        'data/res_users_data.xml',
        'security/base_groups.xml',
        'security/base_security.xml',
        'views/base_menus.xml',
        'views/decimal_precision_views.xml',
        'views/res_config_views.xml',
        'views/ir_actions_views.xml',
        'views/ir_asset_views.xml',
        'views/ir_config_parameter_views.xml',
        'views/ir_cron_views.xml',
        'views/ir_cron_trigger_views.xml',
        'views/ir_filters_views.xml',
        'views/ir_model_views.xml',
        'views/ir_attachment_views.xml',
        'views/ir_rule_views.xml',
        'views/ir_sequence_views.xml',
        'views/ir_translation_views.xml',
        'views/ir_ui_menu_views.xml',
        'views/ir_ui_view_views.xml',
        'views/ir_default_views.xml',
        'data/ir_cron_data.xml',
        'views/ir_logging_views.xml',
        'views/ir_module_views.xml',
        'data/ir_module_category_data.xml',
        'wizard/base_module_update_views.xml',
        'wizard/base_language_install_views.xml',
        'wizard/base_import_language_views.xml',
        'wizard/base_module_upgrade_views.xml',
        'wizard/base_module_uninstall_views.xml',
        'wizard/base_export_language_views.xml',
        'wizard/base_update_translations_views.xml',
        'data/ir_actions_data.xml',
  
        'views/ir_profile_views.xml',
        'views/res_lang_views.xml',
        'views/res_users_views.xml',
        'views/ir_property_views.xml',
        'views/res_config_settings_views.xml',
        'security/ir.model.access.csv',
    ],
    'test': [],
    'installable': True,
    'auto_install': True,
    'post_init_hook': 'post_init',
    'license': 'LGPL-3',
}
