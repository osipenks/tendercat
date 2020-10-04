# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from . import data_dump
import logging

_logger = logging.getLogger(__name__)


class DataDumpWizard(models.TransientModel):
    """
    Dump data for data models
    """
    _name = 'tender_cat.data.dump.wizard'
    _description = 'Dump data for data models'

    data_model_id = fields.Many2one('tender_cat.data.model', string='Data model')
    user_id = fields.Many2one('res.users', 'User', index=True)

    @api.model
    def default_get(self, default_fields):
        result = super(DataDumpWizard, self).default_get(default_fields)
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.data.model':
            active_id = self._context.get('active_id')
            if active_id:
                result['data_model_id'] = self.env['tender_cat.data.model'].browse(active_id).id
        else:
            if 'data_model_id' in default_fields:
                found_ids = self.env['tender_cat.data.model'].search([('use_data_dumping', '=', 1)])
                if found_ids:
                    result['data_model_id'] = found_ids[0].id
        return result

    def action_make_data_dump(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return ''
        # active_ids = self.ids, active_model = 'tender_cat.data.model', active_id = self.id
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.data.model':
            pass

        return {
            'name': _('Make data dump'),
            'res_model': 'tender_cat.data.dump.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('tender_cat.view_tender_cat_data_dump_wizard_form').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def make_data_dump(self):
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.data.model':
            pass
        elif active_model == 'tender_cat.file_chunk':
            record_ids = self._context.get('active_ids')
            if record_ids:
                dump = data_dump.DataDump(self.env, self.data_model_id.id)
                dump.make_dump('file_chunk', record_ids)
