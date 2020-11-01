# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging


_logger = logging.getLogger(__name__)


class TenderDocument(models.Model):
    _name = 'tender_cat.tender.document'
    _description = "Tender document"

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Detailed description')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    document_group_id = fields.Many2one('tender_cat.tender.document.group', string='Document group', index=True)

    content_type = fields.Selection([('file', _('File')),
                                     ('code', _('Python code')),
                                     ], string='Content', required=True, default='file')

    file_content = fields.Binary('PDF')

    show_upload_file = fields.Boolean(default=True)

    doc_date = fields.Date(string='Date', default=fields.Date.today())

    doc_class = fields.Selection([('doc_copy', _('Document copy')),
                                  ('doc_report', _('Report')),
                                  ('doc_template', _('Document template')),
                                  ('doc_external', _('External document')),
                                  ], string='Type', required=True, default='doc_copy')

    _order = 'doc_date desc'

    @api.onchange('file_content', 'doc_class')
    def _onchange_file_content(self):
        self.show_upload_file = self.file_content is False and self.doc_class == 'doc_copy'

    def write(self, vals):

        # Clear file content, if it isn't doc_copy
        doc_class = vals.get('doc_class', 0)
        if doc_class and not doc_class == 'doc_copy':
            vals.update({'file_content': False})

        res = super(TenderDocument, self).write(vals) if vals else True
        return res

    def get_desc(self):
        desc = _('Document copy')
        desc += (_(', дата') + str(self.doc_date)) if self.doc_date else ''
        return desc
