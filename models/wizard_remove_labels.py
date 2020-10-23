# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from . import data_dump
import logging

_logger = logging.getLogger(__name__)


class RemoveLabelsWizard(models.TransientModel):
    """
    Dump data for data models
    """
    _name = 'tender_cat.remove.labels.wizard'
    _description = 'Remove labels from texts'

    tender_id = fields.Many2one('tender_cat.tender', string='Tender')
    leave_user_edited_flag = fields.Boolean(string='Leave \'User edited text\' marks', default=True)

    @api.model
    def default_get(self, default_fields):
        result = super(RemoveLabelsWizard, self).default_get(default_fields)
        active_model = self._context.get('active_model')
        if active_model == 'tender_cat.tender':
            active_id = self._context.get('active_id')
            if active_id:
                result['tender_id'] = self.env['tender_cat.tender'].browse(active_id).id
        return result

    def action_remove_labels(self):
        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            return {}
        # active_ids = self.ids, active_model = 'tender_cat.data.model', active_id = self.id
        # active_model = self._context.get('active_model')
        # if active_model == 'tender_cat.tender':
        #     pass

        return {
            'name': _('Remove labels from texts'),
            'res_model': 'tender_cat.remove.labels.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('view_tender_cat_remove_labels_wizard_form').id,
            'context': self.env.context,
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    def remove_labels(self):
        """
        Take off labels from tender's texts
        """
        chunks = self.env['tender_cat.file_chunk']
        chunk_ids = chunks.search([
            ('tender_id', '=', self.tender_id.id),
        ]).ids

        for chunk in chunks.browse(chunk_ids):
            vals = {
                'user_label_ids': [(5, )]
            }
            if not self.leave_user_edited_flag:
                vals.update({'user_edited_label': 0})

            chunk.write(vals)
