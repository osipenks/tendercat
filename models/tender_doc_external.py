# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging


_logger = logging.getLogger(__name__)


class TenderDocExternal(models.Model):
    _name = 'tender_cat.tender.doc.external'
    _description = "Tender doc external"

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Detailed description')

    document_group_id = fields.Many2one('tender_cat.tender.document.group', string='Document group', index=True)

    def get_desc(self):
        desc = _('External document')
        desc += (', ' + self.description) if self.description else ''
        return desc
