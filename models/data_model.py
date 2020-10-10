# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from . import da_reqdoc_classifier
from . import utils
from .data_model_activity import RunActivity, RunAsyncActivity
import logging
import csv
import os


_logger = logging.getLogger(__name__)


class DataModel(models.Model):
    _name = 'tender_cat.data.model'
    _description = "Data model"
    _refit_make_sens = fields.Boolean(default=False)
    _tuning_make_sens = fields.Boolean(default=False)

    name = fields.Char(string='Name')
    description = fields.Text(string='Detailed description')

    dump_number = fields.Integer(string='Last dump number')
    use_data_dumping = fields.Boolean(string='Use data dumping')

    label_ids = fields.Many2many(
        'tender_cat.label', 'tender_cat_data_model_labels_rel', 'data_model_id', 'label_id',
        string='Use labels',
    )

    last_activity_id = fields.Many2one('tender_cat.data.model.activity', string='Data model activity')
    activity_started = fields.Boolean()

    activities_count = fields.Integer(compute='_compute_activities_count',
                                      string="Number of required documents")

    def _compute_activities_count(self):
        query = """SELECT COUNT(DISTINCT id) AS count
                                FROM tender_cat_data_model_activity
                                WHERE   data_model_id = %s"""
        for data_model in self:
            self.env.cr.execute(query, (data_model.id,))
            res = self.env.cr.dictfetchone()
            if res:
                data_model.activities_count = res['count']

    def start_activity(self, activity_type, cron=True):

        activity = self.env['tender_cat.data.model.activity']
        new_act = activity.create({'data_model_id': self.id,
                                   'activity_type': activity_type,
                                   })

        self.write({'last_activity_id': new_act.id, 'activity_started': True, })

        code = 'env[\'tender_cat.data.model.activity\'].browse({}).run(env[\'tender_cat.data.model\'].browse({}))'\
            .format(new_act.id, self.id)
        task_name = 'Data model {}: {}'.format(self.id, activity_type)

        utils.start_cron_task(self, task_name, code)

        return int(new_act.id)

    def stop_activity(self, activity_id=None):
        self.write({'activity_started': False})

    def get_model_folder(self, folder_type):
        folder_for_models = str(self.env["ir.config_parameter"].sudo()
                                .get_param("tender_cat.processing_folder", default='~/'))
        return os.path.join(folder_for_models, 'model', folder_type, str(self.id))

    def get_user_labeled_files(self):
        #   Dump only user labeled files
        label_ids = self.label_ids.mapped('id')
        query = """SELECT DISTINCT tender_file_id
                    FROM tender_cat_file_chunk_tender_cat_label_rel AS chunk_labels
                    LEFT JOIN  tender_cat_file_chunk AS chunks
                    ON chunks.id = chunk_labels.tender_cat_file_chunk_id AND chunks.user_edited_label
                    WHERE tender_cat_label_id IN %s AND tender_file_id IS NOT NULL"""
        self.env.cr.execute(query, (tuple(label_ids),))
        return list(v[0] for v in self.env.cr.fetchall())

    def refit_make_sens(self):
        return self._refit_make_sens

    def tuning_make_sens(self):
        return self._tuning_make_sens

    def tune_model(self):
        raise NotImplementedError

    def refit_model(self):
        """
        Change model stage to Refit
        Dump all user labeled data
        Call data algorithm to fit the model
        Backup model files to ./bkp folder, copy new model files to folder ./trained
        Change model stage to Ready
        """
        # todo: with DataModelActivity('Refit'):
        # 1. Dump all user labeled data
        dump_folder = self.get_model_folder('dump')
        if not os.path.exists(dump_folder):
            os.makedirs(dump_folder)

        # Clean folder before dumping
        for filename in os.listdir(dump_folder):
            file_path = os.path.join(dump_folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
            except Exception as e:
                _logger.warning('Failed to delete {}: {}'.format(file_path, e))
                self.stop_activity()

        # Dump files to folder
        file_ids = self.get_user_labeled_files()
        self.dump_chunk_files(dump_folder, file_ids)
        if not file_ids:
            _logger.warning('Refit for {} failed, there is no data for model!'.format(self.name))
            return

        # 2. Call data algorithm to fit the model
        trained_folder = self.get_model_folder('trained')
        if not os.path.exists(trained_folder):
            os.makedirs(trained_folder)

        model = da_reqdoc_classifier.DataTransformer(data_folder=dump_folder,
                                                     trained_folder=trained_folder)
        model.fit()

        # 3. Stop activity, if it started before
        self.stop_activity()

    def transform_data(self, obj_id=None):
        # todo: make child classes, specialized models for different tasks
        with RunActivity(self, 'Transform', obj_id) as a:
            a.log('Running within with statement, a: {}'.format(a))
            # Prepare data for classification:
            #   data frame with label, text_id, text, file_name, file_id, tender_id, tender_name
            # Call data algorithm transform,
            # Updates text chunks labels
            a.log('A little bit more logging')

    def stat_button_data_model_activities(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tender_cat.data.model.activity',
            'name': "Activities",
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {'search_default_data_model_id': self.id},
        }

    def action_refit_model(self):
        self.start_activity('Refit')

    def action_make_data_dump(self):
        """
        Call wizard to help user make a dump
        """
        return self.env['tender_cat.data.dump.wizard'] \
            .with_context(active_ids=self.ids, active_model='tender_cat.data.model', active_id=self.id) \
            .action_make_data_dump()

    def dump_chunk_files(self, folder, file_ids):
        """
        Dump all chunks of specified files to csv, with labels used by data model
        """
        model_label_ids = self.label_ids.mapped('id')
        # get all file ids of selected chunks
        for file_id in file_ids:
            # for each file create csv copy
            file = self.env['ir.attachment'].browse(file_id)
            origin_file_name = file.name
            _logger.info('Dumping {} to csv in {}'.format(origin_file_name, folder))
            file_name, file_ext = os.path.splitext(origin_file_name)
            csv_file_name = os.path.join(folder, file_name + '.csv')
            with open(csv_file_name, mode='w') as file:
                # dump chunks in csv file
                csv_fields = ['label_id', 'label_name', 'text', 'text_id', 'file', 'tender']
                writer = csv.DictWriter(file, fieldnames=csv_fields, delimiter=',')
                writer.writeheader()
                chunks = self.env['tender_cat.file_chunk'].search([('tender_file_id', '=', file_id)])
                for chunk in chunks:
                    val = {'label_id': '',
                           'label_name': '',
                           'text': chunk.chunk_text,
                           'text_id': chunk.id,
                           'file': origin_file_name,
                           'tender': chunk.tender_id.tender_id,
                           }
                    labels = chunk['user_label_ids']
                    if labels:
                        # check whether data model uses label
                        chunk_written = False
                        for label in labels:
                            if label.id in model_label_ids:
                                val.update({'label_id': label.id,
                                            'label_name': label.name,
                                            })
                                writer.writerow(val)
                                chunk_written = True
                        if not chunk_written:
                            # if not, write without label
                            writer.writerow(val)
                    else:
                        writer.writerow(val)

    def dump_data(self, folder, data_type=None, ids=None):
        if data_type == 'file_chunk':
            if ids is not None and ids:
                # Find file ids for specified chunks
                query = """SELECT DISTINCT tender_file_id FROM tender_cat_file_chunk 
                                               WHERE id IN %s """
                self.env.cr.execute(query, (tuple(ids),))
                file_ids = list(v[0] for v in self.env.cr.fetchall())
                self.dump_chunk_files(folder, file_ids)
            else:
                # Find file ids for labels used by data model
                label_ids = self.label_ids.mapped('id')
                query = """SELECT DISTINCT tender_file_id
                            FROM tender_cat_file_chunk_tender_cat_label_rel AS chunk_labels
                            LEFT JOIN  tender_cat_file_chunk AS chunks
                            ON chunks.id = chunk_labels.tender_cat_file_chunk_id
                            WHERE tender_cat_label_id IN %s AND tender_file_id IS NOT NULL
                            """
                self.env.cr.execute(query, (tuple(label_ids),))
                file_ids = list(v[0] for v in self.env.cr.fetchall())
                self.dump_chunk_files(folder, file_ids)

        self.dump_number += 1
        self.write({'dump_number': self.dump_number})

    def dump_changes(self, data_type=None, ids=None):
        raise NotImplementedError
