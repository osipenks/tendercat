from odoo import fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    processing_folder = fields.Char(
        string="Processing folder",
        help="Defines the folder for processing files",
        config_parameter="tender_cat.processing_folder",
    )


