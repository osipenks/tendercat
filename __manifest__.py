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
        'views/tender_cat_views.xml',
        'views/tender_views.xml',
        'views/file_chunk_views.xml',
        'views/label_views.xml',
        'views/config_settings.xml',
        'views/templates.xml',
    ],

    'css': ['static/src/css/tender_cat.css'],


}
