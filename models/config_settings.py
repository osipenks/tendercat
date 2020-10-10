from odoo import fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    processing_folder = fields.Char(
        string="Processing folder",
        help="Defines the folder for processing files",
        config_parameter="tender_cat.processing_folder",
    )

    req_docs_data_model = fields.Many2one('tender_cat.data.model',
                                          string="Data model to find documents required for tender",
                                          help="Data model to find documents required for tender",
                                          config_parameter="tender_cat.req_docs_data_model",
                                          )



