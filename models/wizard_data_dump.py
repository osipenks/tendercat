# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from . import data_dump
import logging
import tempfile
from .utils import zip_folder, clean_folder
import base64


_logger = logging.getLogger(__name__)


class DataDumpWizard(models.TransientModel):
    """
    Dump data for data models
    """
    _name = 'tender_cat.data.dump.wizard'
    _description = 'Dump data for data models'

    data_model_id = fields.Many2one('tender_cat.data.model', string='Data model')

    labels_kind = fields.Selection([
        ('edited', 'Only labeled by user'),
        ('all', 'All labeled data')],
        'Labels', required=True, default='edited',
    )

    dump_folder = fields.Char(string="Dump to folder")

    archive_name = fields.Char(string='Archive name')

    data = fields.Binary('File', readonly=True, attachment=False)
    state = fields.Selection([('choose', 'choose'), ('get', 'get')],  # choose arch name or get the file
                             default='choose')
    moto = fields.Text(default=_('Great! Archive is ready, you can download it now'))

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
            result['labels_kind'] = 'all'

        data_model_id = result.get('data_model_id')
        if data_model_id:
            dump = data_dump.DataDump(self.env, data_model_id)
            result['dump_folder'] = dump.folder(data_model_id)
            data_model = self.env['tender_cat.data.model'].browse(data_model_id)
            result['archive_name'] = data_model.name

        return result

    @api.onchange('data_model_id')
    def _onchange_tender(self):
        dump = data_dump.DataDump(self.env, self.data_model_id)
        self.dump_folder = dump.folder(self.data_model_id)

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

    def create_archive(self):
        this = self[0]
        pdf_ext = 'pdf'
        zip_ext = 'zip'
        arch_name = "%s.%s" % (this.archive_name, zip_ext)

        self.make_data_dump()

        # Make archive from files in folder
        tmp_file = tempfile.NamedTemporaryFile()
        zip_folder(self.dump_folder, tmp_file.name)

        vals = {'state': 'get', 'archive_name': arch_name}

        # Save archive to binary field
        with open(tmp_file.name, 'rb') as arch_file:
            out = base64.b64encode(arch_file.read())
            if out:
                vals.update({'data': out})

        tmp_file.close()
        this.write(vals)
        clean_folder(self.dump_folder)

        return {
            'name': _('Download proposal files'),
            'type': 'ir.actions.act_window',
            'res_model': 'tender_cat.data.dump.wizard',
            'view_mode': 'form',
            'res_id': this.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def make_data_dump(self):
        dump = data_dump.DataDump(self.env, self.data_model_id.id)
        active_model = self._context.get('active_model')
        chunks = self.env['tender_cat.file_chunk']
        if active_model == 'tender_cat.data.model':
            if self.labels_kind == 'all':
                dump.make_dump('file_chunk', folder=self.dump_folder)
            else:
                chunk_ids = chunks.search([('user_edited_label', '=', 1)]).ids
                dump.make_dump('file_chunk', ids=chunk_ids, folder=self.dump_folder)
        elif active_model == 'tender_cat.file_chunk':
            record_ids = self._context.get('active_ids')
            if record_ids:
                if self.labels_kind == 'all':
                    dump.make_dump('file_chunk', ids=record_ids, folder=self.dump_folder)
                else:
                    chunk_ids = chunks.search(['&',
                                               ('user_edited_label', '=', 1),
                                               ('id', 'in', tuple(record_ids)), ]).ids
                    if chunk_ids:
                        dump.make_dump('file_chunk', ids=chunk_ids, folder=self.dump_folder)
