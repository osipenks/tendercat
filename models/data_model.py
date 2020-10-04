# -*- coding: utf-8 -*-

from odoo import models, fields
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

    def refit_make_sens(self):
        return self._refit_make_sens

    def tuning_make_sens(self):
        return self._tuning_make_sens

    def tune(self):
        pass

    def refit_model(self):
        pass

    def transform_data(self):
        pass

    def action_make_data_dump(self):
        return self.env['tender_cat.data.dump.wizard'] \
            .with_context(active_ids=self.ids, active_model='tender_cat.data.model', active_id=self.id) \
            .action_make_data_dump()

    def dump_data(self, folder, data_type=None, ids=None):
        if data_type == 'file_chunk':
            # get all file ids of chunks
            query = """SELECT DISTINCT tender_file_id FROM tender_cat_file_chunk 
                       WHERE id IN %s """
            self.env.cr.execute(query, (tuple(ids),))
            for file_id in list(v[0] for v in self.env.cr.fetchall()):
                file = self.env['ir.attachment'].browse(file_id)
                origin_file_name = file.name
                _logger.info('Dumping {} {} to csv in {}'.format(data_type, origin_file_name, folder))
                file_name, file_ext = os.path.splitext(origin_file_name)
                csv_file_name = os.path.join(folder, file_name+'.csv')
                with open(csv_file_name, mode='w') as file:
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
                            for label in labels:
                                val.update({'label_id': label.id,
                                            'label_name': label.name,
                                            })
                                writer.writerow(val)
                        else:
                            writer.writerow(val)

        self.dump_number += 1
        self.write({'dump_number': self.dump_number})

    def dump_changes(self, data_type=None, ids=None):
        pass
