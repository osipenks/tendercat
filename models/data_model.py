# -*- coding: utf-8 -*-

from odoo import models, fields, _
from . import da_reqdoc_deep_sim_pipeline
#from . import utils
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

    def get_model_folder(self, folder_type):
        folder_for_models = str(self.env["ir.config_parameter"].sudo()
                                .get_param("tender_cat.processing_folder", default='~/'))
        full_path = os.path.join(folder_for_models, 'model', folder_type, str(self.id))
        if not os.path.exists(full_path):
            os.makedirs(full_path)
        return full_path

    def get_user_labeled_files(self):
        #   Dump only user labeled files
        label_ids = self.label_ids.mapped('id')
        query = """
                    SELECT tender_file_id
                            FROM (
                                    SELECT DISTINCT tender_file_id
                                    FROM tender_cat_file_chunk_tender_cat_label_rel AS chunk_labels
                                    LEFT JOIN  tender_cat_file_chunk AS chunks
                                    ON chunks.id = chunk_labels.tender_cat_file_chunk_id AND chunks.user_edited_label
                                    WHERE tender_cat_label_id IN %s AND tender_file_id IS NOT NULL
                                     UNION
                                                     SELECT DISTINCT tender_file_id
                                                     FROM tender_cat_file_chunk AS example_chunks
                                                              LEFT JOIN tender_cat_tender AS tender
                                                                        ON example_chunks.tender_id = tender.id
                                                                            AND tender.is_training_example
                                                     WHERE tender.id IS NOT NULL
                                 ) as sel
                """
        self.env.cr.execute(query, (tuple(label_ids),))
        return list(v[0] for v in self.env.cr.fetchall())

    def refit_make_sens(self):
        return self._refit_make_sens

    def tuning_make_sens(self):
        return self._tuning_make_sens

    def tune_model(self):
        raise NotImplementedError

    def refit_model(self, a):
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

        # Clean folder before dumping
        for filename in os.listdir(dump_folder):
            file_path = os.path.join(dump_folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
            except Exception as e:
                a.warning('Failed to delete {}: {}'.format(file_path, e))
                return

        # Dump files to folder
        file_ids = self.get_user_labeled_files()
        self.dump_chunk_files(dump_folder, file_ids)
        if not file_ids:
            a.warning('Refit for {} failed, there is no data for model!'.format(self.name))
            return

        # 2. Call data algorithm to fit the model
        trained_folder = self.get_model_folder('trained')

        model = da_reqdoc_deep_sim_pipeline.DataPipeline(
            data_folder=dump_folder,
            trained_folder=trained_folder,
            a=a)
        model.fit()

    def transform_data(self, obj_id=None):
        # todo: make child classes, specialized models for different tasks
        with RunActivity(self, 'Transform', obj_id) as a:
            # Prepare input/output files
            trained_folder = self.get_model_folder('trained')
            run_folder = self.get_model_folder('run')
            model_input = os.path.join(run_folder, str(a.id)+'input.csv')
            model_output = os.path.join(run_folder, str(a.id)+'output.csv')

            # Dump texts from tender files to input.csv
            query = """SELECT DISTINCT tender_file_id FROM tender_cat_file_chunk WHERE tender_id = %s """
            self.env.cr.execute(query, (obj_id,))
            file_ids = list(v[0] for v in self.env.cr.fetchall())
            a.log('{} files selected to unload'.format(len(file_ids)))
            self.dump_chunk_files(run_folder, file_ids, model_input)

            # Call algorithm to transform data
            model = da_reqdoc_deep_sim_pipeline.DataPipeline(trained_folder=trained_folder, a=a)
            model.transform(input_file=model_input, output_file=model_output, trained_folder=trained_folder, a=a)

            # Check if the output data exist
            if not os.path.isfile(model_output):
                a.log('Error: model output file {} not found'.format(model_output))
                model_output = model_input
                #return

            # Upload data from model output file, update file chunks labels
            chunks = self.env['tender_cat.file_chunk']
            labels = self.env['tender_cat.label']
            cnt_loaded, cnt_labeled = 0, 0
            with open(model_output, mode='r') as f:
                score_val = 0
                reader = csv.DictReader(f)
                for line in reader:
                    cnt_loaded += 1
                    is_req_doc = False
                    chunk_id = int(line['text_id'])
                    label_id = line['label_id']
                    chunk = chunks.browse(chunk_id)
                    if not chunk:
                        a.log('Warning: text not found, id {} content {}'.format(chunk_id, line['text']))
                        continue
                    if label_id:
                        is_req_doc = True
                        labels_ids = labels.search([('id', '=', label_id)]).ids
                        chunk.write({
                            'req_doc_score': score_val,
                            'is_req_doc': is_req_doc,
                            'user_label_ids': [(4, labels_ids[0])]
                        })
                        cnt_labeled += 1
                    else:
                        if chunk.user_label_ids:
                            is_req_doc = True
                        chunk.write({'req_doc_score': score_val, 'is_req_doc': is_req_doc, })

                a.log('Labels {}, loaded {} texts from {}'.format(cnt_labeled, cnt_loaded, model_output))

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
        with RunAsyncActivity(self, 'Refit'):
            _logger.info('Asynchronous activity {} started '.format('Refit'))

    def action_make_data_dump(self):
        """
        Call wizard to help user make a dump
        """
        return self.env['tender_cat.data.dump.wizard'] \
            .with_context(active_ids=self.ids, active_model='tender_cat.data.model', active_id=self.id) \
            .action_make_data_dump()

    def dump_chunk_files(self, folder, file_ids, file_name=None):
        """
        Dump all chunks of specified files to csv, with labels used by data model
        """
        csv_file_name = file_name
        open_mode = 'a'

        model_label_ids = self.label_ids.mapped('id')
        # get all file ids of selected chunks
        for file_id in file_ids:
            # for each file create csv copy
            file = self.env['ir.attachment'].browse(file_id)
            origin_file_name = file.name
            _logger.info('Dumping {} to csv in {}'.format(origin_file_name, folder))

            if file_name is None:
                # A separate file for each file_id
                name, file_ext = os.path.splitext(origin_file_name)
                csv_file_name = os.path.join(folder, name + '.csv')
                open_mode = 'w'

            with open(csv_file_name, mode=open_mode) as file:
                # dump chunks in csv file
                csv_fields = ['label_id', 'label_name', 'text', 'text_id', 'file', 'tender']
                writer = csv.DictWriter(file, fieldnames=csv_fields, delimiter=',')

                if os.stat(csv_file_name).st_size == 0:
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
                                val.update({'label_id': label.id, 'label_name': label.name, })
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
                query = """
                        SELECT tender_file_id
                            FROM (
                                     SELECT DISTINCT tender_file_id
                                     FROM tender_cat_file_chunk_tender_cat_label_rel AS chunk_labels
                                              LEFT JOIN tender_cat_file_chunk AS chunks
                                                        ON chunks.id = chunk_labels.tender_cat_file_chunk_id
                                     WHERE tender_cat_label_id IN %s
                                       AND tender_file_id IS NOT NULL
                            
                                     UNION
                            
                                     SELECT DISTINCT tender_file_id
                                     FROM tender_cat_file_chunk AS example_chunks
                                              LEFT JOIN tender_cat_tender AS tender
                                                        ON example_chunks.tender_id = tender.id
                                                            AND tender.is_training_example
                                     WHERE tender.id IS NOT NULL
                                 ) as sel
                            """
                self.env.cr.execute(query, (tuple(label_ids),))
                file_ids = list(v[0] for v in self.env.cr.fetchall())
                self.dump_chunk_files(folder, file_ids)

        self.dump_number += 1
        self.write({'dump_number': self.dump_number})

    def dump_changes(self, data_type=None, ids=None):
        raise NotImplementedError
