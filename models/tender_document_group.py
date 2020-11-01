# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)


class TenderDocumentGroup(models.Model):
    _name = 'tender_cat.tender.document.group'
    _description = "Tender document group"

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')
