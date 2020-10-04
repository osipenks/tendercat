# -*- coding: utf-8 -*-

from odoo import models, fields


class DataLabel(models.Model):
    """ Labels of data objects """
    _name = "tender_cat.label"
    _description = "Label"

    name = fields.Char('Name', required=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Label name already exists!"),
    ]
