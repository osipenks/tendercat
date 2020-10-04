# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
from . import data_dump

_logger = logging.getLogger(__name__)


class FileChunk(models.Model):
    _name = 'tender_cat.file_chunk'
    _description = "File chunk"

    tender_id = fields.Many2one('tender_cat.tender', index=True, string='Tender', required=True)
    tender_file_id = fields.Many2one('ir.attachment', index=True, string='File', required=True)

    user_label_ids = fields.Many2many('tender_cat.label', string='Labels', index=True)

    chunk_id = fields.Integer(string='Chunk ID', index=True, group_operator='count')
    name = fields.Char(string='Chunk ID')
    chunk_text = fields.Text(string='Text', index=True, help='')

    is_req_doc = fields.Boolean(string='It\'s a required document')
    is_doc_context = fields.Boolean(string='It\'s a document\'s context', index=True)

    req_doc_score = fields.Float(default=0, string='Req doc score', digits=(18, 16), group_operator='avg')

    is_qualification = fields.Boolean(string='It\'s a qualification')

    _order = 'tender_file_id asc, chunk_id asc'

    # score, predicted_tags, user_tags, tender_assessment

    @api.onchange('user_label_ids')
    def _onchange_user_label_ids(self):
        tender = self.env['tender_cat.tender'].browse(self.tender_id.id)
        if tender:
            tender.mark_contexts(self._origin.id)

    def write(self, vals):

        # If user changes label, register chunk for dumping
        user_label_ids = vals.get('user_label_ids', 0)
        if user_label_ids:
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


class MakeDumpFileChunk(models.TransientModel):
    """
        Dump file chunks for data models
    """
    _name = 'tender_cat.make.dump.file.chunk'
    _description = 'Dump file chunks for data model'

    data_model_id = fields.Many2one('tender_cat.data.model', string='Data model')
    user_id = fields.Many2one('res.users', 'User', index=True)

    @api.model
    def default_get(self, default_fields):
        result = super(MakeDumpFileChunk, self).default_get(default_fields)
        if 'data_model_id' in default_fields:
            found_ids = self.env['tender_cat.data.model'].search([('use_data_dumping', '=', 1)])
            if found_ids:
                result['data_model_id'] = found_ids[0].id

        return result

    def action_make_dump(self):
        self.ensure_one()
        record_ids = self._context.get('active_ids')
        if record_ids:
            dump = data_dump.DataDump(self.env, self.data_model_id.id)
            dump.make_dump('file_chunk', record_ids)
