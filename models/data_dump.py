# -*- coding: utf-8 -*-

from odoo import models, fields
import logging
import os

_logger = logging.getLogger(__name__)


class DataDump:
    """ Data dumper for data models """
    _data_model_ids = []
    _env = None

    def __init__(self, env, data_model=None):
        self._env = env
        if data_model is not None:
            self._data_model_ids = data_model if isinstance(data_model, list) else [data_model]
        else:
            # Find all models with data dumping
            self._data_model_ids = []
            for data_model in self._env['tender_cat.data.model'].search([('use_data_dumping', '=', 1)]):
                self._data_model_ids.append(data_model.id)

    def register_label_change(self, label_id, chunk_id):
        """
        Register changes for all models who use this particular label_id
        """
        if not self._data_model_ids:
            return

        query = """SELECT data_model_id FROM tender_cat_data_model_labels_rel 
                    WHERE label_id = %s AND data_model_id IN %s """
        self._env.cr.execute(query, (label_id, tuple(self._data_model_ids)))
        found_ids = list(v[0] for v in self._env.cr.fetchall())
        for model_id in found_ids:
            reg_val = {
                'label_id': label_id,
                'chunk_id': chunk_id,
                'user_id': self._env.user.id,
                'data_model_id': model_id,
                'dump_number': self._env['tender_cat.data.model'].browse(model_id).dump_number
            }
            self._env['tender_cat.change.register'].create(reg_val)

    def folder(self, data_model=None):
        proc_folder = str(self._env["ir.config_parameter"].sudo()
                          .get_param("tender_cat.processing_folder", default='~/'))
        if data_model is not None:
            if type(data_model) is int:
                model_folder = os.path.join(proc_folder, 'model', 'dump', str(data_model))
            else:
                model_folder = os.path.join(proc_folder, 'model', 'dump', str(data_model.id))
        else:
            model_folder = os.path.join(proc_folder, 'model', 'dump')
        if not os.path.exists(model_folder):
            os.makedirs(model_folder)
        return model_folder

    def make_dump(self, data_type, ids=None, folder=None):
        """
        Make dump for models, who interested in data_type
        """
        dump_folder = self.folder(data_model) if folder is None else folder

        if not os.path.exists(dump_folder):
            os.makedirs(dump_folder)

        for data_model_id in self._data_model_ids:
            data_model = self._env['tender_cat.data.model'].browse(data_model_id)
            if data_model:
                data_model.dump_data(dump_folder, data_type=data_type, ids=ids)

    def changes(self, data_model=None):
        """
        yield change_record
        data_model.dump_changes(folder)
        cleanup_changes(data_model, dump_number)
        """


class DataDumpChangeRegister(models.Model):
    """ Registered data changes for further dumping """
    _name = 'tender_cat.change.register'
    _description = 'Data change registration'

    data_model_id = fields.Many2one('tender_cat.data.model', index=True)
    dump_number = fields.Integer(default=0)
    label_id = fields.Many2one('tender_cat.label', index=True)
    chunk_id = fields.Many2one('tender_cat.file_chunk', index=True)
    file_id = fields.Many2one(related='chunk_id.tender_file_id', index=True, readonly=True, store=True)
    tender_id = fields.Many2one(related='chunk_id.tender_id', index=True, readonly=True, store=True)
    user_id = fields.Many2one('res.users', index=True)
    color = fields.Integer(related='label_id.color', readonly=True, store=True)
