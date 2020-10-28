# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)


class TenderDocument(models.Model):
    _name = 'tender_cat.tender.document'
    _description = "Tender document"

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    document_type_id = fields.Many2one('tender_cat.tender.document.type', string='Document type', index=True)

    content_type = fields.Selection([('file', 'File'),
                                     ('code', 'Python code'),
                                     ], string='Content', required=True, default='file')

    file_content = fields.Binary('PDF')

    doc_date = fields.Date(string='Date', default=fields.Date.today())





