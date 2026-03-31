
{
    'name': "Odoo OneDrive Connector",
    'version': '18.0.2.0.1',
    'category': 'Extra Tools',
    'author': "JD DEVS",
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/onedrive_config.xml',
        'views/users.xml',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
    'images': ['static/description/assets/screenshots/banner.png'],
    'icon': "/odoo_onedrive_connector/static/description/icon.png",
}
