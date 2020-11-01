# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging


_logger = logging.getLogger(__name__)


class TenderDocReport(models.Model):
    _name = 'tender_cat.tender.doc.report'
    _description = "Tender doc report"

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Detailed description')

    document_group_id = fields.Many2one('tender_cat.tender.document.group', string='Document group', index=True)

    report_class = fields.Selection([('ReportDocRegister', _('Register of documents')),
                                     ('ReportInfAboutCompany', _('Information about the company')),
                                     ], string='Report class', required=True, default='ReportDocRegister')

    def get_desc(self):
        desc = _('Report')
        desc += (', ' + self.description) if self.description else ''
        return desc
