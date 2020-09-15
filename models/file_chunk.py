# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class FileChunk(models.Model):
    _name = 'tender_cat.file_chunk'
    _description = "File chunk"

    tender_id = fields.Many2one('tender_cat.tender', index=True, string='Tender', required=True)
    tender_file_id = fields.Many2one('ir.attachment', index=True, string='File', required=True)

    user_label_ids = fields.Many2many('tender_cat.label', string='Labels')

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
