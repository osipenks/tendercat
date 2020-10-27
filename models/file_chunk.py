# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
from . import data_dump

_logger = logging.getLogger(__name__)


class FileChunk(models.Model):
    _name = 'tender_cat.file_chunk'
    _description = "File chunk"

    tender_id = fields.Many2one('tender_cat.tender', index=True, ondelete='cascade', string='Tender', required=True)
    tender_file_id = fields.Many2one('ir.attachment', index=True, string='File', required=True)

    user_label_ids = fields.Many2many('tender_cat.label', string='Labels', index=True)
    user_edited_label = fields.Boolean(default=False)
    edited_by_id = fields.Many2one('res.users', string='Edited by', index=True)

    chunk_id = fields.Integer(string='Chunk ID', index=True, group_operator='count')
    name = fields.Char(string='Chunk name')
    chunk_text = fields.Text(string='Text', index=True, help='')

    is_req_doc = fields.Boolean(string='It\'s a required document')
    is_doc_context = fields.Boolean(string='It\'s a document\'s context', index=True)

    _order = 'tender_file_id asc, chunk_id asc'
    _log_access = False

    # score, predicted_tags, user_tags, tender_assessment

    @api.onchange('user_label_ids')
    def _onchange_user_label_ids(self):
        tender = self.env['tender_cat.tender'].browse(self.tender_id.id)
        if tender:
            tender.mark_contexts(self._origin.id)
        self.write({'user_edited_label': 1, 'edited_by_id': self.env.user.id})

    def write(self, vals):
        # If user changes label, register chunk for dumping
        user_label_ids = vals.get('user_label_ids', 0)
        if user_label_ids:
            # vals['user_edited_label'] = 1  # mark chunk as user labeled
            for labels in vals['user_label_ids']:
                value_op = labels[0]
                ids = []
                if value_op in [1, 2, 3]:
                    ids = [labels[1]]
                elif value_op in [6]:
                    ids = labels[2]
                else:
                    # todo: ``(5, 0, 0)`` removes all
                    pass
                if ids:
                    dump = data_dump.DataDump(self.env)
                    for label_id in ids:
                        dump.register_label_change(label_id, self._origin.id)

        res = super(FileChunk, self).write(vals) if vals else True
        return res

    def action_make_data_dump(self):
        return self.env['tender_cat.data.dump.wizard'] \
            .with_context(active_ids=self.ids, active_model='tender_cat.file_chunk', active_id=self.id) \
            .action_make_data_dump()
