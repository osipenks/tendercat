# -*- coding: utf-8 -*-
{
    'name': "Tender.cat",

    'summary': """App for AI powered tender evaluation and management, ver. 0.1""",
    'version': "1.0.1",

    'author': 'E+',
    'website': 'https://www.epls.dev',

    'category': 'Uncategorized',
    'version': '0.1',
    'application': True,
    'installable': True,

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/tender_views.xml',
        'views/file_chunk_views.xml',
        'views/data_label_views.xml',
        'views/data_model_views.xml',
        'views/config_settings.xml',
        'views/data_change_register_views.xml',
        'views/templates.xml',
        'wizard/data_dump_wizard_views.xml',
    ],

    'css': ['static/src/css/tender_cat.css'],


}
