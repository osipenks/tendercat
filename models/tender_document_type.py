# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)


class TenderDocumentType(models.Model):
    _name = 'tender_cat.tender.document.type'
    _description = "Tender document type"

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')
