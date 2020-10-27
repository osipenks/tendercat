# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)


class TenderProposal(models.Model):
    _name = 'tender_cat.tender.proposal'
    _description = "Tender proposal"

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    tender_id = fields.Many2one('tender_cat.tender', index=True, ondelete='cascade', string='Tender', required=True)




